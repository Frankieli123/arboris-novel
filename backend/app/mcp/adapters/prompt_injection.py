"""提示词注入适配器（从 MuMu 复用，移植到 Arboris）"""

import re
import json
import logging
from typing import Dict, Any, List

from .base import BaseMCPAdapter, AdapterType, ToolCallResult

logger = logging.getLogger(__name__)


class PromptInjectionAdapter(BaseMCPAdapter):
    """将 MCP 工具转换为文本描述，通过提示词引导 AI 调用。"""

    def __init__(self) -> None:
        super().__init__()
        self.adapter_type = AdapterType.PROMPT_INJECTION

    def format_tools_for_prompt(
        self,
        tools: List[Dict[str, Any]],
        user_message: str,
    ) -> str:
        """将工具列表注入到提示词中。"""
        if not tools:
            return user_message

        tool_descriptions = self._format_tools_as_text(tools)
        enhanced_prompt = f"""你现在可以使用以下工具来帮助回答用户的问题。

## 可用工具

{tool_descriptions}

## 工具使用说明

当你需要使用工具时，请按以下XML格式输出（可以一次调用多个工具）：

<tool_calls>
<tool_call>
<tool_name>工具名称</tool_name>
<arguments>
{{
  "参数名1": "参数值1",
  "参数名2": "参数值2"
}}
</arguments>
</tool_call>
</tool_calls>

## 重要提示

1. 只有在确实需要使用工具时才调用工具
2. 参数必须是有效的JSON格式
3. 仔细检查参数是否符合工具的要求
4. 可以在一个<tool_calls>标签内包含多个<tool_call>
5. 调用工具后，你会收到工具的执行结果，然后需要基于结果继续回答

---

用户问题：{user_message}

请分析问题，判断是否需要使用工具。如果需要，先输出工具调用，然后等待结果。如果不需要，直接回答问题。"""
        return enhanced_prompt

    def _format_tools_as_text(self, tools: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for i, tool in enumerate(tools, 1):
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            description = func.get("description", "无描述")
            parameters = func.get("parameters", {})

            lines.append(f"### {i}. {name}")
            lines.append(f"**描述**: {description}")
            lines.append("")

            if parameters and "properties" in parameters:
                lines.append("**参数**:")
                properties = parameters.get("properties", {})
                required = parameters.get("required", [])
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "string")
                    param_desc = param_info.get("description", "")
                    is_required = "必填" if param_name in required else "可选"
                    lines.append(
                        f"  - `{param_name}` ({param_type}, {is_required}): {param_desc}"
                    )
                lines.append("")

            if "example" in func:
                lines.append(
                    f"**示例**: {json.dumps(func['example'], ensure_ascii=False)}"
                )
                lines.append("")

        return "\n".join(lines)

    def parse_tool_calls(self, ai_response: Any) -> ToolCallResult:
        """从 AI 响应中解析 XML 格式的工具调用。"""
        tool_calls: List[Dict[str, Any]] = []

        try:
            # 如果是 dict，尝试取出 content
            if isinstance(ai_response, dict):
                ai_response = (
                    ai_response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                if not ai_response:
                    return ToolCallResult(
                        tool_calls=[],
                        raw_response="",
                        has_tool_calls=False,
                    )
            elif not isinstance(ai_response, str):
                ai_response = str(ai_response)

            # 提取 <tool_calls> ... </tool_calls>
            tool_calls_match = re.search(
                r"<tool_calls>(.*?)</tool_calls>",
                ai_response,
                re.DOTALL | re.IGNORECASE,
            )
            if not tool_calls_match:
                return ToolCallResult(
                    tool_calls=[],
                    raw_response=ai_response,
                    has_tool_calls=False,
                )

            tool_calls_content = tool_calls_match.group(1)
            tool_call_pattern = r"<tool_call>(.*?)</tool_call>"
            tool_call_matches = re.findall(
                tool_call_pattern,
                tool_calls_content,
                re.DOTALL | re.IGNORECASE,
            )

            for i, tool_call_content in enumerate(tool_call_matches):
                name_match = re.search(
                    r"<tool_name>(.*?)</tool_name>",
                    tool_call_content,
                    re.DOTALL | re.IGNORECASE,
                )
                args_match = re.search(
                    r"<arguments>(.*?)</arguments>",
                    tool_call_content,
                    re.DOTALL | re.IGNORECASE,
                )
                if name_match and args_match:
                    tool_name = name_match.group(1).strip()
                    arguments_str = args_match.group(1).strip()
                    try:
                        arguments = json.loads(arguments_str)
                        tool_calls.append(
                            {
                                "id": f"call_{i}",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(
                                        arguments, ensure_ascii=False
                                    ),
                                },
                            }
                        )
                        logger.info("解析工具调用成功: %s", tool_name)
                    except json.JSONDecodeError as exc:
                        logger.error("解析工具参数失败: %s", arguments_str, exc_info=exc)
                        continue

            has_tool_calls = len(tool_calls) > 0
            if has_tool_calls:
                logger.info("从响应中解析出 %d 个工具调用", len(tool_calls))

            return ToolCallResult(
                tool_calls=tool_calls,
                raw_response=ai_response,
                has_tool_calls=has_tool_calls,
                needs_continuation=has_tool_calls,
            )

        except Exception as exc:  # pragma: no cover - 防御兜底
            logger.error("解析工具调用失败: %s", exc, exc_info=True)
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
        """构建包含工具结果的继续对话提示词。"""
        results_text = self._format_tool_results(tool_results)
        continuation = f"""你之前尝试使用工具来回答用户的问题。

原始问题：{original_message}

你的工具调用：
{self._extract_tool_calls_text(ai_response)}

工具执行结果：
{results_text}

现在，请基于这些工具的执行结果，给出完整、详细的回答。不要重复调用工具，直接使用已有的结果来回答用户的问题。"""
        return continuation

    def _format_tool_results(self, tool_results: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for i, result in enumerate(tool_results, 1):
            tool_name = result.get("name", "unknown")
            success = result.get("success", False)
            content = result.get("content", "")
            status = "✅ 成功" if success else "❌ 失败"
            lines.append(f"{i}. {tool_name} - {status}")

            if success:
                try:
                    if isinstance(content, str):
                        content_obj = json.loads(content)
                        content = json.dumps(content_obj, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                lines.append(f"```\n{content}\n```")
            else:
                error = result.get("error", "未知错误")
                lines.append(f"错误信息: {error}")

            lines.append("")

        return "\n".join(lines)

    def _extract_tool_calls_text(self, ai_response: str) -> str:
        match = re.search(
            r"<tool_calls>(.*?)</tool_calls>",
            ai_response,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            return match.group(0)
        return "（未找到工具调用）"
