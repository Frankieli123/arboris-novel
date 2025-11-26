"""通用 MCP 适配器（UniversalMCPAdapter），从 MuMu 复用移植到 Arboris。"""

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base import BaseMCPAdapter, AdapterType, ToolCallResult
from .prompt_injection import PromptInjectionAdapter
from .function_calling import FunctionCallingAdapter

logger = logging.getLogger(__name__)


@dataclass
class APICapability:
    """API 能力检测结果"""

    supports_function_calling: bool
    tested_at: datetime
    test_duration_ms: float
    error_message: Optional[str] = None


class UniversalMCPAdapter:
    """通用 MCP 适配器管理器。

    功能：
    1. 自动检测 API 是否支持 Function Calling
    2. 缓存检测结果
    3. 自动降级：FC 失败时切换到提示词注入
    4. 提供统一调用接口
    """

    def __init__(
        self,
        cache_ttl_hours: int = 24,
        enable_auto_fallback: bool = True,
    ) -> None:
        # 适配器实例
        self.adapters = {
            AdapterType.FUNCTION_CALLING: FunctionCallingAdapter(),
            AdapterType.PROMPT_INJECTION: PromptInjectionAdapter(),
        }

        # API 能力缓存: {api_identifier: APICapability}
        self._capability_cache: Dict[str, APICapability] = {}
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._cache_lock = asyncio.Lock()

        self._enable_auto_fallback = enable_auto_fallback

        logger.info(
            "UniversalMCPAdapter 初始化完成 (缓存TTL=%s小时, 自动降级=%s)",
            cache_ttl_hours,
            "开启" if enable_auto_fallback else "关闭",
        )

    async def get_adapter(
        self,
        api_identifier: str,
        test_function: Optional[Callable[[], Any]] = None,
    ) -> BaseMCPAdapter:
        """根据能力检测结果返回合适的适配器。"""
        capability = await self._get_cached_capability(api_identifier)
        if capability is None and test_function is not None:
            capability = await self._detect_capability(api_identifier, test_function)

        if capability and capability.supports_function_calling:
            logger.info("使用函数调用适配器(Function Calling): %s", api_identifier)
            return self.adapters[AdapterType.FUNCTION_CALLING]

        logger.info("使用提示词注入适配器: %s", api_identifier)
        return self.adapters[AdapterType.PROMPT_INJECTION]

    async def _get_cached_capability(self, api_identifier: str) -> Optional[APICapability]:
        async with self._cache_lock:
            capability = self._capability_cache.get(api_identifier)
            if not capability:
                return None

            if datetime.now() - capability.tested_at > self._cache_ttl:
                logger.info("API 能力缓存过期: %s", api_identifier)
                del self._capability_cache[api_identifier]
                return None

            logger.debug("API 能力缓存命中: %s", api_identifier)
            return capability

    async def _detect_capability(
        self,
        api_identifier: str,
        test_function: Callable[[], Any],
    ) -> APICapability:
        logger.info("开始检测 API 能力: %s", api_identifier)
        start_time = time.time()

        try:
            result = await test_function()
            supports_fc = self._is_function_calling_response(result)
            duration_ms = (time.time() - start_time) * 1000

            capability = APICapability(
                supports_function_calling=supports_fc,
                tested_at=datetime.now(),
                test_duration_ms=duration_ms,
            )

            async with self._cache_lock:
                self._capability_cache[api_identifier] = capability

            logger.info(
                "%s函数调用(Function Calling): %s (耗时: %.2fms)",
                "支持" if supports_fc else "不支持",
                api_identifier,
                duration_ms,
            )

            return capability

        except Exception as exc:  # pragma: no cover - 防御兜底
            duration_ms = (time.time() - start_time) * 1000
            logger.warning(
                "API 能力检测失败: %s, 错误: %s, 将使用提示词注入模式",
                api_identifier,
                exc,
            )

            capability = APICapability(
                supports_function_calling=False,
                tested_at=datetime.now(),
                test_duration_ms=duration_ms,
                error_message=str(exc),
            )

            async with self._cache_lock:
                self._capability_cache[api_identifier] = capability

            return capability

    def _is_function_calling_response(self, response: Any) -> bool:
        """根据响应结构判断是否支持 Function Calling。"""
        try:
            if isinstance(response, dict):
                message = response.get("choices", [{}])[0].get("message", {})
                return "tool_calls" in message or "function_call" in message

            if hasattr(response, "choices"):
                message = response.choices[0].message
                return hasattr(message, "tool_calls") or hasattr(
                    message, "function_call"
                )

            return False
        except Exception:
            return False

    async def call_with_fallback(
        self,
        api_identifier: str,
        tools: List[Dict[str, Any]],
        user_message: str,
        call_function: Callable[..., Any],
        test_function: Optional[Callable[[], Any]] = None,
    ) -> ToolCallResult:
        """带自动降级策略的工具调用。"""
        adapter = await self.get_adapter(api_identifier, test_function)

        try:
            if adapter.supports_native_tools():
                logger.info("尝试使用函数调用模式(Function Calling)")
                result = await self._try_function_calling(
                    tools, user_message, call_function, adapter
                )
            else:
                logger.info("使用提示词注入模式")
                result = await self._try_prompt_injection(
                    tools, user_message, call_function, adapter  # type: ignore[arg-type]
                )

            return result

        except Exception as exc:
            logger.error("工具调用失败: %s", exc)

            if self._enable_auto_fallback and adapter.supports_native_tools():
                logger.warning("函数调用模式(Function Calling)失败，降级到提示词注入模式")
                async with self._cache_lock:
                    self._capability_cache[api_identifier] = APICapability(
                        supports_function_calling=False,
                        tested_at=datetime.now(),
                        test_duration_ms=0,
                        error_message=str(exc),
                    )

                fallback_adapter = self.adapters[AdapterType.PROMPT_INJECTION]
                return await self._try_prompt_injection(
                    tools,
                    user_message,
                    call_function,
                    fallback_adapter,  # type: ignore[arg-type]
                )

            raise

    async def _try_function_calling(
        self,
        tools: List[Dict[str, Any]],
        user_message: str,
        call_function: Callable[..., Any],
        adapter: FunctionCallingAdapter,
    ) -> ToolCallResult:
        response = await call_function(
            message=user_message,
            tools_param=tools,
            tool_choice_param="auto",
        )
        return adapter.parse_tool_calls(response)

    async def _try_prompt_injection(
        self,
        tools: List[Dict[str, Any]],
        user_message: str,
        call_function: Callable[..., Any],
        adapter: PromptInjectionAdapter,
    ) -> ToolCallResult:
        enhanced_prompt = adapter.format_tools_for_prompt(tools, user_message)
        response = await call_function(
            message=enhanced_prompt,
            tools_param=None,
            tool_choice_param=None,
        )
        return adapter.parse_tool_calls(response)

    def clear_cache(self, api_identifier: Optional[str] = None) -> None:
        """清理能力缓存。"""
        if api_identifier:
            if api_identifier in self._capability_cache:
                del self._capability_cache[api_identifier]
                logger.info("已清理 API 能力缓存: %s", api_identifier)
        else:
            self._capability_cache.clear()
            logger.info("已清理所有 API 能力缓存")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息。"""
        return {
            "total_cached": len(self._capability_cache),
            "cache_ttl_hours": self._cache_ttl.total_seconds() / 3600,
            "cached_apis": [
                {
                    "api_identifier": api_id,
                    "supports_fc": cap.supports_function_calling,
                    "tested_at": cap.tested_at.isoformat(),
                    "test_duration_ms": cap.test_duration_ms,
                }
                for api_id, cap in self._capability_cache.items()
            ],
        }
