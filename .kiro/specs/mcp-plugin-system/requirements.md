# Requirements Document

## Introduction

本需求文档定义了为 Arboris Novel AI 小说创作平台添加 MCP (Model Context Protocol) 插件系统的功能需求。MCP 插件系统将允许用户通过标准化的协议集成外部工具和服务（如搜索引擎、知识库、文件系统等），从而增强 AI 创作能力，提升小说创作质量。

该系统基于官方 MCP Python SDK，支持 HTTP 通信协议，并与现有的 LLM 服务（OpenAI/Anthropic Function Calling）深度集成。用户可以通过简单的配置启用 MCP 插件，系统会自动在章节生成、大纲创作等场景中调用相关工具，为 AI 提供实时的外部知识和数据支持。

## Glossary

- **MCP (Model Context Protocol)**: 一种标准化协议，用于 AI 应用与外部工具/服务之间的通信
- **MCP Plugin**: 遵循 MCP 协议的外部服务，提供特定功能（如搜索、文件访问等）
- **MCP Client**: 系统中负责与 MCP Server 通信的客户端组件
- **MCP Server**: 外部的 MCP 服务提供方，通过 HTTP 接口暴露工具
- **Tool**: MCP Plugin 提供的具体功能单元，可被 AI 调用
- **Tool Call**: AI 决定调用某个 Tool 的行为，包含工具名称和参数
- **Function Calling**: OpenAI/Anthropic 提供的功能，允许 AI 决定何时调用外部工具
- **Plugin Registry**: 插件注册表，管理所有已加载的 MCP 插件会话
- **Session**: 与 MCP Server 建立的持久连接会话
- **Arboris System**: 本小说创作平台系统
- **User**: 使用 Arboris 平台的小说创作者
- **Admin**: 系统管理员
- **Chapter Generation**: 章节内容生成功能
- **Outline Generation**: 大纲生成功能
- **LLM Service**: 系统中负责与大语言模型交互的服务层

## Requirements

### Requirement 1

**User Story:** 作为系统管理员，我希望能够配置和管理 MCP 插件，以便为用户提供增强的 AI 创作能力

#### Acceptance Criteria

1. WHEN 管理员创建 MCP 插件配置 THEN Arboris System SHALL 验证配置参数的完整性和有效性
2. WHEN 管理员提供插件名称、类型、服务器 URL 和认证信息 THEN Arboris System SHALL 将配置存储到数据库中
3. WHEN 插件配置的 enabled 字段设置为 true THEN Arboris System SHALL 自动加载插件到注册表并建立连接
4. WHEN 管理员更新插件配置 THEN Arboris System SHALL 重新加载插件会话以应用新配置
5. WHEN 管理员删除插件 THEN Arboris System SHALL 关闭相关会话并清理所有相关资源

### Requirement 2

**User Story:** 作为用户，我希望能够启用或禁用 MCP 插件，以便控制 AI 创作时使用哪些外部工具

#### Acceptance Criteria

1. WHEN 用户查看可用插件列表 THEN Arboris System SHALL 显示所有已配置的插件及其状态
2. WHEN 用户启用某个插件 THEN Arboris System SHALL 在该用户的 AI 创作请求中包含该插件提供的工具
3. WHEN 用户禁用某个插件 THEN Arboris System SHALL 在该用户的 AI 创作请求中排除该插件提供的工具
4. WHEN 用户的插件配置发生变化 THEN Arboris System SHALL 在下次 AI 请求时应用新的配置

### Requirement 3

**User Story:** 作为系统，我需要与 MCP Server 建立可靠的连接，以便调用外部工具

#### Acceptance Criteria

1. WHEN 系统加载 MCP 插件 THEN Arboris System SHALL 使用官方 MCP Python SDK 创建 HTTP 客户端
2. WHEN 建立连接时 THEN Arboris System SHALL 使用 streamablehttp_client 创建 HTTP 流
3. WHEN HTTP 流创建成功 THEN Arboris System SHALL 初始化 MCP ClientSession
4. WHEN ClientSession 初始化完成 THEN Arboris System SHALL 调用 initialize 方法完成握手
5. WHEN 连接建立失败 THEN Arboris System SHALL 记录错误日志并标记插件为不可用状态

