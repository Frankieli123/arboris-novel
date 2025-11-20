# MCP调用流程分析报告

## 项目概述
这是一个AI小说创作平台，集成了MCP (Model Context Protocol) 插件系统，用于增强AI创作能力。

---

## 一、MCP架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP 插件系统架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   API层      │ ───> │   服务层     │ ───> │  MCP核心  │ │
│  │ mcp_plugins  │      │ mcp_tool_    │      │  registry │ │
│  │    .py       │      │  service.py  │      │    .py    │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                      │                     │       │
│         │                      │                     │       │
│         v                      v                     v       │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │  数据库层    │      │  测试服务    │      │ HTTP客户端│ │
│  │  MCPPlugin   │      │ mcp_test_    │      │ http_     │ │
│  │   Model      │      │  service.py  │      │ client.py │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈
- **后端框架**: FastAPI + SQLAlchemy
- **MCP SDK**: 官方 Python MCP SDK (`mcp` package)
- **通信协议**: HTTP (streamable HTTP)
- **AI服务**: OpenAI / Anthropic (支持Function Calling)

---

## 二、MCP调用流程详解

### 2.1 插件生命周期管理

#### 阶段1: 插件注册与加载

```python
# 步骤1: 用户通过API创建插件配置
POST /mcp/plugins
{
  "plugin_name": "exa",
  "plugin_type": "http",
  "server_url": "https://mcp.exa.ai",
  "headers": {"Authorization": "Bearer xxx"},
  "enabled": true,
  "category": "search"
}

# 步骤2: 插件配置存入数据库 (MCPPlugin表)
# 步骤3: 如果enabled=true，自动加载到注册表
await mcp_registry.load_plugin(plugin)
```

**加载过程** (`registry.py:load_plugin`):
1. 创建 `HTTPMCPClient` 实例
2. 建立与MCP服务器的连接
3. 初始化MCP会话
4. 存储到 `_sessions` 字典中
5. 启动后台健康检查任务

#### 阶段2: 工具发现

```python
# 获取插件提供的工具列表
tools = await mcp_registry.get_plugin_tools(user_id, plugin_name)

# 内部流程:
# 1. 从注册表获取客户端
# 2. 调用 client.list_tools()
# 3. 返回工具定义列表
```

**工具定义格式** (OpenAI Function Calling):
```json
{
  "type": "function",
  "function": {
    "name": "exa_search",
    "description": "搜索网络内容",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string"},
        "num_results": {"type": "integer"}
      },
      "required": ["query"]
    }
  }
}
```

### 2.2 AI创作中的MCP工具注入

#### 场景1: 章节生成 (带MCP增强)

```
用户请求生成章节
    │
    ├─> 1. 获取用户启用的MCP工具
    │      └─> mcp_tool_service.get_user_enabled_tools()
    │          ├─> 查询数据库: enabled=True的插件
    │          ├─> 确保插件已加载到注册表
    │          └─> 格式化为OpenAI工具格式
    │
    ├─> 2. 构建AI提示词
    │      ├─> 项目信息 (书名、主题、世界观)
    │      ├─> 角色信息
    │      ├─> 大纲上下文
    │      └─> 记忆系统上下文
    │
    ├─> 3. 调用AI服务 (带工具)
    │      └─> ai_service.generate_text_with_mcp()
    │          ├─> 第一轮: AI分析任务，决定是否调用工具
    │          │   └─> 返回 tool_calls 或 content
    │          │
    │          ├─> 如果有 tool_calls:
    │          │   ├─> 执行工具调用
    │          │   │   └─> mcp_tool_service.execute_tool_calls()
    │          │   │       ├─> 并行执行多个工具
    │          │   │       ├─> 带重试机制 (指数退避)
    │          │   │       └─> 记录调用指标
    │          │   │
    │          │   ├─> 构建工具结果上下文
    │          │   └─> 第二轮: AI基于工具结果生成内容
    │          │
    │          └─> 返回最终生成的章节内容
    │
    └─> 4. 保存章节到数据库
```

#### 场景2: 大纲生成 (带MCP搜索增强)

