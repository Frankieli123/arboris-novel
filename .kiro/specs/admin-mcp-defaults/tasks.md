# Implementation Plan

- [x] 1. 数据库迁移和模型调整




- [x] 1.1 修改 MCPPlugin 模型支持默认插件


  - 调整 `user_id` 字段为可空（nullable=True）
  - 更新唯一索引约束
  - _Requirements: 7.1, 7.2_

- [x] 1.2 创建数据库迁移脚本


  - 创建 SQLite 迁移脚本
  - 创建 PostgreSQL 迁移脚本（如果需要）
  - _Requirements: 7.1_

- [x] 1.3 编写数据模型属性测试



  - **Property 1: 默认插件全局唯一性**
  - **Validates: Requirements 1.3, 7.1**

- [x] 1.4 编写数据模型属性测试




  - **Property 2: 用户插件用户内唯一性**
  - **Validates: Requirements 5.3, 7.2**

- [x] 2. Repository 层扩展





- [x] 2.1 扩展 MCPPluginRepository


  - 实现 `get_default_plugins()` 方法
  - 实现 `get_user_plugins()` 方法
  - 实现 `get_all_available_plugins()` 方法
  - 实现 `create_default_plugin()` 方法
  - 实现 `create_user_plugin()` 方法
  - _Requirements: 1.3, 5.3, 7.1, 7.2, 7.3_

- [x] 2.2 扩展 UserPluginPreferenceRepository


  - 实现 `get_enabled_plugins()` 方法（考虑偏好设置）
  - 实现 `set_user_preference()` 方法
  - _Requirements: 5.4, 7.4_

- [x] 2.3 编写 Repository 单元测试


  - 测试 `get_default_plugins()`
  - 测试 `get_all_available_plugins()`
  - 测试 `get_enabled_plugins()`
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 2.4 编写 Repository 属性测试


  - **Property 3: 用户可用插件合并正确性**
  - **Validates: Requirements 7.3**

- [x] 2.5 编写 Repository 属性测试


  - **Property 10: 用户偏好查询正确性**
  - **Validates: Requirements 5.4**

- [x] 3. LLM Service MCP 集成





- [x] 3.1 在 LLMService 中添加 generate_with_mcp() 方法


  - 实现工具获取逻辑
  - 实现多轮工具调用循环
  - 实现降级处理
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 3.2 实现 _call_llm_with_tools() 辅助方法


  - 使用 OpenAI 客户端调用 AI
  - 处理工具调用响应
  - _Requirements: 9.2, 9.3_

- [x] 3.3 编写 LLM Service 单元测试


  - 测试没有工具时降级
  - 测试工具调用失败时降级
  - 测试多轮工具调用
  - _Requirements: 9.5_

- [x] 3.4 编写 LLM Service 属性测试


  - **Property 5: 工具调用降级一致性**
  - **Validates: Requirements 9.5**

- [x] 3.5 编写 LLM Service 属性测试


  - **Property 6: 工具列表格式正确性**
  - **Validates: Requirements 9.2**

- [x] 3.6 编写 LLM Service 属性测试


  - **Property 7: 多轮工具调用终止性**
  - **Validates: Requirements 9.3, 9.4**



- [x] 4. Service 层扩展



- [x] 4.1 扩展 MCPPluginService


  - 实现 `list_default_plugins()` 方法
  - 实现 `list_plugins_with_user_status()` 方法
  - 实现 `create_default_plugin()` 方法
  - 实现 `toggle_user_plugin()` 方法
  - _Requirements: 1.1, 1.2, 5.1, 5.4_

- [x] 4.2 编写 MCPPluginService 单元测试


  - 测试 `list_default_plugins()`
  - 测试 `list_plugins_with_user_status()`
  - 测试 `toggle_user_plugin()`
  - _Requirements: 1.1, 5.1, 5.4_
-

- [x] 5. API 层实现




- [x] 5.1 在 admin.py 中添加 MCP 管理端点


  - 实现 `GET /api/admin/mcp/plugins`（列出默认插件）
  - 实现 `POST /api/admin/mcp/plugins`（创建默认插件）
  - 实现 `PUT /api/admin/mcp/plugins/{id}`（更新默认插件）
  - 实现 `DELETE /api/admin/mcp/plugins/{id}`（删除默认插件）
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 5.2 在 novels.py 中添加 MCP 支持


  - 扩展 `NovelGenerateRequest` schema 添加 `enable_mcp` 字段
  - 修改生成端点调用 `generate_with_mcp()`
  - _Requirements: 10.1, 10.2, 10.3_

