 # Implementation Plan

- [x] 1. 设置项目基础结构和依赖





- [x] 1.1 添加 MCP SDK 和相关依赖到 requirements.txt


  - 添加 `mcp>=0.1.0`（官方 MCP Python SDK）
  - 添加 `hypothesis>=6.0.0`（属性测试库）
  - 确保 `httpx>=0.24.0` 已安装
  - _Requirements: 所有需求_

- [x] 1.2 创建 MCP 模块目录结构


  - 创建 `backend/app/mcp/` 目录
  - 创建 `backend/app/mcp/__init__.py`
  - 创建 `backend/app/mcp/config.py`
  - 创建 `backend/app/mcp/http_client.py`
  - 创建 `backend/app/mcp/registry.py`
  - _Requirements: 所有需求_

- [x] 2. 实现数据模型和数据库迁移




- [x] 2.1 创建 MCPPlugin 数据模型


  - 在 `backend/app/models/mcp_plugin.py` 中定义 MCPPlugin 模型
  - 使用 SQLAlchemy 2.0 Mapped 类型注解
  - 包含所有必需字段（plugin_name, display_name, server_url 等）
  - 添加关系映射到 UserPluginPreference
  - _Requirements: 1.2_

- [x] 2.2 创建 UserPluginPreference 数据模型

  - 在同一文件中定义 UserPluginPreference 模型
  - 添加外键约束到 users 和 mcp_plugins 表
  - 添加唯一约束 (user_id, plugin_id)
  - 添加关系映射
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 2.3 更新 models/__init__.py


  - 导出 MCPPlugin 和 UserPluginPreference
  - 确保模型在 SQLAlchemy 元数据中注册
  - _Requirements: 1.2, 2.1_

- [x] 2.4 创建数据库迁移脚本


  - 创建 Alembic 迁移添加 mcp_plugins 表
  - 创建 Alembic 迁移添加 user_plugin_preferences 表
  - 添加必要的索引
  - 测试迁移的 upgrade 和 downgrade
  - _Requirements: 1.2, 2.1_

- [x] 3. 实现 Repository 层




- [x] 3.1 创建 MCPPluginRepository


  - 在 `backend/app/repositories/mcp_plugin_repository.py` 中实现
  - 继承 BaseRepository[MCPPlugin]
  - 实现 get_by_name() 方法
  - 实现 list_enabled() 方法
  - 实现 list_by_category() 方法
  - _Requirements: 1.1, 1.2, 1.5_

- [x] 3.2 创建 UserPluginPreferenceRepository


  - 在 `backend/app/repositories/user_plugin_preference_repository.py` 中实现
  - 继承 BaseRepository[UserPluginPreference]
  - 实现 get_user_preference() 方法
  - 实现 get_enabled_plugins() 方法（包含 JOIN 查询）
  - 实现 set_user_preference() 方法
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 4. 实现 MCP 核心层




- [x] 4.1 创建 MCP 配置类


  - 在 `backend/app/mcp/config.py` 中定义 MCPConfig
  - 使用 @dataclass(frozen=True) 定义配置常量
  - 包含连接池、缓存、重试、超时等配置
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 4.2 实现 HTTP MCP Client


  - 在 `backend/app/mcp/http_client.py` 中实现 HTTPMCPClient 类
  - 实现 connect() 方法使用 streamablehttp_client
  - 实现 disconnect() 方法清理资源
  - 实现 list_tools() 方法
  - 实现 call_tool() 方法
  - 实现 is_connected() 方法
  - 添加超时控制和错误处理
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 12.1_

- [x] 4.3 为 HTTP MCP Client 编写属性测试






  - **Property 21: Error State Recovery**
  - **Validates: Requirements 12.4**
  - 测试连接失败后的重连机制
  - 使用 Hypothesis 生成随机连接场景

- [x] 4.4 实现 MCP Plugin Registry


  - 在 `backend/app/mcp/registry.py` 中实现 MCPPluginRegistry 类
  - 实现 load_plugin() 方法
  - 实现 unload_plugin() 方法
  - 实现 get_client() 方法（带会话复用）
  - 实现 list_tools() 方法
  - 实现 call_tool() 方法
  - 实现 cleanup_expired_sessions() 方法
  - 实现 evict_lru_session() 方法
  - 实现 start_cleanup_task() 和 shutdown() 方法
  - 使用细粒度锁（per-user locks）
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 4.5 为 Plugin Registry 编写属性测试










  - **Property 13: Session Reuse**
  - **Validates: Requirements 8.2**
  - 测试会话复用逻辑
  - **Property 14: LRU Eviction**
  - **Validates: Requirements 8.3**
  - 测试 LRU 驱逐策略
  - **Property 15: Session TTL Cleanup**
  - **Validates: Requirements 8.4**
  - 测试 TTL 过期清理