```python
# 用户请求生成大纲
POST /projects/{project_id}/wizard/generate-outline

# 流程:
# 1. 检查用户是否启用了搜索类MCP插件
# 2. 如果有，使用MCP搜索相关情节参考
#    └─> 调用 exa_search("小说情节设计技巧")
# 3. 将搜索结果注入到提示词中
# 4. AI基于参考资料生成大纲
```

### 2.3 工具调用执行流程

#### 详细步骤 (`mcp_tool_service.py:execute_tool_calls`)

```python
# 输入: AI返回的tool_calls列表
tool_calls = [
  {
    "id": "call_abc123",
    "type": "function",
    "function": {
      "name": "exa_search",
      "arguments": '{"query": "科幻小说情节设计"}'
    }
  }
]

# 步骤1: 并行执行所有工具调用
tasks = [_execute_single_tool(tc) for tc in tool_calls]
results = await asyncio.gather(*tasks)

# 步骤2: 单个工具执行 (_execute_single_tool)
# 2.1 解析插件名和工具名
plugin_name, tool_name = "exa", "search"

# 2.2 解析参数
arguments = json.loads(tool_call["function"]["arguments"])

# 2.3 带重试的调用
result = await _call_tool_with_retry(
    user_id, plugin_name, tool_name, arguments, timeout=60
)

# 2.4 记录指标
self._metrics[tool_key].update_success(duration_ms)

# 步骤3: 格式化返回结果
return {
    "tool_call_id": "call_abc123",
    "role": "tool",
    "name": "exa_search",
    "content": json.dumps(result),
    "success": True
}
```

#### 重试机制 (指数退避)

```python
# 配置 (mcp/config.py)
MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0s
MAX_RETRY_DELAY = 10.0s

# 重试逻辑
for attempt in range(MAX_RETRIES):
    try:
        result = await mcp_registry.call_tool(...)
        return result
    except Exception as e:
        if attempt == MAX_RETRIES - 1:
            raise
        delay = min(BASE_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
        await asyncio.sleep(delay)
```

### 2.4 MCP HTTP客户端实现

#### 连接建立 (`http_client.py:_ensure_connected`)

```python
# 使用官方MCP SDK
from mcp.client.streamable_http import streamablehttp_client

# 1. 创建HTTP流
stream_context = streamablehttp_client(
    url="https://mcp.exa.ai",
    headers={"Authorization": "Bearer xxx"},
    timeout=60.0
)
read_stream, write_stream, _ = await stream_context.__aenter__()

# 2. 创建MCP会话
session = ClientSession(read_stream, write_stream)
await session.__aenter__()

# 3. 初始化会话
await session.initialize()
```

#### 工具调用 (`http_client.py:call_tool`)

```python
# 调用MCP工具
result = await session.call_tool(
    tool_name="search",
    arguments={"query": "AI小说创作"}
)

# 处理返回结果
if result.content:
    for content in result.content:
        if isinstance(content, types.TextContent):
            return content.text
        elif isinstance(content, types.ImageContent):
            return {"type": "image", "data": content.data}
```

---

## 三、关键特性

### 3.1 连接池管理

```python
# registry.py: MCPPluginRegistry

# 特性:
# 1. 细粒度锁 - 每个用户一个锁，避免全局阻塞
# 2. LRU驱逐 - 达到max_clients时驱逐最久未使用的会话
# 3. 自动过期 - TTL机制，定期清理过期会话
# 4. 健康检查 - 监控错误率，自动标记异常会话

# 配置
MAX_CLIENTS = 1000
CLIENT_TTL = 3600s (1小时)
CLEANUP_INTERVAL = 300s (5分钟)
```

### 3.2 工具缓存

```python
# mcp_tool_service.py: 工具定义缓存

# 缓存结构
_tool_cache = {
    "user123:exa": ToolCacheEntry(
        tools=[...],
        expire_time=datetime(...),
        hit_count=42
    )
}

# 缓存策略
CACHE_TTL = 10分钟
# 减少重复的list_tools调用，提升性能
```

### 3.3 调用指标

```python
# 记录每个工具的调用统计
_metrics = {
    "exa.search": ToolMetrics(
        total_calls=100,
        success_calls=95,
        failed_calls=5,
        avg_duration_ms=234.5,
        success_rate=0.95
    )
}

# API查询
GET /mcp/plugins/metrics?tool_name=exa.search
```

