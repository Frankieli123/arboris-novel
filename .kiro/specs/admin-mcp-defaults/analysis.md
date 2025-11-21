# MuMu 项目 vs 当前项目 MCP 对比分析

## MuMu 项目的 MCP 应用

### 1. 数据模型
- **MCPPlugin 模型**：包含完整的插件配置
  - 支持 `user_id` 字段（用于区分用户插件和默认插件）
  - 支持 `category` 字段（插件分类）
  - 支持 `config` 和 `headers` JSON 字段
  - 支持 `enabled` 和 `status` 状态管理

### 2. MCP 工具的实际调用场景（重要！）

MuMu 项目在以下业务场景中调用 MCP 工具：

#### 2.1 大纲生成（outlines.py）
- **全新生成大纲**：`enable_mcp=True`
  - 使用 MCP 工具搜索情节设计参考资料
  - 调用 `ai_service.generate_with_mcp()` 收集参考
  - 将参考资料注入到大纲生成提示词中

- **续写大纲**：`enable_mcp=True`
  - 使用 MCP 工具搜索续写参考资料
  - 每批生成前都会调用 MCP 收集资料

#### 2.2 章节生成（chapters.py）
- **生成章节内容**：`enable_mcp=True`
  - 使用 MCP 工具收集章节参考资料
  - 根据章节主题搜索相关信息
  - 将参考资料融入章节内容生成

#### 2.3 角色生成（characters.py）
- **生成角色设定**：`enable_mcp=True`
  - 使用 MCP 工具搜索人物原型参考
  - 收集角色背景资料
  - 辅助生成更丰富的角色设定

#### 2.4 向导流式生成（wizard_stream.py）
- **大纲向导**：`enable_mcp=True`
  - 实时使用 MCP 工具收集参考资料
  - 流式返回进度和结果

- **角色向导**：`enable_mcp=True`
  - 实时搜索角色参考资料

### 3. AI 服务的 MCP 集成

**核心方法**：`ai_service.generate_with_mcp()`

```python
async def generate_with_mcp(
    prompt: str,
    user_id: str,
    db_session,
    enable_mcp: bool = True,
    max_tool_rounds: int = 3,
    tool_choice: str = "auto",
    **kwargs
):
    # 1. 获取用户启用的 MCP 工具
    tools = await mcp_tool_service.get_user_enabled_tools(user_id, db_session)
    
    # 2. 工具调用循环（最多 3 轮）
    for round in range(max_tool_rounds):
        # 调用 AI，第一轮传递工具列表
        ai_response = await generate_text(prompt, tools=tools if round==0 else None)
        
        # 检查 AI 是否请求工具调用
        if ai_response.tool_calls:
            # 执行工具调用
            tool_results = await mcp_tool_service.execute_tool_calls(...)
            
            # 构建工具上下文
            tool_context = await mcp_tool_service.build_tool_context(tool_results)
            
            # 更新对话历史，继续下一轮
            conversation_history.append(tool_context)
        else:
            # AI 返回最终内容，结束循环
            return ai_response.content
```

**关键特点**：
- 支持多轮工具调用（最多 3 轮）
- AI 自主决定是否使用工具
- 工具结果以 Markdown 格式注入对话
- 失败时自动降级为普通生成

### 4. 工具服务功能
- **MCPToolService**：
  - `get_user_enabled_tools()`: 获取用户启用的工具
  - `execute_tool_calls()`: 并行执行工具调用
  - `build_tool_context()`: 格式化工具结果为上下文
  - 工具缓存机制（TTL 缓存）
  - 工具调用指标记录
  - 指数退避重试机制

### 5. 前端界面
- **PluginManagement.vue**：
  - 插件列表展示（支持分类显示）
  - 插件创建/编辑（支持 JSON 配置）
  - 插件测试功能
  - 用户启用/禁用插件

- **业务表单**：
  - 所有生成请求都有 `enable_mcp` 开关
  - 用户可以选择是否使用 MCP 增强

## 当前项目的 MCP 实现

### 1. 数据模型
- **MCPPlugin 模型**：基本相同
  - 已支持 `category` 字段
  - 已支持 `config` 和 `headers` JSON 字段
  - 已支持 `enabled` 状态管理

### 2. MCP 工具的应用场景
- **当前缺失**：没有在 LLM 服务中集成 MCP 工具
- **需要添加**：类似 `generate_text_with_mcp()` 的功能

### 3. 工具服务功能
- **MCPToolService**：功能基本完整
  - 已实现工具获取、调用、缓存
  - 已实现指标记录和重试机制

### 4. 前端界面
- **PluginManagement.vue**：功能基本完整
  - 已支持插件管理
  - 已支持 JSON 配置

## 关键差异