- [x] 5. 实现 Pydantic Schemas







- [ ] 5. 实现 Pydantic Schemas

- [x] 5.1 创建 MCP Plugin Schemas







  - 在 `backend/app/schemas/mcp_plugin.py` 中定义所有 Schema
  - 实现 MCPPluginBase, MCPPluginCreate, MCPPluginUpdate
  - 实现 MCPPluginResponse（包含 user_enabled 字段）
  - 实现 ToolDefinition, ToolCallResult, ToolMetrics
  - 实现 PluginTestReport
  - 使用 Field 添加中文描述
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

- [x] 5.2 为 Schemas 编写属性测试






  - **Property 1: Plugin Configuration Round-Trip**
  - **Validates: Requirements 1.2**
  - 测试配置的序列化和反序列化
- [x] 6. 实现服务层




- [ ] 6. 实现服务层

- [x] 6.1 创建 MCPPluginService


  - 在 `backend/app/services/mcp_plugin_service.py` 中实现
  - 实现 create_plugin() 方法（带名称唯一性检查）
  - 实现 get_plugin() 方法
  - 实现 get_plugin_with_user_status() 方法
  - 实现 list_plugins_with_user_status() 方法
  - 实现 update_plugin() 方法
  - 实现 delete_plugin() 方法
  - 实现 toggle_user_plugin() 方法
  - 添加中文日志和错误消息
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4_

- [x] 6.2 为 MCPPluginService 编写属性测试


 



  - **Property 2: Enabled Plugins Are Loaded**
  - **Validates: Requirements 1.3**
  - **Property 3: Plugin Deletion Cleanup**
  - **Validates: Requirements 1.5**
  - **Property 4: User Tool Inclusion**
  - **Validates: Requirements 2.2**
  - **Property 5: User Tool Exclusion**
  - **Validates: Requirements 2.3**
  - **Property 18: Configuration Change Propagation**
  - **Validates: Requirements 2.4**

- [x] 6.3 创建 MCPToolService


  - 在 `backend/app/services/mcp_tool_service.py` 中实现
  - 实现 get_user_enabled_tools() 方法（带缓存）
  - 实现 execute_tool_calls() 方法（并行执行）
  - 实现 _execute_single_tool() 方法
  - 实现 _call_tool_with_retry() 方法（指数退避）
  - 实现 _convert_to_openai_format() 方法
  - 实现 get_metrics() 方法
  - 实现 clear_cache() 方法
  - 添加工具缓存逻辑（ToolCacheEntry）
  - 添加指标记录逻辑（ToolMetrics）
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 9.1, 9.2, 9.3, 9.4, 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 6.4 为 MCPToolService 编写属性测试






  - **Property 6: Tool Format Conversion**
  - **Validates: Requirements 4.2, 4.3**
  - **Property 7: Tool Cache Hit**
  - **Validates: Requirements 4.4, 11.3**
  - **Property 8: Tool Cache Expiration**
  - **Validates: Requirements 4.5, 11.4**
  - **Property 9: Tool Call Parsing**
  - **Validates: Requirements 6.1, 6.2**
  - **Property 10: Tool Call Retry**
  - **Validates: Requirements 6.4**
  - **Property 11: Tool Call Result Format**
  - **Validates: Requirements 6.6**
  - **Property 12: Parallel Tool Execution**
  - **Validates: Requirements 6.7**
  - **Property 16: Metrics Recording**
  - **Validates: Requirements 9.1, 9.2, 9.3**
  - **Property 17: Metrics Completeness**
  - **Validates: Requirements 9.4**
  - **Property 20: Cache Clear**
  - **Validates: Requirements 11.5**
  - **Property 22: Parameter Validation**
  - **Validates: Requirements 12.3**

- [x] 6.4 创建 MCPTestService


  - 在 `backend/app/services/mcp_test_service.py` 中实现
  - 实现 test_plugin() 方法
  - 测试连接建立
  - 获取工具列表
  - 选择工具并执行测试调用
  - 生成详细测试报告
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 7. 扩展 LLM Service




- [x] 7.1 在 LLMService 中添加 MCP 支持


  - 在 `backend/app/services/llm_service.py` 中添加 generate_text_with_mcp() 方法
  - 实现两轮 AI 调用逻辑（工具调用 + 最终生成）
  - 集成 MCPToolService
  - 实现降级策略（工具失败时继续生成）
  - 添加中文日志
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 7.2 为 LLM Service MCP 功能编写属性测试






  - **Property 19: Graceful Degradation**
  - **Validates: Requirements 5.5**
  - 测试工具失败时的降级行为