- [x] 5.3 编写 Admin API 单元测试


  - 测试只有管理员可以创建默认插件
  - 测试列出默认插件
  - 测试更新和删除默认插件
  - _Requirements: 1.1, 1.2, 1.4, 1.5_

- [x] 5.4 编写 Novel API 单元测试


  - 测试 enable_mcp 参数
  - 测试 MCP 增强生成
  - _Requirements: 10.1, 10.2_


- [x] 6. Frontend 实现




- [x] 6.1 在 SettingsManagement.vue 中添加 MCP 管理标签


  - 添加"MCP 插件"标签页
  - 实现默认插件列表展示
  - 实现插件创建/编辑模态框
  - 实现 JSON 配置输入和验证
  - _Requirements: 1.1, 1.2, 2.1, 3.1, 4.1_

- [x] 6.2 在 admin.ts 中添加 MCP API 调用


  - 实现 `listDefaultMCPPlugins()`
  - 实现 `createDefaultMCPPlugin()`
  - 实现 `updateDefaultMCPPlugin()`
  - 实现 `deleteDefaultMCPPlugin()`
  - _Requirements: 1.1, 1.2, 1.4, 1.5_

- [x] 6.3 调整 PluginManagement.vue 标识默认插件


  - 在插件列表中添加"默认"标签
  - 区分显示默认插件和用户插件
  - _Requirements: 5.2_

- [x] 6.4 在小说生成界面添加 enable_mcp 开关


  - 在生成表单中添加"使用 MCP 增强"开关
  - 默认启用 MCP
  - _Requirements: 10.1_
- [x] 7. Schema 和类型定义




- [ ] 7. Schema 和类型定义

- [x] 7.1 扩展 MCPPluginResponse schema

  - 添加 `is_default` 字段
  - 添加 `user_enabled` 字段
  - _Requirements: 5.2_

- [x] 7.2 创建 NovelGenerateRequest schema

  - 添加 `enable_mcp` 字段
  - _Requirements: 10.1_

- [x] 7.3 编写 Schema 属性测试


  - **Property 8: JSON 配置验证正确性**
  - **Validates: Requirements 3.2, 3.3, 4.2**

- [x] 7.4 编写 Schema 属性测试


  - **Property 9: 插件分类一致性**
  - **Validates: Requirements 2.5**

- [x] 8. 错误处理和日志





- [x] 8.1 实现 MCP 工具调用失败降级


  - 在 LLMService 中添加异常捕获
  - 记录错误日志
  - 返回降级标志
  - _Requirements: 9.5, 10.4_

- [x] 8.2 实现 JSON 配置验证


  - 前端验证 JSON 格式
  - 后端验证 JSON 格式
  - 返回友好的错误信息
  - _Requirements: 3.2, 3.3, 4.2_

- [x] 8.3 实现插件名称冲突处理


  - 捕获数据库唯一约束错误
  - 返回 409 Conflict 错误
  - _Requirements: 1.3_
-

- [x] 9. 集成测试



- [x] 9.1 编写端到端集成测试


  - 测试完整的 MCP 生成流程
  - 测试管理员配置默认插件流程
  - 测试用户启用/禁用插件流程
  - _Requirements: 1.1, 5.4, 9.1, 10.2_

- [ ] 10. 文档和部署
- [ ] 10.1 更新 API 文档
  - 添加管理员 MCP 端点文档
  - 添加小说生成 MCP 参数文档
  - _Requirements: 1.1, 10.1_

- [ ] 10.2 更新用户文档
  - 更新 MCP_ADMIN_GUIDE.md
  - 添加默认插件配置说明
  - 添加 MCP 增强生成说明
  - _Requirements: 1.1, 10.1_

- [ ] 10.3 更新部署指南
  - 添加数据库迁移步骤
  - 添加 MCP 配置说明
  - _Requirements: 1.1_
-

- [x] 11. Checkpoint - 确保所有测试通过




- Ensure all tests pass, ask the user if questions arise.