### 1. 用户插件 vs 默认插件
- **MuMu 项目**：通过 `user_id` 字段区分
  - 默认插件：`user_id` 为特殊值（如 NULL 或 "system"）
  - 用户插件：`user_id` 为具体用户 ID
  
- **当前项目**：使用 `UserPluginPreference` 表
  - 默认插件：在 `MCPPlugin` 表中，`enabled=True`
  - 用户偏好：在 `UserPluginPreference` 表中记录

### 2. LLM 集成
- **MuMu 项目**：已集成到 LLM 服务
- **当前项目**：未集成（这是主要缺失）

## 需要实现的功能

### 1. 管理员设置中的默认 MCP 配置
- 在管理员设置界面添加 MCP 插件管理区域
- 管理员可以配置默认插件（对所有用户生效）
- 支持插件分类和 JSON 配置

### 2. 用户设置中的 MCP 管理
- 保留现有的用户插件管理功能
- 用户可以查看默认插件
- 用户可以添加自己的插件
- 用户可以启用/禁用默认插件（只影响自己）

### 3. 数据模型调整
- 使用 `user_id` 字段区分默认插件和用户插件
  - 默认插件：`user_id = NULL` 或 `user_id = "system"`
  - 用户插件：`user_id = 具体用户 ID`
- 保留 `UserPluginPreference` 表用于记录用户对默认插件的启用/禁用偏好

### 4. LLM 服务集成（可选，但重要）
- 在 LLM 服务中添加 MCP 工具支持
- 实现两轮 AI 调用逻辑
- 支持工具调用失败时的降级处理


## 当前项目的 MCP 实现状态

### 1. 已实现的功能 ✅
- **数据模型**：MCPPlugin 模型完整
- **工具服务**：MCPToolService 功能完整
- **插件注册表**：MCPPluginRegistry 完整
- **前端界面**：PluginManagement.vue 完整
- **API 路由**：MCP 插件管理 API 完整

### 2. 缺失的功能 ❌
- **LLM 服务集成**：没有在 LLM 服务中调用 MCP
- **业务场景应用**：没有在任何业务场景中使用 MCP
- **默认插件管理**：没有管理员设置默认插件的功能

### 3. 当前项目的业务场景

查看当前项目的主要业务场景：
- **小说生成**：`novels.py` - 生成小说内容
- **写作辅助**：`writer.py` - 写作建议、续写等
- **灵感模式**：`InspirationMode.vue` - 灵感生成

**这些场景都没有使用 MCP！**

## 关键发现

### MuMu 项目的 MCP 使用模式
1. **配置阶段**：管理员/用户配置 MCP 插件
2. **调用阶段**：在业务逻辑中调用 `generate_with_mcp()`
3. **增强效果**：AI 可以搜索实时信息、读取文件等

### 当前项目的状态
1. **配置阶段**：✅ 已完成（可以配置插件）
2. **调用阶段**：❌ 未实现（没有调用 MCP）
3. **增强效果**：❌ 无法使用（因为没有调用）

**结论：当前项目只实现了 MCP 的"配置"功能，但没有实现"调用"功能。**

## 需要实现的功能优先级

### 高优先级（核心功能）
1. **在 LLM 服务中集成 MCP**
   - 添加 `generate_with_mcp()` 方法
   - 实现多轮工具调用逻辑
   - 支持降级处理

2. **在业务场景中应用 MCP**
   - 小说生成时使用 MCP 搜索参考资料
   - 写作辅助时使用 MCP 查询信息
   - 灵感生成时使用 MCP 收集素材

### 中优先级（管理功能）
3. **管理员设置默认 MCP 插件**
   - 在管理员设置中添加 MCP 配置区域
   - 支持配置默认插件（对所有用户生效）
   - 用户可以覆盖默认设置

### 低优先级（优化功能）
4. **用户体验优化**
   - 在前端表单中添加 `enable_mcp` 开关
   - 显示 MCP 工具调用进度
   - 展示使用了哪些工具

## 建议的实现顺序

### 方案 A：先实现调用功能（推荐）
1. 在 LLM 服务中集成 MCP（让 MCP 能用起来）
2. 在 1-2 个业务场景中应用 MCP（验证效果）
3. 添加管理员默认插件配置（完善管理）

**优点**：快速看到 MCP 的实际效果，验证价值

### 方案 B：先实现管理功能
1. 添加管理员默认插件配置（完善管理）
2. 在 LLM 服务中集成 MCP（让 MCP 能用起来）
3. 在业务场景中应用 MCP（验证效果）

**优点**：管理功能更完善，但看不到实际效果

## 推荐方案

**建议采用方案 A**，因为：
1. 当前项目已经可以配置 MCP 插件了
2. 但是配置了也用不了（没有调用）
3. 应该先让 MCP 能用起来，看到实际效果
4. 然后再完善管理功能（默认插件等）
