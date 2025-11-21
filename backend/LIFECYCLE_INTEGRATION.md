# MCP 插件注册表生命周期集成

## 概述

本文档描述了 MCP 插件注册表与 FastAPI 应用生命周期的集成实现。

## 实现内容

### 1. 应用启动时初始化注册表 (main.py)

在 `backend/app/main.py` 的 `lifespan` 函数中：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时初始化数据库，并预热提示词缓存
    logger.info("正在初始化应用...")
    await init_db()
    async with AsyncSessionLocal() as session:
        prompt_service = PromptService(session)
        await prompt_service.preload()
    
    # 初始化 MCP 插件注册表
    logger.info("正在初始化 MCP 插件注册表...")
    mcp_registry = MCPPluginRegistry(
        max_clients=MCPConfig.MAX_CLIENTS,
        client_ttl=MCPConfig.CLIENT_TTL_SECONDS
    )
    app.state.mcp_registry = mcp_registry
    
    # 启动清理任务
    await mcp_registry.start_cleanup_task()
    logger.info("MCP 插件注册表已初始化并启动清理任务")
    
    yield
    
    # 应用关闭时清理资源
    logger.info("正在关闭应用...")
    await mcp_registry.shutdown()
    logger.info("应用已关闭")
```

**功能说明：**
- 在应用启动时创建 `MCPPluginRegistry` 实例
- 将注册表存储到 `app.state.mcp_registry`，使其在整个应用生命周期内可访问
- 启动后台清理任务，定期清理过期的插件会话
- 在应用关闭时调用 `shutdown()` 方法，优雅地关闭所有连接和清理资源

### 2. 依赖注入函数 (dependencies.py)

在 `backend/app/core/dependencies.py` 中添加：

```python
def get_mcp_registry(request: Request) -> MCPPluginRegistry:
    """获取 MCP 插件注册表实例。
    
    从应用状态中获取在启动时初始化的 MCP 插件注册表。
    
    Args:
        request: FastAPI 请求对象
        
    Returns:
        MCP 插件注册表实例
        
    Raises:
        HTTPException: 如果注册表未初始化
    """
    registry = getattr(request.app.state, "mcp_registry", None)
    if registry is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MCP 插件注册表未初始化"
        )
    return registry
```

**功能说明：**
- 提供标准的 FastAPI 依赖注入函数
- 从 `app.state` 中获取注册表实例
- 如果注册表未初始化，抛出 500 错误

### 3. API 路由集成 (mcp_plugins.py)

更新 `backend/app/api/routers/mcp_plugins.py` 中的服务依赖注入：

```python
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
```

**功能说明：**
- 使用 `get_mcp_registry` 依赖注入函数获取注册表
- 将注册表传递给需要它的服务（MCPToolService、MCPTestService）
- 确保所有 API 端点都能访问到同一个注册表实例

## 架构优势

1. **单例模式**：整个应用共享一个注册表实例，确保会话复用和资源管理的一致性
2. **生命周期管理**：注册表随应用启动而初始化，随应用关闭而清理
3. **依赖注入**：通过 FastAPI 的依赖注入系统，各个组件可以方便地访问注册表
4. **资源清理**：后台清理任务自动管理过期会话，应用关闭时优雅地释放所有资源
5. **错误处理**：如果注册表未初始化，依赖注入函数会抛出明确的错误

## 使用示例

在任何需要使用 MCP 注册表的 API 端点中：

```python
@router.get("/example")
async def example_endpoint(
    registry: MCPPluginRegistry = Depends(get_mcp_registry)
):
    # 使用注册表
    tools = await registry.list_tools(user_id, plugin_name, server_url)
    return {"tools": tools}
```

## 测试验证

所有现有的属性测试（59 个测试）都通过，验证了：
- 注册表的会话管理功能
- LRU 驱逐策略
- TTL 清理机制
- 工具服务的集成
- API 路由的正确性

## 相关需求

- **Requirements 8.1**: 系统启动时初始化 MCP Plugin Registry 并设置最大连接数限制
- **Requirements 8.5**: 系统执行定期清理任务关闭所有过期和异常的会话

## 下一步

注册表已完全集成到应用生命周期中，可以继续实现：
- Task 10: 集成到章节生成流程
- Task 11: 前端集成（可选）
- Task 12: 测试和验证