### 3.4 智能测试

```python
# mcp_test_service.py: 使用AI测试插件

# 测试流程:
# 1. 连接测试 - 验证MCP服务器可达
# 2. 获取工具列表
# 3. AI分析工具 - 选择合适的工具进行测试
# 4. AI生成测试参数 - 真实有效的参数
# 5. 执行工具调用 - 验证功能正常
# 6. 返回详细测试报告

# 示例
POST /mcp/plugins/{plugin_id}/test
# 返回:
{
  "success": true,
  "message": "✅ Function Calling测试成功！",
  "tools_count": 5,
  "suggestions": [
    "🤖 AI选择: search",
    "📝 参数: {\"query\": \"人工智能最新进展\"}",
    "⏱️ 耗时: 456ms",
    "📊 结果: ..."
  ]
}
```

---

## 四、典型使用场景

### 4.1 场景: 创作科幻小说章节

```
1. 用户配置MCP插件
   ├─> Exa搜索 (获取科技资讯)
   └─> 文件系统 (读取参考资料)

2. 用户请求生成第5章
   └─> 主题: 太空探索

3. 系统执行流程:
   ├─> 加载MCP工具 (2个插件, 8个工具)
   │
   ├─> AI第一轮分析:
   │   └─> 决定调用 exa_search("最新太空探索技术")
   │
   ├─> 执行工具调用:
   │   ├─> 搜索到5篇相关文章
   │   └─> 耗时: 1.2秒
   │
   ├─> AI第二轮创作:
   │   ├─> 基于搜索结果
   │   ├─> 结合项目设定
   │   └─> 生成3000字章节内容
   │
   └─> 保存章节 + 更新记忆系统
```

### 4.2 场景: 大纲生成增强

```
1. 用户启动项目向导
   └─> 主题: 赛博朋克侦探故事

2. 生成大纲阶段:
   ├─> 检测到用户启用了Exa搜索
   │
   ├─> 自动搜索参考资料:
   │   ├─> "赛博朋克小说情节设计"
   │   ├─> "侦探小说结构技巧"
   │   └─> "科幻悬疑故事案例"
   │
   ├─> 将搜索结果注入提示词:
   │   【📚 MCP工具搜索 - 情节设计参考】
   │   以下是通过MCP工具搜索到的情节设计参考资料...
   │
   └─> AI生成20章大纲
       └─> 参考了真实的创作技巧和案例
```

---

## 五、数据流图

### 5.1 完整数据流

