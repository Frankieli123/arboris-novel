# Requirements Document

## Introduction

本规范定义了 MCP 插件系统的完整实现，包括两个核心部分：

1. **MCP 调用功能**：在 LLM 服务中集成 MCP 工具，使 AI 能够调用外部工具来增强生成能力
2. **默认插件管理**：在管理员设置中添加默认 MCP 插件配置，允许管理员为所有用户配置默认插件

**当前状态**：
- ✅ MCP 插件的配置功能已完成（用户可以添加和管理插件）
- ❌ MCP 插件的调用功能未实现（配置了也用不了）
- ❌ 管理员默认插件功能未实现

**目标**：
- 让 MCP 插件能够真正被 AI 调用，增强生成能力
- 完善管理功能，支持默认插件配置

## Glossary

- **MCP (Model Context Protocol)**: 模型上下文协议，用于扩展 AI 系统功能的插件协议
- **Admin Settings**: 管理员设置，仅管理员可访问的系统配置界面
- **Default Plugin**: 默认插件，管理员配置的对所有用户生效的插件
- **User Plugin**: 用户插件，用户在主页设置中自定义的插件
- **Plugin Category**: 插件分类，用于组织和管理不同类型的插件（如 search、filesystem、database 等）
- **JSON Configuration**: JSON 配置，使用 JSON 格式存储插件的详细配置信息
- **Plugin Registry**: 插件注册表，管理所有可用插件的系统组件

## Requirements

### Requirement 1

**User Story:** 作为管理员，我希望在管理员设置中配置默认 MCP 插件，以便为所有用户提供统一的基础功能。

#### Acceptance Criteria

1. WHEN 管理员访问管理员设置页面 THEN 系统应显示"默认 MCP 插件"配置区域
2. WHEN 管理员在默认插件配置区域点击"添加插件" THEN 系统应显示插件创建表单
3. WHEN 管理员填写插件信息并保存 THEN 系统应将插件保存为默认插件并对所有用户生效
4. WHEN 管理员编辑默认插件配置 THEN 系统应更新插件配置并立即对所有用户生效
5. WHEN 管理员删除默认插件 THEN 系统应移除该插件并停止对所有用户提供该功能

### Requirement 2

**User Story:** 作为管理员，我希望为 MCP 插件设置分类，以便更好地组织和管理不同类型的插件。

#### Acceptance Criteria

1. WHEN 管理员创建或编辑插件 THEN 系统应提供分类选择字段
2. WHEN 管理员选择插件分类 THEN 系统应将分类信息保存到插件配置中
3. WHEN 系统显示插件列表 THEN 系统应按分类对插件进行分组显示
4. WHEN 用户查看可用插件 THEN 系统应显示每个插件的分类标签
5. WHEN 管理员未指定分类 THEN 系统应将插件归类为"general"默认分类

### Requirement 3

**User Story:** 作为管理员，我希望使用 JSON 格式配置插件的详细参数，以便灵活地设置复杂的插件配置。

#### Acceptance Criteria

1. WHEN 管理员创建或编辑插件 THEN 系统应提供 JSON 格式的配置输入区域
2. WHEN 管理员输入 JSON 配置 THEN 系统应验证 JSON 格式的正确性
3. WHEN JSON 格式无效 THEN 系统应显示错误提示并阻止保存
4. WHEN JSON 格式有效 THEN 系统应将配置保存到插件的 config 字段
5. WHEN 系统使用插件 THEN 系统应读取 JSON 配置并应用到插件运行时

### Requirement 4

**User Story:** 作为管理员，我希望为插件配置认证请求头，以便插件能够访问需要身份验证的外部服务。

#### Acceptance Criteria

1. WHEN 管理员创建或编辑插件 THEN 系统应提供认证请求头的 JSON 输入区域
2. WHEN 管理员输入请求头 JSON THEN 系统应验证 JSON 格式的正确性
3. WHEN 请求头 JSON 格式有效 THEN 系统应将请求头保存到插件的 headers 字段
4. WHEN 插件发起 HTTP 请求 THEN 系统应在请求中包含配置的认证请求头
5. WHEN 管理员未配置请求头 THEN 系统应允许插件在无认证的情况下运行

### Requirement 5