### Requirement 4

**User Story:** 作为系统，我需要发现 MCP 插件提供的工具，以便将它们提供给 AI 使用

#### Acceptance Criteria

1. WHEN 系统需要获取插件工具列表 THEN Arboris System SHALL 调用 MCP Client 的 list_tools 方法
2. WHEN 获取到工具列表 THEN Arboris System SHALL 将工具定义转换为 OpenAI Function Calling 格式
3. WHEN 转换工具定义时 THEN Arboris System SHALL 包含工具名称、描述和参数 schema
4. WHEN 工具列表获取成功 THEN Arboris System SHALL 缓存结果以提升性能
5. WHEN 缓存超过有效期 THEN Arboris System SHALL 重新获取工具列表

### Requirement 5

**User Story:** 作为用户，我希望在生成章节内容时 AI 能够自动调用 MCP 工具获取外部信息，以便提升创作质量

#### Acceptance Criteria

1. WHEN 用户请求生成章节内容 THEN Arboris System SHALL 获取该用户启用的所有 MCP 工具
2. WHEN 调用 LLM 生成内容时 THEN Arboris System SHALL 将 MCP 工具列表作为可用工具传递给 AI
3. WHEN AI 返回 tool_calls THEN Arboris System SHALL 解析工具调用请求并执行相应的 MCP 工具
4. WHEN 工具执行完成 THEN Arboris System SHALL 将工具结果作为上下文再次调用 AI 生成最终内容
5. WHEN 所有工具调用失败 THEN Arboris System SHALL 降级为普通生成模式继续完成请求

### Requirement 6

**User Story:** 作为系统，我需要可靠地执行 MCP 工具调用，以便为 AI 提供准确的外部数据

#### Acceptance Criteria

1. WHEN 系统执行工具调用 THEN Arboris System SHALL 解析工具名称和参数
2. WHEN 解析参数时 THEN Arboris System SHALL 验证 JSON 格式的有效性
3. WHEN 调用 MCP 工具时 THEN Arboris System SHALL 使用 ClientSession 的 call_tool 方法
4. WHEN 工具调用失败 THEN Arboris System SHALL 使用指数退避策略进行重试
5. WHEN 达到最大重试次数仍失败 THEN Arboris System SHALL 返回错误信息并记录失败指标
6. WHEN 工具调用成功 THEN Arboris System SHALL 提取结果内容并格式化为 AI 可理解的格式
7. WHEN 多个工具需要调用 THEN Arboris System SHALL 并行执行所有工具调用以提升性能

### Requirement 7

**User Story:** 作为系统管理员，我希望能够测试 MCP 插件的连接和功能，以便确保配置正确

#### Acceptance Criteria

1. WHEN 管理员请求测试插件 THEN Arboris System SHALL 尝试建立与 MCP Server 的连接
2. WHEN 连接成功 THEN Arboris System SHALL 获取插件提供的工具列表
3. WHEN 获取到工具列表 THEN Arboris System SHALL 使用 AI 分析并选择合适的工具进行测试
4. WHEN AI 选择工具后 THEN Arboris System SHALL 使用 AI 生成真实有效的测试参数
5. WHEN 测试参数生成后 THEN Arboris System SHALL 执行工具调用并记录执行时间
6. WHEN 测试完成 THEN Arboris System SHALL 返回详细的测试报告包含成功状态、工具数量、测试建议和执行结果

### Requirement 8

**User Story:** 作为系统，我需要管理 MCP 连接池，以便高效地处理多用户并发请求

#### Acceptance Criteria

1. WHEN 系统启动时 THEN Arboris System SHALL 初始化 MCP Plugin Registry 并设置最大连接数限制
2. WHEN 用户请求需要 MCP 工具时 THEN Arboris System SHALL 为该用户创建或复用已有的插件会话
3. WHEN 会话数量达到上限 THEN Arboris System SHALL 使用 LRU 策略驱逐最久未使用的会话
4. WHEN 会话空闲时间超过 TTL THEN Arboris System SHALL 自动关闭并清理该会话
5. WHEN 系统执行定期清理任务 THEN Arboris System SHALL 关闭所有过期和异常的会话
6. WHEN 访问同一用户的会话时 THEN Arboris System SHALL 使用细粒度锁避免并发冲突

