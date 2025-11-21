import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin, get_current_user, get_mcp_registry
from ...db.session import get_session
from ...mcp.registry import MCPPluginRegistry
from ...schemas.mcp_plugin import (
    MCPPluginCreate,
    MCPPluginResponse,
    MCPPluginUpdate,
    PluginTestReport,
    ToolDefinition,
)
from ...schemas.user import UserInDB
from ...services.mcp_plugin_service import MCPPluginService
from ...services.mcp_test_service import MCPTestService
from ...services.mcp_tool_service import MCPToolService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["MCP Plugins"])


def get_mcp_plugin_service(session: AsyncSession = Depends(get_session)) -> MCPPluginService:
    """获取 MCP 插件服务实例。"""
    return MCPPluginService(session)


def get_mcp_tool_service(
    session: AsyncSession = Depends(get_session),
    registry: MCPPluginRegistry = Depends(get_mcp_registry)
) -> MCPToolService:
    """获取 MCP 工具服务实例。"""
    return MCPToolService(session, registry)


def get_mcp_test_service(
    session: AsyncSession = Depends(get_session),
    registry: MCPPluginRegistry = Depends(get_mcp_registry)
) -> MCPTestService:
    """获取 MCP 测试服务实例。"""
    return MCPTestService(session, registry)