```
┌─────────────┐
│   用户请求   │ (生成章节)
└──────┬──────┘
       │
       v
┌─────────────────────────────────────────────────────────┐
│                    API层 (FastAPI)                       │
│  POST /projects/{id}/chapters/{chapter_id}/generate     │
└──────┬──────────────────────────────────────────────────┘
       │
       v
┌─────────────────────────────────────────────────────────┐
│                  服务层 (Services)                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │  1. 获取项目信息 (Project, WorldSetting)         │  │
│  │  2. 获取角色信息 (Characters)                    │  │
│  │  3. 获取大纲上下文 (Outlines)                    │  │
│  │  4. 获取记忆上下文 (Memory Service)              │  │
│  │  5. 获取MCP工具 (MCP Tool Service) ◄─────────┐  │  │
│  └──────────────────────────────────────────────────┘  │
└──────┬──────────────────────────────────────────────────┘
       │                                                │
       v                                                │
┌─────────────────────────────────────────────────────┐  │
│              MCP Tool Service                        │  │
│  ┌────────────────────────────────────────────────┐ │  │
│  │  get_user_enabled_tools()                      │ │  │
│  │  ├─> 查询数据库: enabled=True的插件            │ │  │
│  │  ├─> 确保插件已加载                            │ │  │
│  │  └─> 格式化为OpenAI工具格式                    │ │  │
│  └────────────────────────────────────────────────┘ │  │
└──────┬──────────────────────────────────────────────┘  │
       │                                                  │
       v                                                  │
┌─────────────────────────────────────────────────────┐  │
│              MCP Registry                            │  │
│  ┌────────────────────────────────────────────────┐ │  │
│  │  _sessions: {                                  │ │  │
│  │    "user123:exa": SessionInfo(                │ │  │
│  │      client=HTTPMCPClient(...),               │ │  │
│  │      status="active"                          │ │  │
│  │    )                                          │ │  │
│  │  }                                            │ │  │
│  └────────────────────────────────────────────────┘ │  │
└──────┬──────────────────────────────────────────────┘  │
       │                                                  │
       v                                                  │
┌─────────────────────────────────────────────────────┐  │
│           HTTP MCP Client                            │  │
│  ┌────────────────────────────────────────────────┐ │  │
│  │  官方MCP SDK                                   │ │  │
│  │  ├─> streamablehttp_client                    │ │  │
│  │  ├─> ClientSession                            │ │  │
│  │  └─> call_tool() / list_tools()              │ │  │
│  └────────────────────────────────────────────────┘ │  │
└──────┬──────────────────────────────────────────────┘  │
       │                                                  │
       v                                                  │
┌─────────────────────────────────────────────────────┐  │
│           MCP Server (外部)                          │  │
│  例如: https://mcp.exa.ai                            │  │
│  ├─> 接收工具调用请求                                │  │
│  ├─> 执行搜索/查询                                   │  │
│  └─> 返回结果                                        │  │
└──────┬──────────────────────────────────────────────┘  │
       │                                                  │
       │ (工具结果)                                       │
       v                                                  │
┌─────────────────────────────────────────────────────┐  │
│              AI Service                              │  │
│  ┌────────────────────────────────────────────────┐ │  │
│  │  generate_text_with_mcp()                      │ │  │
│  │  ├─> 第一轮: AI + 工具列表                     │ │  │
│  │  │   └─> 返回 tool_calls                       │ │  │
│  │  ├─> 执行工具调用 ──────────────────────────────┘  │
│  │  ├─> 第二轮: AI + 工具结果                     │  │
│  │  │   └─> 返回最终内容                          │  │
│  └────────────────────────────────────────────────┘ │  │
└──────┬──────────────────────────────────────────────┘  │
       │                                                  │
       v                                                  │
┌─────────────────────────────────────────────────────┐  │
│           生成的章节内容                             │  │
│  ├─> 保存到数据库                                    │  │
│  ├─> 更新记忆系统                                    │  │
│  └─> 返回给用户                                      │  │
└─────────────────────────────────────────────────────┘  │
```

---

## 六、配置与优化

### 6.1 性能配置 (`mcp/config.py`)

```python
@dataclass(frozen=True)
class MCPConfig:
    # 连接池
    MAX_CLIENTS = 1000
    CLIENT_TTL_SECONDS = 3600
    IDLE_TIMEOUT_SECONDS = 1800
    
    # 健康检查
    HEALTH_CHECK_INTERVAL_SECONDS = 60
    ERROR_RATE_CRITICAL = 0.7
    ERROR_RATE_WARNING = 0.4
    
    # 清理任务
    CLEANUP_INTERVAL_SECONDS = 300
    
    # 缓存
    TOOL_CACHE_TTL_MINUTES = 10
    
    # 重试
    MAX_RETRIES = 3
    BASE_RETRY_DELAY_SECONDS = 1.0
    MAX_RETRY_DELAY_SECONDS = 10.0
    
    # 超时
    DEFAULT_TIMEOUT_SECONDS = 60.0
    TOOL_CALL_TIMEOUT_SECONDS = 60.0
```

### 6.2 并发优化

```python
# 1. 细粒度锁 - 每个用户一个锁
_user_locks: Dict[str, asyncio.Lock] = {}

# 2. 并行工具调用
tasks = [execute_tool(tc) for tc in tool_calls]
results = await asyncio.gather(*tasks)

# 3. HTTP连接池
httpx.Limits(
    max_keepalive_connections=50,
    max_connections=100,
    keepalive_expiry=30.0
)
```

### 6.3 错误处理

```python
# 1. 重试机制 - 指数退避
# 2. 超时控制 - 60秒默认超时
# 3. 降级策略 - MCP失败时降级为普通生成
# 4. 错误率监控 - 自动标记异常会话
# 5. 详细日志 - 记录所有关键步骤
```