### Requirement 9

**User Story:** 作为系统管理员，我希望能够监控 MCP 工具的调用情况，以便了解系统运行状态和优化性能

#### Acceptance Criteria

1. WHEN 系统执行工具调用 THEN Arboris System SHALL 记录调用开始时间和结束时间
2. WHEN 工具调用成功 THEN Arboris System SHALL 增加成功计数并更新平均执行时间
3. WHEN 工具调用失败 THEN Arboris System SHALL 增加失败计数并记录错误信息
4. WHEN 管理员查询工具指标 THEN Arboris System SHALL 返回总调用次数、成功次数、失败次数、平均耗时和成功率
5. WHEN 工具错误率超过阈值 THEN Arboris System SHALL 标记该工具为异常状态并记录警告日志

### Requirement 10

**User Story:** 作为用户，我希望在生成大纲时 AI 能够使用搜索工具获取参考资料，以便创作出更有深度的故事结构

#### Acceptance Criteria

1. WHEN 用户请求生成大纲 THEN Arboris System SHALL 检查用户是否启用了搜索类 MCP 插件
2. WHEN 用户启用了搜索插件 THEN Arboris System SHALL 在提示词中包含搜索工具
3. WHEN AI 决定使用搜索工具 THEN Arboris System SHALL 执行搜索并获取相关参考资料
4. WHEN 搜索结果返回 THEN Arboris System SHALL 将结果注入到提示词上下文中
5. WHEN AI 基于搜索结果生成大纲 THEN Arboris System SHALL 返回包含参考资料的大纲内容

### Requirement 11

**User Story:** 作为系统，我需要缓存工具定义，以便减少重复的 list_tools 调用提升性能

#### Acceptance Criteria

1. WHEN 系统首次获取插件工具列表 THEN Arboris System SHALL 将结果存储到缓存中并设置过期时间
2. WHEN 系统再次需要相同插件的工具列表 THEN Arboris System SHALL 检查缓存是否存在且未过期
3. WHEN 缓存命中且未过期 THEN Arboris System SHALL 直接返回缓存的工具列表
4. WHEN 缓存过期或不存在 THEN Arboris System SHALL 重新调用 list_tools 并更新缓存
5. WHEN 管理员请求清理缓存 THEN Arboris System SHALL 删除所有缓存的工具定义

### Requirement 12

**User Story:** 作为系统，我需要处理 MCP 工具调用中的各种错误情况，以便保证系统稳定性

#### Acceptance Criteria

1. WHEN MCP Server 连接超时 THEN Arboris System SHALL 记录超时错误并在配置的超时时间后终止连接
2. WHEN MCP Server 返回错误响应 THEN Arboris System SHALL 解析错误信息并返回给调用方
3. WHEN 工具参数格式错误 THEN Arboris System SHALL 返回参数验证失败的错误信息
4. WHEN 网络连接中断 THEN Arboris System SHALL 标记会话为异常状态并在下次使用时重新建立连接
5. WHEN 工具调用过程中发生未预期的异常 THEN Arboris System SHALL 捕获异常、记录详细日志并返回通用错误信息

### Requirement 13

**User Story:** 作为开发者，我希望系统提供清晰的 API 接口，以便前端能够方便地管理和使用 MCP 插件

#### Acceptance Criteria

1. WHEN 前端请求插件列表 THEN Arboris System SHALL 返回所有插件的基本信息和状态
2. WHEN 前端创建插件 THEN Arboris System SHALL 验证请求参数并返回创建结果
3. WHEN 前端更新插件 THEN Arboris System SHALL 应用更新并返回更新后的插件信息
4. WHEN 前端删除插件 THEN Arboris System SHALL 执行删除操作并返回成功状态
5. WHEN 前端切换插件启用状态 THEN Arboris System SHALL 更新状态并返回新状态
6. WHEN 前端请求测试插件 THEN Arboris System SHALL 执行测试流程并返回测试报告
7. WHEN 前端查询工具指标 THEN Arboris System SHALL 返回指定工具或所有工具的统计数据
