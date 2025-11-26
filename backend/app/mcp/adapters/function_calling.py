"""Function Calling 适配器（从 MuMu 复用，移植到 Arboris）"""

import json
import logging
from typing import Dict, Any, List

from .base import BaseMCPAdapter, AdapterType, ToolCallResult

logger = logging.getLogger(__name__)


class FunctionCallingAdapter(BaseMCPAdapter):
    """用于支持原生工具调用的 AI API（如 OpenAI）"""

    def __init__(self) -> None:
        super().__init__()
        self.adapter_type = AdapterType.FUNCTION_CALLING

    def supports_native_tools(self) -> bool:
        """支持原生工具调用。"""
        return True

    def format_tools_for_prompt(
        self,
        tools: List[Dict[str, Any]],
        user_message: str,
    ) -> str:
        """Function Calling 模式下不需要修改提示词，直接返回用户消息。"""
        return user_message

    def get_tools_for_api(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """返回适用于 API 的工具格式（OpenAI 直接使用 MCP 工具定义）。"""
        return tools

    def parse_tool_calls(self, ai_response: Any) -> ToolCallResult:
        """从 AI 响应中解析工具调用（Function Calling 格式）。"""
        try:
            # 字典格式（HTTP 返回 JSON）
            if isinstance(ai_response, dict):
                message = ai_response.get("choices", [{}])[0].get("message", {})
                tool_calls = message.get("tool_calls", [])
                content = message.get("content", "")

            # 对象格式（OpenAI SDK 返回对象）
            elif hasattr(ai_response, "choices"):
                message = ai_response.choices[0].message
                tool_calls = getattr(message, "tool_calls", None) or []
                content = getattr(message, "content", "") or ""

                # 转为字典，方便后续统一处理
                if tool_calls:
                    tool_calls = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ]
            else:
                # 其他类型（纯文本等）一律视为无工具调用
                return ToolCallResult(
                    tool_calls=[],
                    raw_response=str(ai_response),
                    has_tool_calls=False,
                )

            has_tool_calls = len(tool_calls) > 0
            if has_tool_calls:
                logger.info("✅ 函数调用模式(Function Calling)解析出 %d 个工具调用", len(tool_calls))
                for tc in tool_calls:
                    logger.info("  - %s", tc["function"]["name"])

            return ToolCallResult(
                tool_calls=tool_calls,
                raw_response=content or "",
                has_tool_calls=has_tool_calls,
                needs_continuation=has_tool_calls,
            )

        except Exception as exc:  # pragma: no cover - 防御性兜底
            logger.error("解析函数调用(Function Calling)响应失败: %s", exc, exc_info=True)
            return ToolCallResult(
                tool_calls=[],
                raw_response=str(ai_response),
                has_tool_calls=False,
            )

    def build_continuation_prompt(
        self,
        original_message: str,
        ai_response: str,
        tool_results: List[Dict[str, Any]],
    ) -> str:
        """构建包含工具结果的继续对话提示词（降级兜底用）。"""
        results_text = "\n\n".join(
            [f"工具 {r['name']} 的结果:\n{r['content']}" for r in tool_results]
        )
        return (
            f"{original_message}\n\n工具执行结果:\n{results_text}\n\n"
            f"请基于以上工具结果回答用户的问题。"
        )

    def build_messages_with_tool_results(
        self,
        messages: List[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """构建包含工具结果的消息历史（Function Calling 标准格式）。"""
        new_messages = list(messages)

        # 助手的工具调用消息
        new_messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        })

        # 工具结果消息
        for result in tool_results:
            new_messages.append({
                "role": "tool",
                "tool_call_id": result.get("tool_call_id", ""),
                "name": result.get("name", ""),
                "content": result.get("content", ""),
            })

        return new_messages