**User Story:** 作为用户，我希望在主页设置中查看和管理我的 MCP 插件，以便自定义我的工作环境。

#### Acceptance Criteria

1. WHEN 用户访问主页设置的 MCP 插件区域 THEN 系统应显示默认插件和用户自定义插件
2. WHEN 用户查看插件列表 THEN 系统应标识哪些是默认插件，哪些是用户自定义插件
3. WHEN 用户添加自定义插件 THEN 系统应将插件仅关联到该用户，不影响其他用户
4. WHEN 用户启用或禁用默认插件 THEN 系统应仅对该用户生效，不改变默认设置
5. WHEN 用户删除自定义插件 THEN 系统应仅删除该用户的插件，不影响默认插件

### Requirement 6

**User Story:** 作为管理员，我希望测试 MCP 插件的连接和功能，以便确保插件配置正确且可用。

#### Acceptance Criteria

1. WHEN 管理员在插件列表中点击"测试"按钮 THEN 系统应发起插件连接测试
2. WHEN 插件测试成功 THEN 系统应显示成功消息和可用工具数量
3. WHEN 插件测试失败 THEN 系统应显示错误信息和建议的解决方案
4. WHEN 测试完成 THEN 系统应记录测试时间和结果
5. WHEN 管理员查看插件详情 THEN 系统应显示最后测试时间和状态

### Requirement 7

**User Story:** 作为开发者，我希望系统正确区分默认插件和用户插件，以便两者互不干扰且能够共存。

#### Acceptance Criteria

1. WHEN 管理员创建默认插件 THEN 系统应在数据库中使用特殊标识（如 user_id 为 NULL 或 "system"）标记为全局默认插件
2. WHEN 用户创建自定义插件 THEN 系统应将插件关联到该用户的 user_id
3. WHEN 查询用户可用插件 THEN 系统应返回默认插件和该用户的自定义插件的合并列表
4. WHEN 用户修改默认插件的启用状态 THEN 系统应在用户偏好表中记录该设置，不修改默认插件本身
5. WHEN 删除默认插件 THEN 系统应同时清理所有用户对该插件的偏好设置

### Requirement 8

**User Story:** 作为系统架构师，我希望保持现有 MCP 插件系统的架构，以便新功能能够无缝集成到现有代码中。

#### Acceptance Criteria

1. WHEN 实现默认插件功能 THEN 系统应复用现有的 MCPPlugin 模型和 schema
2. WHEN 添加管理员设置界面 THEN 系统应复用现有的插件管理组件
3. WHEN 处理插件请求 THEN 系统应使用现有的 MCPPluginService 和 MCPPluginRegistry
4. WHEN 存储插件配置 THEN 系统应使用现有的数据库表结构
5. WHEN 用户访问插件 THEN 系统应通过现有的 API 路由提供服务

### Requirement 9 (核心功能)

**User Story:** 作为开发者，我希望在 LLM 服务中集成 MCP 工具支持，以便 AI 能够调用外部工具来增强生成能力。

#### Acceptance Criteria

1. WHEN LLM 服务生成内容 THEN 系统应支持可选的 MCP 工具调用模式（enable_mcp 参数）
2. WHEN enable_mcp=True THEN 系统应获取用户启用的 MCP 工具并传递给 AI
3. WHEN AI 决定使用工具 THEN 系统应执行工具调用并收集结果
4. WHEN 工具调用完成 THEN 系统应将结果传递给 AI 进行第二轮生成
5. WHEN 所有工具调用失败或用户未启用任何工具 THEN 系统应降级为普通生成模式

### Requirement 10

**User Story:** 作为用户，我希望在小说生成时能够使用 MCP 工具搜索参考资料，以便生成更丰富和准确的内容。

#### Acceptance Criteria

1. WHEN 用户生成小说内容 THEN 系统应支持 enable_mcp 参数
2. WHEN enable_mcp=True THEN 系统应使用 MCP 工具搜索相关参考资料
3. WHEN 搜索到参考资料 THEN 系统应将资料融入生成提示词
4. WHEN MCP 工具调用失败 THEN 系统应降级为普通生成模式
5. WHEN 生成完成 THEN 系统应记录是否使用了 MCP 增强
