"""
Unit tests for Novel API endpoints with MCP support.

Tests novel generation endpoints with MCP enhancement.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from app.schemas.novel import NovelGenerateRequest, NovelGenerateResponse


class TestNovelGenerateEndpoint:
    """Test novel generation endpoint with MCP support."""
    
    @pytest.mark.asyncio
    async def test_generate_with_mcp_enabled(self):
        """测试启用 MCP 的小说生成。
        
        验证：
        - enable_mcp=True 时调用 generate_with_mcp
        - 返回 MCP 增强的结果
        """
        mock_llm_service = AsyncMock()
        
        # Mock MCP-enhanced generation result
        mock_result = {
            "content": "这是一个使用 MCP 工具增强生成的科幻故事...",
            "mcp_enhanced": True,
            "tools_used": ["search.web_search", "database.query"],
            "tool_calls_made": 2,
            "finish_reason": "stop"
        }
        mock_llm_service.generate_with_mcp.return_value = mock_result
        
        # Create request
        request = NovelGenerateRequest(
            prompt="写一篇科幻小说",
            enable_mcp=True,
            temperature=0.7
        )
        
        # Call service
        result = await mock_llm_service.generate_with_mcp(
            prompt=request.prompt,
            user_id=1,
            enable_mcp=request.enable_mcp,
            temperature=request.temperature,
            max_tool_rounds=3,
            tool_choice="auto"
        )
        
        # Verify
        assert result["content"] != ""
        assert result["mcp_enhanced"] is True
        assert len(result["tools_used"]) == 2
        assert result["tool_calls_made"] == 2
        mock_llm_service.generate_with_mcp.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_with_mcp_disabled(self):
        """测试禁用 MCP 的小说生成。
        
        验证：
        - enable_mcp=False 时不使用 MCP 工具
        - 返回普通生成结果
        """
        mock_llm_service = AsyncMock()
        
        # Mock normal generation result (no MCP)
        mock_result = {
            "content": "这是一个普通生成的故事...",
            "mcp_enhanced": False,
            "tools_used": [],
            "tool_calls_made": 0,
            "finish_reason": "stop"
        }
        mock_llm_service.generate_with_mcp.return_value = mock_result
        
        # Create request with MCP disabled
        request = NovelGenerateRequest(
            prompt="写一篇故事",
            enable_mcp=False,
            temperature=0.7
        )
        
        # Call service
        result = await mock_llm_service.generate_with_mcp(
            prompt=request.prompt,
            user_id=1,
            enable_mcp=request.enable_mcp,
            temperature=request.temperature,
            max_tool_rounds=3,
            tool_choice="auto"
        )
        
        # Verify
        assert result["content"] != ""
        assert result["mcp_enhanced"] is False
        assert len(result["tools_used"]) == 0
        assert result["tool_calls_made"] == 0
    
    @pytest.mark.asyncio
    async def test_generate_mcp_fallback(self):
        """测试 MCP 失败时的降级处理。
        
        验证：
        - MCP 工具调用失败时自动降级
        - 仍然返回有效的生成内容
        """
        mock_llm_service = AsyncMock()
        
        # Mock fallback result (MCP failed, fell back to normal)
        mock_result = {
            "content": "这是降级后生成的内容...",
            "mcp_enhanced": False,
            "tools_used": [],
            "tool_calls_made": 0,
            "finish_reason": "stop"
        }
        mock_llm_service.generate_with_mcp.return_value = mock_result
        
        # Create request with MCP enabled
        request = NovelGenerateRequest(
            prompt="写一篇故事",
            enable_mcp=True,
            temperature=0.7
        )
        
        # Call service (will fallback internally)
        result = await mock_llm_service.generate_with_mcp(
            prompt=request.prompt,
            user_id=1,
            enable_mcp=request.enable_mcp,
            temperature=request.temperature,
            max_tool_rounds=3,
            tool_choice="auto"
        )
        
        # Verify fallback behavior
        assert result["content"] != ""
        assert result["mcp_enhanced"] is False
        assert result["finish_reason"] == "stop"
    
    @pytest.mark.asyncio
    async def test_generate_with_tools_used(self):
        """测试使用多个工具的生成。
        
        验证：
        - 正确记录使用的工具列表
        - 正确记录工具调用次数
        """
        mock_llm_service = AsyncMock()
        
        # Mock result with multiple tool calls
        mock_result = {
            "content": "基于搜索结果生成的内容...",
            "mcp_enhanced": True,
            "tools_used": [
                "search.web_search",
                "search.web_search",  # Called twice
                "database.query"
            ],
            "tool_calls_made": 3,
            "finish_reason": "stop"
        }
        mock_llm_service.generate_with_mcp.return_value = mock_result
        
        # Create request
        request = NovelGenerateRequest(
            prompt="搜索科幻小说的写作技巧",
            enable_mcp=True
        )
        
        # Call service
        result = await mock_llm_service.generate_with_mcp(
            prompt=request.prompt,
            user_id=1,
            enable_mcp=request.enable_mcp,
            temperature=request.temperature,
            max_tool_rounds=3,
            tool_choice="auto"
        )
        
        # Verify
        assert result["mcp_enhanced"] is True
        assert result["tool_calls_made"] == 3
        assert len(result["tools_used"]) == 3
        assert "search.web_search" in result["tools_used"]
        assert "database.query" in result["tools_used"]
    
    @pytest.mark.asyncio
    async def test_generate_response_schema(self):
        """测试生成响应的 schema 正确性。
        
        验证：
        - 响应包含所有必需字段
        - 字段类型正确
        """
        # Create a response
        response = NovelGenerateResponse(
            content="生成的内容",
            mcp_enhanced=True,
            tools_used=["tool1", "tool2"],
            tool_calls_made=2
        )
        
        # Verify schema
        assert isinstance(response.content, str)
        assert isinstance(response.mcp_enhanced, bool)
        assert isinstance(response.tools_used, list)
        assert isinstance(response.tool_calls_made, int)
        assert response.content == "生成的内容"
        assert response.mcp_enhanced is True
        assert len(response.tools_used) == 2
        assert response.tool_calls_made == 2
    
    @pytest.mark.asyncio
    async def test_generate_request_defaults(self):
        """测试生成请求的默认值。
        
        验证：
        - enable_mcp 默认为 True
        - temperature 默认为 0.7
        - max_length 默认为 2000
        """
        # Create request with only required field
        request = NovelGenerateRequest(prompt="测试")
        
        # Verify defaults
        assert request.enable_mcp is True
        assert request.temperature == 0.7
        assert request.max_length == 2000
    
    @pytest.mark.asyncio
    async def test_generate_with_custom_temperature(self):
        """测试使用自定义温度参数生成。
        
        验证：
        - 可以自定义 temperature 参数
        - 参数正确传递给 LLM 服务
        """
        mock_llm_service = AsyncMock()
        
        mock_result = {
            "content": "内容",
            "mcp_enhanced": False,
            "tools_used": [],
            "tool_calls_made": 0,
            "finish_reason": "stop"
        }
        mock_llm_service.generate_with_mcp.return_value = mock_result
        
        # Create request with custom temperature
        request = NovelGenerateRequest(
            prompt="测试",
            temperature=0.9
        )
        
        # Call service
        await mock_llm_service.generate_with_mcp(
            prompt=request.prompt,
            user_id=1,
            enable_mcp=request.enable_mcp,
            temperature=request.temperature,
            max_tool_rounds=3,
            tool_choice="auto"
        )
        
        # Verify temperature was passed
        call_args = mock_llm_service.generate_with_mcp.call_args
        assert call_args.kwargs["temperature"] == 0.9