---

## 七、API接口总结

### 7.1 插件管理

```
GET    /mcp/plugins                    # 列出所有插件
POST   /mcp/plugins                    # 创建插件
POST   /mcp/plugins/simple             # 简化创建 (JSON配置)
GET    /mcp/plugins/{id}               # 获取插件详情
PUT    /mcp/plugins/{id}               # 更新插件
DELETE /mcp/plugins/{id}               # 删除插件
POST   /mcp/plugins/{id}/toggle        # 启用/禁用插件
POST   /mcp/plugins/{id}/test          # 测试插件
GET    /mcp/plugins/{id}/tools         # 获取工具列表
POST   /mcp/plugins/call               # 调用工具
```

### 7.2 监控与管理

```
GET    /mcp/plugins/metrics            # 获取调用指标
GET    /mcp/plugins/cache/stats        # 获取缓存统计
POST   /mcp/plugins/cache/clear        # 清理缓存
```

---

## 八、最佳实践

### 8.1 插件配置

```json
{
  "plugin_name": "exa",
  "display_name": "Exa搜索",
  "plugin_type": "http",
  "server_url": "https://mcp.exa.ai",
  "headers": {
    "Authorization": "Bearer YOUR_API_KEY"
  },
  "enabled": true,
  "category": "search",
  "config": {
    "timeout": 60
  }
}
```

### 8.2 工具调用建议

1. **合理设置超时**: 默认60秒，可根据工具特性调整
2. **启用缓存**: 减少重复的list_tools调用
3. **监控指标**: 定期查看success_rate和avg_duration
4. **错误处理**: 实现降级策略，MCP失败时不影响核心功能
5. **测试先行**: 使用智能测试功能验证插件配置

### 8.3 性能优化

1. **连接复用**: 利用连接池，避免频繁建立连接
2. **并行调用**: 多个工具调用使用asyncio.gather并行执行
3. **细粒度锁**: 避免全局锁，提升并发性能
4. **LRU驱逐**: 控制内存使用，自动清理过期会话
5. **健康检查**: 及时发现异常会话，避免雪崩效应

---

## 九、总结

### 9.1 核心优势

1. **标准化**: 基于官方MCP SDK，符合协议规范
2. **高性能**: 连接池、缓存、并行调用
3. **可靠性**: 重试机制、健康检查、降级策略
4. **可观测**: 详细指标、日志、测试工具
5. **易用性**: 简化配置、智能测试、自动管理

### 9.2 应用价值

- **增强AI能力**: 通过MCP工具访问外部知识和服务
- **提升创作质量**: 实时搜索、参考资料注入
- **灵活扩展**: 支持任意MCP兼容的工具和服务
- **用户友好**: 简单配置即可使用，无需编程

### 9.3 技术亮点

1. **官方SDK集成**: 使用`mcp` Python包，确保兼容性
2. **Function Calling**: 完整支持OpenAI/Anthropic工具调用
3. **智能测试**: AI驱动的插件测试，自动生成测试用例
4. **记忆增强**: MCP工具结果与记忆系统结合
5. **生产就绪**: 完善的错误处理、监控、优化

---

## 附录

### A. 相关文件清单

```
backend/app/mcp/
├── __init__.py           # 模块入口
├── config.py             # 配置常量
├── http_client.py        # HTTP MCP客户端
└── registry.py           # 插件注册表

backend/app/api/
└── mcp_plugins.py        # MCP API接口

backend/app/services/
├── mcp_tool_service.py   # 工具服务
├── mcp_test_service.py   # 测试服务
├── ai_service.py         # AI服务 (集成MCP)
└── prompt_service.py     # 提示词服务

backend/app/models/
└── mcp_plugin.py         # 数据模型

backend/app/schemas/
└── mcp_plugin.py         # API Schema
```

### B. 依赖包

```
mcp                       # 官方MCP Python SDK
httpx                     # HTTP客户端
openai                    # OpenAI API
anthropic                 # Anthropic API
fastapi                   # Web框架
sqlalchemy                # ORM
```

---

**报告生成时间**: 2025-11-21  
**分析版本**: v1.0  
**项目**: AI小说创作平台 - MCP集成
