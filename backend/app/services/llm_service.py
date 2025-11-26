import logging
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import httpx
from fastapi import HTTPException, status
from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, InternalServerError

from ..core.config import settings
from ..mcp import UniversalMCPAdapter
from ..repositories.llm_config_repository import LLMConfigRepository
from ..repositories.system_config_repository import SystemConfigRepository
from ..repositories.user_repository import UserRepository
from ..services.admin_setting_service import AdminSettingService
from ..services.prompt_service import PromptService
from ..services.usage_service import UsageService
from ..utils.llm_tool import ChatMessage, LLMClient

if TYPE_CHECKING:
    from ..services.mcp_tool_service import MCPToolService

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 运行环境未安装时兼容
    from ollama import AsyncClient as OllamaAsyncClient
except ImportError:  # pragma: no cover - Ollama 为可选依赖
    OllamaAsyncClient = None


class LLMService:
    """封装与大模型交互的所有逻辑，包括配额控制与配置选择。"""

    def __init__(
        self,
        session,
        mcp_tool_service: Optional["MCPToolService"] = None,
        enable_mcp_adapter: bool = True,
    ):
        self.session = session
        self.llm_repo = LLMConfigRepository(session)
        self.system_config_repo = SystemConfigRepository(session)
        self.user_repo = UserRepository(session)
        self.admin_setting_service = AdminSettingService(session)
        self.usage_service = UsageService(session)
        self._embedding_dimensions: Dict[str, int] = {}
        self.mcp_tool_service = mcp_tool_service
        self.enable_mcp_adapter = enable_mcp_adapter
        self.mcp_adapter: Optional[UniversalMCPAdapter]
        if enable_mcp_adapter:
            self.mcp_adapter = UniversalMCPAdapter()
        else:
            self.mcp_adapter = None

    async def get_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = "json_object",
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
        )

    async def get_summary(
        self,
        chapter_content: str,
        *,
        temperature: float = 0.2,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        system_prompt: Optional[str] = None,
    ) -> str:
        if not system_prompt:
            prompt_service = PromptService(self.session)
            system_prompt = await prompt_service.get_prompt("extraction")
        if not system_prompt:
            logger.error("未配置名为 'extraction' 的摘要提示词，无法生成章节摘要")
            raise HTTPException(status_code=500, detail="未配置摘要提示词，请联系管理员配置 'extraction' 提示词")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter_content},
        ]
        return await self._stream_and_collect(messages, temperature=temperature, user_id=user_id, timeout=timeout)

    async def _stream_and_collect(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        user_id: Optional[int],
        timeout: float,
        response_format: Optional[str] = None,
    ) -> str:
        config = await self._resolve_llm_config(user_id)
        client = LLMClient(api_key=config["api_key"], base_url=config.get("base_url"))

        chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]

        full_response = ""
        finish_reason = None

        logger.info(
            "开始流式生成 LLM 响应: 模型=%s 用户=%s 消息数=%d",
            config.get("model"),
            user_id,
            len(messages),
        )

        try:
            async for part in client.stream_chat(
                messages=chat_messages,
                model=config.get("model"),
                temperature=temperature,
                timeout=int(timeout),
                response_format=response_format,
            ):
                if part.get("content"):
                    full_response += part["content"]
                if part.get("finish_reason"):
                    finish_reason = part["finish_reason"]
        except InternalServerError as exc:
            detail = "AI 服务内部错误，请稍后重试"
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    payload = response.json()
                    error_data = payload.get("error", {}) if isinstance(payload, dict) else {}
                    detail = error_data.get("message_zh") or error_data.get("message") or detail
                except Exception:
                    detail = str(exc) or detail
            else:
                detail = str(exc) or detail
            logger.error(
                "LLM 流式调用内部错误: 模型=%s 用户=%s 详情=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail)
        except (httpx.RemoteProtocolError, httpx.ReadTimeout, APIConnectionError, APITimeoutError) as exc:
            if isinstance(exc, httpx.RemoteProtocolError):
                detail = "AI 服务连接被意外中断，请稍后重试"
            elif isinstance(exc, (httpx.ReadTimeout, APITimeoutError)):
                detail = "AI 服务响应超时，请稍后重试"
            else:
                detail = "无法连接到 AI 服务，请稍后重试"
            logger.error(
                "LLM 流式调用失败: 模型=%s 用户=%s 详情=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail) from exc

        logger.debug(
            "LLM 响应收集完成: 模型=%s 用户=%s 结束原因=%s 响应预览=%s",
            config.get("model"),
            user_id,
            finish_reason,
            full_response[:500],
        )

        if finish_reason == "length":
            logger.warning(
                "LLM 响应因长度被截断: 模型=%s 用户=%s 响应长度=%d",
                config.get("model"),
                user_id,
                len(full_response),
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 响应因长度限制被截断（已生成 {len(full_response)} 字符），请缩短输入内容或调整模型参数"
            )

        if not full_response:
            logger.error(
                "LLM 返回空响应: 模型=%s 用户=%s 结束原因=%s",
                config.get("model"),
                user_id,
                finish_reason,
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 未返回有效内容（结束原因: {finish_reason or '未知'}），请稍后重试或联系管理员"
            )

        await self.usage_service.increment("api_request_count")
        logger.info(
            "LLM 响应成功: 模型=%s 用户=%s 字符数=%d",
            config.get("model"),
            user_id,
            len(full_response),
        )
        return full_response

    async def generate_text(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = None,
    ) -> str:
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
        )

    async def generate_with_mcp(
        self,
        prompt: str,
        user_id: int,
        *,
        enable_mcp: bool = True,
        max_tool_rounds: int = 3,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        """
        使用 MCP 工具增强的文本生成
        
        Args:
            prompt: 生成提示词
            user_id: 用户 ID
            enable_mcp: 是否启用 MCP 工具
            max_tool_rounds: 最大工具调用轮次
            tool_choice: 工具选择策略（auto/required/none）
            temperature: 温度参数
            timeout: 超时时间
            
        Returns:
            {
                "content": "生成的文本",
                "tool_calls_made": 2,
                "tools_used": ["plugin.tool1", "plugin.tool2"],
                "finish_reason": "stop",
                "mcp_enhanced": True
            }
        """
        # 初始化结果
        result = {
            "content": "",
            "tool_calls_made": 0,
            "tools_used": [],
            "finish_reason": "",
            "mcp_enhanced": False
        }
        
        # 1. 获取 MCP 工具（如果启用）
        tools = None
        if enable_mcp and self.mcp_tool_service:
            try:
                tools = await self.mcp_tool_service.get_user_enabled_tools(user_id)
                if tools:
                    logger.info(f"MCP 增强: 用户 {user_id} 加载了 {len(tools)} 个工具")
                    result["mcp_enhanced"] = True
                else:
                    logger.info(f"用户 {user_id} 未启用任何 MCP 工具，使用普通生成模式")
            except Exception as e:
                logger.error(
                    f"获取 MCP 工具失败，降级为普通生成: user_id={user_id} error={str(e)}",
                    exc_info=True
                )
                tools = None
        
        # 2. 如果没有工具，直接使用普通生成
        if not tools:
            content = await self._stream_and_collect(
                [{"role": "user", "content": prompt}],
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=None
            )
            result["content"] = content
            result["finish_reason"] = "stop"
            return result
        
        # 3. 工具调用循环
        conversation_history = [{"role": "user", "content": prompt}]
        
        for round_num in range(max_tool_rounds):
            logger.info(f"MCP 工具调用轮次: {round_num + 1}/{max_tool_rounds}")
            
            # 调用 AI（第一轮传递工具列表）
            ai_response = await self._call_llm_with_tools(
                conversation_history,
                tools=tools if round_num == 0 else None,
                tool_choice=tool_choice if round_num == 0 else None,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout
            )
            
            # 检查是否有工具调用
            tool_calls = ai_response.get("tool_calls", [])
            
            if not tool_calls:
                # AI 返回最终内容
                result["content"] = ai_response.get("content", "")
                result["finish_reason"] = ai_response.get("finish_reason", "stop")
                break
            
            # 4. 执行工具调用
            logger.info(f"AI 请求调用 {len(tool_calls)} 个工具: user_id={user_id} round={round_num + 1}")
            
            try:
                tool_results = await self.mcp_tool_service.execute_tool_calls(
                    user_id, tool_calls
                )
                
                # 检查是否所有工具调用都失败
                all_failed = all(not r.get("success", False) for r in tool_results)
                if all_failed:
                    logger.warning(
                        f"所有工具调用都失败，降级为普通生成模式: user_id={user_id} "
                        f"failed_tools={[r.get('name') for r in tool_results]}"
                    )
                    content = await self._stream_and_collect(
                        [{"role": "user", "content": prompt}],
                        temperature=temperature,
                        user_id=user_id,
                        timeout=timeout,
                        response_format=None
                    )
                    result["content"] = content
                    result["finish_reason"] = "stop"
                    # Keep mcp_enhanced = True because tools were available (just failed)
                    break
                
                # 记录使用的工具
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    if tool_name not in result["tools_used"]:
                        result["tools_used"].append(tool_name)
                
                result["tool_calls_made"] += len(tool_calls)
                
                # 记录成功和失败的工具
                success_count = sum(1 for r in tool_results if r.get("success", False))
                logger.info(
                    f"工具调用完成: user_id={user_id} success={success_count}/{len(tool_results)}"
                )
                
                # 5. 更新对话历史
                conversation_history.append({
                    "role": "assistant",
                    "content": ai_response.get("content", ""),
                    "tool_calls": tool_calls
                })
                
                # 添加工具结果
                for tool_result in tool_results:
                    conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "name": tool_result["name"],
                        "content": tool_result["content"]
                    })
                
            except Exception as e:
                logger.error(
                    f"工具调用执行失败，降级为普通生成: user_id={user_id} "
                    f"error={str(e)} round={round_num + 1}",
                    exc_info=True
                )
                # 降级为普通生成
                content = await self._stream_and_collect(
                    [{"role": "user", "content": prompt}],
                    temperature=temperature,
                    user_id=user_id,
                    timeout=timeout,
                    response_format=None
                )
                result["content"] = content
                result["finish_reason"] = "stop"
                # Keep mcp_enhanced = True because tools were available (just failed)
                break
        
        return result

    async def generate_text_with_mcp(
        self,
        messages: List[Dict[str, str]],
        user_id: int,
        *,
        temperature: float = 0.7,
        timeout: float = 300.0,
    ) -> str:
        """使用 MCP 工具支持生成文本。
        
        实现两轮 AI 调用逻辑：
        1. 第一轮：AI 分析任务并决定是否使用工具
        2. 如果 AI 返回工具调用，执行工具并收集结果
        3. 第二轮：AI 基于工具结果生成最终内容
        
        如果所有工具调用失败，系统会降级为普通生成模式。
        
        Args:
            messages: 对话消息列表
            user_id: 用户 ID
            temperature: 温度参数
            timeout: 超时时间
            
        Returns:
            生成的文本内容
            
        Raises:
            HTTPException: 当生成失败时
        """
        if not self.mcp_tool_service:
            logger.warning("MCP 工具服务未初始化，降级为普通生成模式")
            return await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=None
            )
        
        # 获取用户启用的 MCP 工具
        try:
            tools = await self.mcp_tool_service.get_user_enabled_tools(user_id)
            logger.info("用户 %d 启用了 %d 个 MCP 工具", user_id, len(tools))
        except Exception as exc:
            logger.error(
                "获取用户 MCP 工具失败，降级为普通生成模式: user_id=%d error=%s",
                user_id,
                str(exc),
                exc_info=True
            )
            return await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=None
            )
        
        # 如果没有启用的工具，直接使用普通生成
        if not tools:
            logger.info("用户 %d 未启用任何 MCP 工具，使用普通生成模式", user_id)
            return await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=None
            )
        
        # 第一轮：调用 AI 并提供工具
        try:
            response = await self._call_llm_with_tools(
                messages,
                tools=tools,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout
            )
        except Exception as exc:
            logger.error(
                "第一轮 AI 调用失败，降级为普通生成模式: user_id=%d error=%s",
                user_id,
                str(exc),
                exc_info=True
            )
            return await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=None
            )
        
        # 检查 AI 是否决定使用工具
        tool_calls = response.get("tool_calls")
        if not tool_calls:
            # AI 决定不使用工具，直接返回内容
            content = response.get("content", "")
            logger.info("AI 未使用工具，直接返回内容（长度: %d）", len(content))
            return content
        
        logger.info("AI 请求调用 %d 个工具", len(tool_calls))
        
        # 执行工具调用
        try:
            tool_results = await self.mcp_tool_service.execute_tool_calls(user_id, tool_calls)
            success_count = sum(1 for r in tool_results if r.get("success"))
            logger.info(
                "工具调用完成: user_id=%d success=%d/%d tools=%s",
                user_id,
                success_count,
                len(tool_results),
                [r.get("name") for r in tool_results]
            )
        except Exception as exc:
            logger.error(
                "工具调用执行失败，降级为普通生成模式: user_id=%d error=%s",
                user_id,
                str(exc),
                exc_info=True
            )
            return await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=None
            )
        
        # 检查是否所有工具调用都失败
        all_failed = all(not r.get("success", False) for r in tool_results)
        if all_failed:
            logger.warning(
                "所有工具调用都失败，降级为普通生成模式: user_id=%d failed_tools=%s",
                user_id,
                [r.get("name") for r in tool_results]
            )
            return await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=None
            )
        
        # 第二轮：将工具结果添加到对话历史，再次调用 AI
        # 添加 AI 的工具调用消息
        messages.append({
            "role": "assistant",
            "content": response.get("content") or "",
            "tool_calls": tool_calls
        })
        
        # 添加工具结果消息
        for tool_result in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tool_result["tool_call_id"],
                "name": tool_result["name"],
                "content": tool_result["content"]
            })
        
        # 第二轮调用 AI 生成最终内容
        try:
            final_content = await self._stream_and_collect(
                messages,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout,
                response_format=None
            )
            logger.info(
                "第二轮 AI 调用成功: user_id=%d content_length=%d",
                user_id,
                len(final_content)
            )
            return final_content
        except Exception as exc:
            logger.error(
                "第二轮 AI 调用失败: user_id=%d error=%s",
                user_id,
                str(exc),
                exc_info=True
            )
            raise
    
    async def _call_llm_with_tools(
        self,
        messages: List[Dict[str, str]],
        *,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        temperature: float,
        user_id: Optional[int],
        timeout: float,
    ) -> Dict[str, Any]:
        """调用 LLM 并提供工具列表。
        
        Args:
            messages: 对话消息列表
            tools: OpenAI Function Calling 格式的工具列表（可选）
            tool_choice: 工具选择策略（可选）
            temperature: 温度参数
            user_id: 用户 ID
            timeout: 超时时间
            
        Returns:
            包含 content 和可选 tool_calls 的响应字典
        """
        config = await self._resolve_llm_config(user_id)

        # 使用 OpenAI 客户端进行非流式调用（工具调用需要完整响应）
        client = AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url"),
        )

        # 定义底层调用封装，供通用适配器或直接调用使用
        async def call_api(
            *,
            message: str,
            tools_param: Optional[List[Dict[str, Any]]],
            tool_choice_param: Optional[str],
        ) -> Any:
            # 将最后一条用户消息替换为给定 message，用于提示词注入场景
            updated_messages: List[Dict[str, Any]] = []
            if messages:
                updated_messages = messages[:-1]
                last = messages[-1].copy()
                if last.get("role") == "user":
                    last["content"] = message
                updated_messages.append(last)
            else:
                updated_messages = [{"role": "user", "content": message}]

            request_params = {
                "model": config.get("model") or "gpt-3.5-turbo",
                "messages": updated_messages,
                "temperature": temperature,
                "timeout": timeout,
            }
            if tools_param:
                request_params["tools"] = tools_param
                if tool_choice_param:
                    request_params["tool_choice"] = tool_choice_param

            resp = await client.chat.completions.create(**request_params)
            return resp

        async def test_fc() -> Any:
            """测试当前 API 是否支持 Function Calling。"""
            test_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "test_function",
                        "description": "测试函数",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]
            try:
                return await call_api(
                    message="测试 Function Calling 支持",
                    tools_param=test_tools,
                    tool_choice_param="none",
                )
            except Exception as exc:  # pragma: no cover - 能力检测失败时的调试信息
                logger.debug("Function Calling 测试失败: %s", exc)
                raise

        # 优先尝试使用通用适配器（自动检测 + 降级），仅在提供 tools 时启用
        if self.enable_mcp_adapter and self.mcp_adapter and tools:
            try:
                api_identifier = f"{config.get('base_url') or 'openai'}::" f"{config.get('model') or ''}"

                last_user_message = ""
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        last_user_message = msg.get("content", "")
                        break

                adapter_result = await self.mcp_adapter.call_with_fallback(
                    api_identifier=api_identifier,
                    tools=tools,
                    user_message=last_user_message,
                    call_function=call_api,
                    test_function=test_fc,
                )

                if adapter_result.has_tool_calls:
                    return {
                        "tool_calls": adapter_result.tool_calls,
                        "content": adapter_result.raw_response,
                        "finish_reason": "tool_calls",
                    }
                return {
                    "content": adapter_result.raw_response,
                    "finish_reason": "stop",
                }

            except Exception as exc:
                logger.error(
                    "MCP 通用适配器调用失败，降级为原始工具调用: %s",
                    str(exc),
                )

        # 原始实现（无适配器或降级失败）
        try:
            request_params = {
                "model": config.get("model") or "gpt-3.5-turbo",
                "messages": messages,
                "temperature": temperature,
                "timeout": timeout,
            }
            if tools:
                request_params["tools"] = tools
                if tool_choice:
                    request_params["tool_choice"] = tool_choice

            response = await client.chat.completions.create(**request_params)

            choice = response.choices[0]
            message_obj = choice.message

            result = {
                "content": message_obj.content or "",
                "finish_reason": choice.finish_reason,
            }

            if message_obj.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message_obj.tool_calls
                ]

            logger.debug(
                "LLM 工具调用响应: model=%s user_id=%s tool_calls=%d",
                config.get("model"),
                user_id,
                len(result.get("tool_calls", [])),
            )

            return result

        except InternalServerError as exc:
            detail = "AI 服务内部错误，请稍后重试"
            response_obj = getattr(exc, "response", None)
            if response_obj is not None:
                try:
                    payload = response_obj.json()
                    error_data = payload.get("error", {}) if isinstance(payload, dict) else {}
                    detail = error_data.get("message_zh") or error_data.get("message") or detail
                except Exception:
                    detail = str(exc) or detail
            else:
                detail = str(exc) or detail
            logger.error(
                "LLM 工具调用内部错误: model=%s user_id=%s detail=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail)
        except (httpx.RemoteProtocolError, httpx.ReadTimeout, APIConnectionError, APITimeoutError) as exc:
            if isinstance(exc, httpx.RemoteProtocolError):
                detail = "AI 服务连接被意外中断，请稍后重试"
            elif isinstance(exc, (httpx.ReadTimeout, APITimeoutError)):
                detail = "AI 服务响应超时，请稍后重试"
            else:
                detail = "无法连接到 AI 服务，请稍后重试"
            logger.error(
                "LLM 工具调用失败: model=%s user_id=%s detail=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail) from exc

    async def _resolve_llm_config(self, user_id: Optional[int]) -> Dict[str, Optional[str]]:
        if user_id:
            config = await self.llm_repo.get_by_user(user_id)
            if config and config.llm_provider_api_key:
                return {
                    "api_key": config.llm_provider_api_key,
                    "base_url": config.llm_provider_url,
                    "model": config.llm_provider_model,
                }

        # 检查每日使用次数限制
        if user_id:
            await self._enforce_daily_limit(user_id)

        api_key = await self._get_config_value("llm.api_key")
        base_url = await self._get_config_value("llm.base_url")
        model = await self._get_config_value("llm.model")

        if not api_key:
            logger.error("未配置默认 LLM API Key，且用户 %s 未设置自定义 API Key", user_id)
            raise HTTPException(
                status_code=500,
                detail="未配置默认 LLM API Key，请联系管理员配置系统默认 API Key 或在个人设置中配置自定义 API Key"
            )

        return {"api_key": api_key, "base_url": base_url, "model": model}

    async def get_embedding(
        self,
        text: str,
        *,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
    ) -> List[float]:
        """生成文本向量，用于章节 RAG 检索，支持 openai 与 ollama 双提供方。"""
        provider = await self._get_config_value("embedding.provider") or "openai"
        default_model = (
            await self._get_config_value("ollama.embedding_model") or "nomic-embed-text:latest"
            if provider == "ollama"
            else await self._get_config_value("embedding.model") or "text-embedding-3-large"
        )
        target_model = model or default_model

        if provider == "ollama":
            if OllamaAsyncClient is None:
                logger.error("未安装 ollama 依赖，无法调用本地嵌入模型。")
                raise HTTPException(status_code=500, detail="缺少 Ollama 依赖，请先安装 ollama 包。")

            base_url = (
                await self._get_config_value("ollama.embedding_base_url")
                or await self._get_config_value("embedding.base_url")
            )
            client = OllamaAsyncClient(host=base_url)
            try:
                response = await client.embeddings(model=target_model, prompt=text)
            except Exception as exc:  # pragma: no cover - 本地服务调用失败
                logger.error(
                    "Ollama 嵌入请求失败: model=%s base_url=%s error=%s",
                    target_model,
                    base_url,
                    exc,
                    exc_info=True,
                )
                return []
            embedding: Optional[List[float]]
            if isinstance(response, dict):
                embedding = response.get("embedding")
            else:
                embedding = getattr(response, "embedding", None)
            if not embedding:
                logger.warning("Ollama 返回空向量: model=%s", target_model)
                return []
            if not isinstance(embedding, list):
                embedding = list(embedding)
        else:
            config = await self._resolve_llm_config(user_id)
            api_key = await self._get_config_value("embedding.api_key") or config["api_key"]
            base_url = await self._get_config_value("embedding.base_url") or config.get("base_url")
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            try:
                response = await client.embeddings.create(
                    input=text,
                    model=target_model,
                )
            except Exception as exc:  # pragma: no cover - 网络或鉴权失败
                logger.error(
                    "OpenAI 嵌入请求失败: model=%s base_url=%s user_id=%s error=%s",
                    target_model,
                    base_url,
                    user_id,
                    exc,
                    exc_info=True,
                )
                return []
            if not response.data:
                logger.warning("OpenAI 嵌入请求返回空数据: model=%s user_id=%s", target_model, user_id)
                return []
            embedding = response.data[0].embedding

        if not isinstance(embedding, list):
            embedding = list(embedding)

        dimension = len(embedding)
        if not dimension:
            vector_size_str = await self._get_config_value("embedding.model_vector_size")
            if vector_size_str:
                dimension = int(vector_size_str)
        if dimension:
            self._embedding_dimensions[target_model] = dimension
        return embedding

    async def get_embedding_dimension(self, model: Optional[str] = None) -> Optional[int]:
        """获取嵌入向量维度，优先返回缓存结果，其次读取配置。"""
        provider = await self._get_config_value("embedding.provider") or "openai"
        default_model = (
            await self._get_config_value("ollama.embedding_model") or "nomic-embed-text:latest"
            if provider == "ollama"
            else await self._get_config_value("embedding.model") or "text-embedding-3-large"
        )
        target_model = model or default_model
        if target_model in self._embedding_dimensions:
            return self._embedding_dimensions[target_model]
        vector_size_str = await self._get_config_value("embedding.model_vector_size")
        return int(vector_size_str) if vector_size_str else None

    async def _enforce_daily_limit(self, user_id: int) -> None:
        limit_str = await self.admin_setting_service.get("daily_request_limit", "100")
        limit = int(limit_str or 10)
        used = await self.user_repo.get_daily_request(user_id)
        if used >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日请求次数已达上限，请明日再试或设置自定义 API Key。",
            )
        await self.user_repo.increment_daily_request(user_id)
        await self.session.commit()

    async def _get_config_value(self, key: str) -> Optional[str]:
        record = await self.system_config_repo.get_by_key(key)
        if record:
            return record.value
        # 兼容环境变量，首次迁移时无需立即写入数据库
        env_key = key.upper().replace(".", "_")
        return os.getenv(env_key)