@router.get("/plugins", response_model=List[MCPPluginResponse])
async def list_plugins(
    current_user: UserInDB = Depends(get_current_user),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> List[MCPPluginResponse]:
    """列出所有可用的 MCP 插件及用户的启用状态。"""
    plugins = await plugin_service.list_plugins_with_user_status(current_user.id)
    logger.info("用户 %s 查询插件列表，共 %d 个", current_user.id, len(plugins))
    return plugins


@router.post("/plugins", response_model=MCPPluginResponse, status_code=status.HTTP_201_CREATED)
async def create_plugin(
    plugin_data: MCPPluginCreate,
    current_user: UserInDB = Depends(get_current_admin),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> MCPPluginResponse:
    """创建新的 MCP 插件配置（仅管理员）。"""
    plugin = await plugin_service.create_plugin(plugin_data)
    logger.info("管理员 %s 创建插件: %s", current_user.username, plugin.plugin_name)
    result = await plugin_service.get_plugin_with_user_status(plugin.id, current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="插件创建后无法获取"
        )
    return result


@router.get("/plugins/{plugin_id}", response_model=MCPPluginResponse)
async def get_plugin(
    plugin_id: int,
    current_user: UserInDB = Depends(get_current_user),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> MCPPluginResponse:
    """获取插件详情。"""
    plugin = await plugin_service.get_plugin_with_user_status(plugin_id, current_user.id)
    if not plugin:
        logger.warning("用户 %s 查询不存在的插件 %d", current_user.id, plugin_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="插件不存在")
    logger.info("用户 %s 查询插件 %d", current_user.id, plugin_id)
    return plugin


@router.put("/plugins/{plugin_id}", response_model=MCPPluginResponse)
async def update_plugin(
    plugin_id: int,
    plugin_data: MCPPluginUpdate,
    current_user: UserInDB = Depends(get_current_admin),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> MCPPluginResponse:
    """更新插件配置（仅管理员）。"""
    plugin = await plugin_service.update_plugin(plugin_id, plugin_data)
    logger.info("管理员 %s 更新插件 %d", current_user.username, plugin_id)
    result = await plugin_service.get_plugin_with_user_status(plugin.id, current_user.id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="插件更新后无法获取"
        )
    return result


@router.delete("/plugins/{plugin_id}", status_code=status.HTTP_200_OK)
async def delete_plugin(
    plugin_id: int,
    current_user: UserInDB = Depends(get_current_admin),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> Dict[str, str]:
    """删除插件（仅管理员）。"""
    await plugin_service.delete_plugin(plugin_id)
    logger.info("管理员 %s 删除插件 %d", current_user.username, plugin_id)
    return {"status": "success", "message": "插件已删除"}


@router.post("/plugins/{plugin_id}/toggle", response_model=Dict[str, bool])
async def toggle_plugin(
    plugin_id: int,
    enabled: bool = Body(..., embed=True),
    current_user: UserInDB = Depends(get_current_user),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> Dict[str, bool]:
    """切换用户的插件启用状态。"""
    new_status = await plugin_service.toggle_user_plugin(current_user.id, plugin_id, enabled)
    logger.info("用户 %s %s插件 %d", current_user.username, "启用" if new_status else "禁用", plugin_id)
    return {"enabled": new_status}


@router.post("/plugins/{plugin_id}/test", response_model=PluginTestReport)
async def test_plugin(
    plugin_id: int,
    current_user: UserInDB = Depends(get_current_admin),
    test_service: MCPTestService = Depends(get_mcp_test_service),
) -> PluginTestReport:
    """测试插件连接和功能（仅管理员）。"""
    report = await test_service.test_plugin(current_user.id, plugin_id)
    logger.info("管理员 %s 测试插件 %d，结果: %s", current_user.username, plugin_id, report.success)
    return report


@router.get("/plugins/{plugin_id}/tools", response_model=List[ToolDefinition])
async def get_plugin_tools(
    plugin_id: int,
    current_user: UserInDB = Depends(get_current_user),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
    tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> List[ToolDefinition]:
    """获取插件提供的工具列表。"""
    # First verify the plugin exists
    plugin = await plugin_service.get_plugin(plugin_id)
    if not plugin:
        logger.warning("用户 %s 查询不存在的插件 %d 的工具", current_user.id, plugin_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="插件不存在")
    
    # Get tools from the plugin
    try:
        tools = await tool_service.get_plugin_tools(current_user.id, plugin.plugin_name)
        logger.info("用户 %s 查询插件 %d 的工具，共 %d 个", current_user.id, plugin_id, len(tools))
        return tools
    except Exception as exc:
        logger.error("获取插件 %d 工具失败: %s", plugin_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取插件工具失败: {str(exc)}"
        )


@router.get("/metrics", response_model=Dict)
async def get_metrics(
    tool_name: Optional[str] = None,
    current_user: UserInDB = Depends(get_current_admin),
    tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> Dict:
    """获取工具调用指标（仅管理员）。"""
    metrics = tool_service.get_metrics(tool_name)
    logger.info("管理员 %s 查询工具指标: %s", current_user.username, tool_name or "全部")
    return metrics


@router.post("/cache/clear", status_code=status.HTTP_200_OK)
async def clear_cache(
    current_user: UserInDB = Depends(get_current_admin),
    tool_service: MCPToolService = Depends(get_mcp_tool_service),
) -> Dict[str, str]:
    """清空工具定义缓存（仅管理员）。"""
    tool_service.clear_cache()
    logger.info("管理员 %s 清空工具缓存", current_user.username)
    return {"status": "success", "message": "缓存已清空"}


@router.post("/plugins/import", response_model=Dict, status_code=status.HTTP_200_OK)
async def import_plugins_from_json(
    mcp_config: Dict = Body(...),
    current_user: UserInDB = Depends(get_current_admin),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> Dict:
    """从 MCP 配置 JSON 批量导入插件（仅管理员）。
    
    支持标准的 MCP 配置格式：
    {
        "mcpServers": {
            "plugin-name": {
                "type": "http",
                "url": "https://...",
                "headers": {...}
            }
        }
    }
    """
    if "mcpServers" not in mcp_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="配置格式错误：缺少 'mcpServers' 字段"
        )
    
    mcp_servers = mcp_config["mcpServers"]
    if not isinstance(mcp_servers, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="配置格式错误：'mcpServers' 必须是对象"
        )
    
    created = []
    skipped = []
    errors = []
    
    for plugin_name, config in mcp_servers.items():
        try:
            # 解析配置
            plugin_type = config.get("type", "http")
            server_url = config.get("url")
            headers = config.get("headers")
            category = config.get("category")
            
            if not server_url:
                errors.append(f"{plugin_name}: 缺少 'url' 字段")
                continue
            
            # 检查插件是否已存在（只检查默认插件）
            existing = await plugin_service.plugin_repo.get_by_name(plugin_name)
            if existing and existing.user_id is None:
                skipped.append(plugin_name)
                continue
            
            # 创建插件
            plugin_data = MCPPluginCreate(
                plugin_name=plugin_name,
                display_name=config.get("display_name", plugin_name),
                plugin_type=plugin_type,
                server_url=server_url,
                headers=headers,
                enabled=config.get("enabled", True),
                category=category,
                config=config.get("config")
            )
            
            plugin = await plugin_service.create_default_plugin(plugin_data)
            created.append(plugin.plugin_name)
            
        except Exception as e:
            errors.append(f"{plugin_name}: {str(e)}")
            logger.error("导入插件 %s 失败: %s", plugin_name, e)
    
    logger.info(
        "管理员 %s 导入插件: 成功 %d, 跳过 %d, 失败 %d",
        current_user.username,
        len(created),
        len(skipped),
        len(errors)
    )
    
    return {
        "status": "success",
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "summary": f"成功导入 {len(created)} 个插件，跳过 {len(skipped)} 个已存在的插件，{len(errors)} 个失败"
    }