- [x] 8. 实现 API Router




- [x] 8.1 创建 MCP Plugins Router


  - 在 `backend/app/api/routers/mcp_plugins.py` 中实现
  - 实现 list_plugins() 端点
  - 实现 create_plugin() 端点（仅管理员）
  - 实现 get_plugin() 端点
  - 实现 update_plugin() 端点（仅管理员）
  - 实现 delete_plugin() 端点（仅管理员）
  - 实现 toggle_plugin() 端点
  - 实现 test_plugin() 端点（仅管理员）
  - 实现 get_plugin_tools() 端点
  - 实现 get_metrics() 端点（仅管理员）
  - 实现 clear_cache() 端点（仅管理员）
  - 使用现有的依赖注入（get_current_user, get_current_admin）
  - 添加中文日志
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

- [x] 8.2 为 API Router 编写属性测试






  - **Property 23: API Response Completeness**
  - **Validates: Requirements 13.1**
  - 测试 API 响应格式的完整性

- [x] 8.3 在主路由中注册 MCP Router


  - 在 `backend/app/api/routers/__init__.py` 中导入 mcp_plugins router
  - 将 router 添加到 api_router
  - _Requirements: 13.1_

- [x] 9. 集成到应用生命周期




- [x] 9.1 修改 main.py lifespan 函数


  - 在启动时初始化 MCPPluginRegistry
  - 将 registry 存储到 app.state.mcp_registry
  - 启动清理任务
  - 在关闭时调用 registry.shutdown()
  - 添加中文日志
  - _Requirements: 8.1, 8.5_

- [x] 9.2 创建依赖注入函数获取 registry


  - 在 `backend/app/core/dependencies.py` 中添加 get_mcp_registry()
  - 从 app.state 获取 registry 实例
  - _Requirements: 8.1_

- [x] 10. 集成到章节生成流程




- [x] 10.1 修改章节生成 API 使用 MCP 工具


  - 在 `backend/app/api/routers/writer.py` 中的章节生成端点
  - 调用 LLMService.generate_text_with_mcp() 而不是普通生成
  - 传递 user_id 以获取用户启用的工具
  - 处理工具调用结果
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 10.2 修改大纲生成流程使用 MCP 工具


  - 在大纲生成相关端点中集成 MCP 工具
  - 检查用户是否启用搜索类插件
  - 将搜索结果注入到提示词中
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 11. 前端集成（可选，根据需要）





- [x] 11.1 创建插件管理页面


  - 在 `frontend/src/views/` 中创建 PluginManagement.vue
  - 显示插件列表
  - 允许用户启用/禁用插件
  - 管理员可以添加/编辑/删除插件
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 2.1, 2.2, 2.3_

- [x] 11.2 创建插件 API 客户端


  - 在 `frontend/src/api/` 中创建 mcp.ts
  - 实现所有 MCP API 调用
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

- [x] 11.3 在设置页面添加插件管理入口


  - 在用户设置页面添加"MCP 插件"选项卡
  - 链接到插件管理页面
  - _Requirements: 2.1_

- [ ] 12. 测试和验证





- [x] 12.1 编写单元测试


  - 测试 Repository 层的 CRUD 操作
  - 测试 Service 层的业务逻辑
  - 测试 API 端点的请求/响应
  - 使用 pytest 和 pytest-asyncio
  - _Requirements: 所有需求_

- [x] 12.2 编写集成测试


  - 测试完整的章节生成流程（带 MCP）
  - 测试插件管理工作流
  - 测试多用户并发场景
  - 测试错误处理和降级
  - _Requirements: 所有需求_

- [x] 12.3 手动测试


  - 配置真实的 MCP 插件（如 Exa Search）
  - 测试插件连接和工具调用
  - 测试章节生成使用外部工具
  - 验证日志和指标记录
  - _Requirements: 所有需求_

- [x] 13. 文档和部署





- [x] 13.1 更新 README


  - 添加 MCP 插件系统说明
  - 添加配置示例
  - 添加常见问题解答
  - _Requirements: 所有需求_

- [x] 13.2 创建管理员指南


  - 如何添加和配置 MCP 插件
  - 如何监控插件性能
  - 如何排查问题
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 9.4, 9.5_

- [x] 13.3 更新部署文档


  - 添加新的依赖安装说明
  - 添加数据库迁移步骤
  - 添加环境变量配置（如果需要）
  - _Requirements: 所有需求_

- [x] 14. 最终检查点 - 确保所有测试通过





- 确保所有测试通过，如有问题请询问用户
