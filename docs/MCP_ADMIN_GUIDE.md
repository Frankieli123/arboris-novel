# MCP 插件系统管理员指南

本指南面向 Arboris Novel 系统管理员，详细说明如何配置、管理和监控 MCP (Model Context Protocol) 插件系统。

## 目录

- [系统概述](#系统概述)
- [插件配置](#插件配置)
- [插件管理](#插件管理)
- [性能监控](#性能监控)
- [故障排查](#故障排查)
- [最佳实践](#最佳实践)
- [安全建议](#安全建议)

---

## 系统概述

### MCP 插件系统架构

MCP 插件系统采用分层架构设计：

```
┌─────────────────────────────────────────┐
│          前端管理界面                    │
│  (插件列表、配置、测试、监控)            │
└──────────────┬──────────────────────────┘
               │ REST API
┌──────────────┴──────────────────────────┐
│          API 层 (FastAPI)                │
│  /api/mcp/plugins - 插件 CRUD            │
│  /api/mcp/test - 插件测试                │
│  /api/mcp/metrics - 性能指标             │
└──────────────┬──────────────────────────┘
               │
┌──────────────┴──────────────────────────┐
│          服务层                          │
│  - MCPPluginService (插件管理)          │
│  - MCPToolService (工具调用)            │
│  - MCPTestService (智能测试)            │
└──────────────┬──────────────────────────┘
               │
┌──────────────┴──────────────────────────┐
│          MCP 核心层                      │
│  - MCPPluginRegistry (连接池)           │
│  - HTTPMCPClient (HTTP 客户端)          │
└──────────────┬──────────────────────────┘
               │ MCP Protocol (HTTP)
┌──────────────┴──────────────────────────┐
│       外部 MCP 服务器                    │
│  (Exa Search, 文件系统, 自定义服务等)   │
└─────────────────────────────────────────┘
```

### 核心特性

- **连接池管理**：自动管理多用户并发连接，支持 LRU 驱逐和 TTL 过期
- **工具缓存**：缓存工具定义，减少重复的 list_tools 调用
- **并行执行**：多个工具调用并行执行，提升性能
- **重试机制**：指数退避重试策略，提高可靠性
- **智能测试**：使用 AI 自动生成测试用例
- **性能监控**：详细的调用指标和成功率统计
- **降级策略**：工具失败时自动降级为普通生成模式

---

## 插件配置

### 1. 添加新插件

#### 通过管理界面

1. 登录管理员账号
2. 进入"设置" → "MCP 插件管理"
3. 点击"添加插件"
4. 填写插件信息：

| 字段 | 必填 | 说明 | 示例 |
|------|------|------|------|
| 插件名称 | ✅ | 唯一标识符，英文小写+下划线 | `exa_search` |
| 显示名称 | ✅ | 用户看到的名称 | `Exa 搜索引擎` |
| 插件类型 | ✅ | 目前仅支持 `http` | `http` |
| 服务器 URL | ✅ | MCP 服务器地址 | `https://api.exa.ai/mcp` |
| 认证信息 | ❌ | JSON 格式的 HTTP 头 | `{"Authorization": "Bearer xxx"}` |
| 分类 | ❌ | 插件分类 | `search`, `storage`, `knowledge` |
| 全局启用 | ✅ | 是否全局启用 | `true` |
| 额外配置 | ❌ | JSON 格式的额外配置 | `{"timeout": 30}` |

5. 点击"测试连接"验证配置
6. 保存插件

#### 通过 API

```bash
curl -X POST "http://your-domain/api/mcp/plugins" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plugin_name": "exa_search",
    "display_name": "Exa 搜索引擎",
    "plugin_type": "http",
    "server_url": "https://api.exa.ai/mcp",
    "headers": {
      "Authorization": "Bearer YOUR_EXA_API_KEY"
    },
    "category": "search",
    "enabled": true
  }'
```

### 2. 常见插件配置示例

#### Exa Search（网络搜索）

```json
{
  "plugin_name": "exa_search",
  "display_name": "Exa 搜索引擎",
  "plugin_type": "http",
  "server_url": "https://api.exa.ai/mcp",
  "headers": {
    "Authorization": "Bearer YOUR_EXA_API_KEY",
    "Content-Type": "application/json"
  },
  "category": "search",
  "enabled": true,
  "config": {
    "max_results": 10,
    "timeout": 30
  }
}
```

**获取 Exa API Key：**
1. 访问 [Exa.ai](https://exa.ai/)
2. 注册账号并获取 API Key
3. 将 Key 填入 `headers.Authorization`

#### 文件系统访问

```json
{
  "plugin_name": "filesystem",
  "display_name": "本地文件系统",
  "plugin_type": "http",
  "server_url": "http://localhost:3000/mcp",
  "category": "storage",
  "enabled": true,
  "config": {
    "allowed_paths": ["/data/novels", "/data/references"]
  }
}
```

**部署文件系统 MCP 服务器：**
```bash
# 使用官方 MCP 文件系统服务器
npm install -g @modelcontextprotocol/server-filesystem
mcp-server-filesystem --port 3000 --allowed-paths /data/novels,/data/references
```

#### 自定义知识库

```json
{
  "plugin_name": "custom_kb",
  "display_name": "小说知识库",
  "plugin_type": "http",
  "server_url": "http://your-kb-server:8080/mcp",
  "headers": {
    "X-API-Key": "YOUR_KB_API_KEY"
  },
  "category": "knowledge",
  "enabled": true
}
```

### 3. 认证配置

MCP 插件支持多种认证方式，通过 `headers` 字段配置：

#### Bearer Token

```json
{
  "headers": {
    "Authorization": "Bearer YOUR_API_KEY"
  }
}
```

#### API Key Header

```json
{
  "headers": {
    "X-API-Key": "YOUR_API_KEY"
  }
}
```

#### Basic Auth

```json
{
  "headers": {
    "Authorization": "Basic BASE64_ENCODED_CREDENTIALS"
  }
}
```

#### 自定义 Headers

```json
{
  "headers": {
    "X-Custom-Auth": "your-auth-token",
    "X-Client-ID": "arboris-novel"
  }
}
```

---

## 插件管理

### 1. 查看插件列表

管理界面会显示所有已配置的插件及其状态：

- **插件名称**：唯一标识符
- **显示名称**：用户友好的名称
- **分类**：插件类型（搜索、存储、知识等）
- **全局状态**：是否全局启用
- **连接状态**：当前连接是否正常
- **工具数量**：提供的工具数量
- **调用统计**：总调用次数、成功率

### 2. 更新插件配置

修改插件配置后，系统会自动：
1. 关闭所有现有连接
2. 清除工具缓存
3. 使用新配置重新建立连接

**注意**：更新配置会影响所有正在使用该插件的用户。

### 3. 禁用/启用插件

#### 全局禁用

管理员可以全局禁用插件，此时：
- 所有用户无法使用该插件
- 现有连接会被关闭
- 工具缓存会被清除

#### 用户级禁用

用户可以在个人设置中禁用插件，不影响其他用户。

### 4. 删除插件

删除插件时，系统会：
1. 关闭所有相关连接
2. 删除所有用户的偏好设置
3. 清除相关缓存和指标
4. 从数据库中移除配置

**警告**：删除操作不可逆，请谨慎操作。

### 5. 测试插件

管理员可以使用"测试插件"功能验证配置：

#### 测试流程

1. **连接测试**：尝试建立与 MCP 服务器的连接
2. **工具发现**：获取插件提供的工具列表
3. **智能测试**：使用 AI 选择合适的工具并生成测试参数
4. **执行测试**：调用工具并记录结果
5. **生成报告**：返回详细的测试报告

#### 测试报告示例

```json
{
  "success": true,
  "plugin_name": "exa_search",
  "connection_status": "connected",
  "tools_count": 3,
  "tools": [
    {
      "name": "search",
      "description": "Search the web for information"
    },
    {
      "name": "find_similar",
      "description": "Find similar content"
    },
    {
      "name": "get_contents",
      "description": "Get full content of URLs"
    }
  ],
  "test_results": [
    {
      "tool_name": "search",
      "success": true,
      "duration_ms": 1250,
      "test_input": {
        "query": "quantum computing basics",
        "num_results": 5
      },
      "result_summary": "Found 5 relevant results"
    }
  ],
  "recommendations": [
    "插件工作正常，所有工具可用",
    "平均响应时间 1.25 秒，性能良好"
  ]
}
```

---

## 性能监控

### 1. 查看工具调用指标

管理界面提供详细的性能监控面板：

#### 全局指标

- **总调用次数**：所有工具的总调用次数
- **成功率**：成功调用的百分比
- **平均响应时间**：所有调用的平均耗时
- **活跃连接数**：当前活跃的 MCP 连接数

#### 单个工具指标

每个工具都有独立的统计：

```json
{
  "tool_name": "exa_search.search",
  "total_calls": 1523,
  "success_calls": 1498,
  "failed_calls": 25,
  "success_rate": 98.36,
  "avg_duration_ms": 1250.5,
  "last_call_time": "2024-01-15T10:30:00Z"
}
```

### 2. 连接池状态

查看当前连接池的状态：

- **最大连接数**：配置的连接池大小（默认 100）
- **当前连接数**：活跃的连接数量
- **空闲连接数**：可复用的空闲连接
- **过期连接数**：等待清理的过期连接

### 3. 缓存统计

工具定义缓存的性能指标：

- **缓存命中率**：缓存命中的百分比
- **缓存大小**：当前缓存的条目数
- **平均命中次数**：每个缓存条目的平均使用次数

### 4. 性能优化建议

系统会根据监控数据提供优化建议：

- **高失败率警告**：某个工具失败率超过 10%
- **慢响应警告**：平均响应时间超过 5 秒
- **连接池不足**：频繁触发 LRU 驱逐
- **缓存效率低**：缓存命中率低于 50%

---

## 故障排查

### 1. 连接问题

#### 症状：插件连接失败

**可能原因：**
- 服务器 URL 错误
- 网络不可达
- 认证信息无效
- 服务器未启动

**排查步骤：**

1. **验证 URL**：
```bash
curl -v https://api.exa.ai/mcp
```

2. **检查认证**：
```bash
curl -H "Authorization: Bearer YOUR_KEY" https://api.exa.ai/mcp
```

3. **查看日志**：
```bash
docker logs arboris-backend | grep "MCP"
```

4. **测试插件**：
使用管理界面的"测试插件"功能获取详细错误信息

#### 症状：连接超时

**可能原因：**
- 网络延迟高
- 服务器响应慢
- 超时配置过短

**解决方案：**

1. 增加超时时间（在 `config` 中配置）：
```json
{
  "config": {
    "timeout": 60
  }
}
```

2. 检查网络连接：
```bash
ping api.exa.ai
traceroute api.exa.ai
```

### 2. 工具调用问题

#### 症状：AI 不调用插件工具

**可能原因：**
- 用户未启用插件
- 插件全局被禁用
- AI 判断不需要使用工具
- 工具描述不清晰

**排查步骤：**

1. **检查用户设置**：
   - 用户是否在个人设置中启用了插件？

2. **检查插件状态**：
   - 插件是否全局启用？
   - 插件连接是否正常？

3. **检查工具描述**：
   - 工具的 `description` 是否清晰？
   - 是否包含关键词？

4. **查看 AI 日志**：
```bash
docker logs arboris-backend | grep "tool_calls"
```

#### 症状：工具调用失败

**可能原因：**
- 参数格式错误
- 服务器返回错误
- 权限不足
- 配额超限

**排查步骤：**

1. **查看错误日志**：
```bash
docker logs arboris-backend | grep "工具调用失败"
```

2. **检查参数**：
   - AI 传递的参数是否符合工具的 schema？

3. **手动测试**：
使用管理界面的"测试插件"功能，手动调用工具

4. **检查配额**：
   - API Key 是否有足够的配额？
   - 是否达到速率限制？

### 3. 性能问题

#### 症状：响应时间过长

**可能原因：**
- 工具本身响应慢
- 网络延迟
- 并发调用过多
- 连接池不足

**解决方案：**

1. **优化工具调用**：
   - 减少不必要的工具调用
   - 使用更快的工具

2. **增加连接池大小**：
修改 `backend/app/mcp/config.py`：
```python
MAX_CLIENTS_PER_USER = 10  # 增加到 10
```

3. **启用缓存**：
确保工具缓存已启用（默认启用）

4. **监控指标**：
定期查看性能监控面板，识别瓶颈

#### 症状：内存占用过高

**可能原因：**
- 连接池过大
- 缓存过多
- 连接泄漏

**解决方案：**

1. **调整连接池配置**：
```python
MAX_CLIENTS_PER_USER = 5  # 减少连接数
CLIENT_TTL_SECONDS = 300  # 减少 TTL
```

2. **清理缓存**：
使用管理界面的"清除缓存"功能

3. **重启服务**：
```bash
docker restart arboris-backend
```

### 4. 常见错误代码

| 错误代码 | 说明 | 解决方案 |
|---------|------|---------|
| `CONNECTION_FAILED` | 无法连接到 MCP 服务器 | 检查 URL 和网络 |
| `AUTH_FAILED` | 认证失败 | 检查 API Key |
| `TIMEOUT` | 请求超时 | 增加超时时间 |
| `TOOL_NOT_FOUND` | 工具不存在 | 检查工具名称 |
| `INVALID_PARAMS` | 参数格式错误 | 检查参数 schema |
| `RATE_LIMIT` | 速率限制 | 等待或增加配额 |
| `SERVER_ERROR` | 服务器内部错误 | 联系服务提供商 |

---

## 最佳实践

### 1. 插件配置

- **使用描述性名称**：`plugin_name` 使用小写+下划线，`display_name` 使用用户友好的名称
- **合理分类**：使用统一的分类标准（search, storage, knowledge, tool 等）
- **安全存储密钥**：不要在配置中硬编码敏感信息，使用环境变量
- **定期测试**：每周测试一次插件连接，确保服务正常

### 2. 性能优化

- **合理设置连接池**：根据用户数量和并发量调整 `MAX_CLIENTS_PER_USER`
- **启用缓存**：工具定义缓存可以显著减少 API 调用
- **监控指标**：定期查看性能监控，及时发现问题
- **优化工具描述**：清晰的工具描述可以减少不必要的调用

### 3. 安全建议

- **最小权限原则**：只授予插件必要的权限
- **定期更新密钥**：定期轮换 API Key
- **监控异常调用**：关注失败率和异常模式
- **限制访问**：使用防火墙限制 MCP 服务器的访问来源

### 4. 用户管理

- **提供文档**：为用户提供插件使用指南
- **合理默认值**：为新用户设置合理的默认插件
- **收集反馈**：定期收集用户对插件的反馈
- **及时通知**：插件维护或故障时及时通知用户

---

## 安全建议

### 1. 认证和授权

- **使用 HTTPS**：所有 MCP 服务器必须使用 HTTPS
- **验证证书**：不要禁用 SSL 证书验证
- **定期轮换密钥**：至少每季度更换一次 API Key
- **最小权限**：只授予必要的权限

### 2. 数据保护

- **加密存储**：敏感配置应加密存储
- **日志脱敏**：日志中不要记录完整的 API Key
- **访问控制**：只有管理员可以查看和修改插件配置
- **审计日志**：记录所有配置变更操作

### 3. 网络安全

- **防火墙规则**：限制 MCP 服务器的访问来源
- **速率限制**：防止 API 滥用
- **DDoS 防护**：使用 CDN 或 DDoS 防护服务
- **监控异常**：监控异常的调用模式

### 4. 合规性

- **数据隐私**：确保插件调用符合数据隐私法规
- **用户同意**：明确告知用户插件会访问哪些数据
- **数据留存**：制定合理的日志和指标留存策略
- **定期审计**：定期审计插件配置和使用情况

---

## 附录

### A. 配置参数参考

#### MCPConfig (backend/app/mcp/config.py)

```python
@dataclass(frozen=True)
class MCPConfig:
    # 连接池配置
    MAX_CLIENTS_PER_USER: int = 5
    CLIENT_TTL_SECONDS: int = 600
    CLEANUP_INTERVAL_SECONDS: int = 60
    
    # 超时配置
    CONNECTION_TIMEOUT_SECONDS: float = 10.0
    TOOL_CALL_TIMEOUT_SECONDS: float = 30.0
    
    # 重试配置
    MAX_RETRIES: int = 3
    BASE_RETRY_DELAY_SECONDS: float = 1.0
    MAX_RETRY_DELAY_SECONDS: float = 10.0
    
    # 缓存配置
    TOOL_CACHE_TTL_MINUTES: int = 30
```

### B. API 端点参考

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/mcp/plugins` | GET | 用户 | 获取插件列表 |
| `/api/mcp/plugins` | POST | 管理员 | 创建插件 |
| `/api/mcp/plugins/{id}` | GET | 用户 | 获取插件详情 |
| `/api/mcp/plugins/{id}` | PUT | 管理员 | 更新插件 |
| `/api/mcp/plugins/{id}` | DELETE | 管理员 | 删除插件 |
| `/api/mcp/plugins/{id}/toggle` | POST | 用户 | 切换启用状态 |
| `/api/mcp/plugins/{id}/test` | POST | 管理员 | 测试插件 |
| `/api/mcp/tools` | GET | 用户 | 获取用户的工具列表 |
| `/api/mcp/metrics` | GET | 管理员 | 获取性能指标 |
| `/api/mcp/cache/clear` | POST | 管理员 | 清除缓存 |

### C. 数据库表结构

#### mcp_plugins

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| plugin_name | VARCHAR(100) | 插件名称（唯一） |
| display_name | VARCHAR(200) | 显示名称 |
| plugin_type | VARCHAR(50) | 插件类型 |
| server_url | VARCHAR(500) | 服务器 URL |
| headers | TEXT | 认证信息（JSON） |
| enabled | BOOLEAN | 全局启用状态 |
| category | VARCHAR(50) | 分类 |
| config | TEXT | 额外配置（JSON） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### user_plugin_preferences

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| user_id | INTEGER | 用户 ID（外键） |
| plugin_id | INTEGER | 插件 ID（外键） |
| enabled | BOOLEAN | 用户启用状态 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### D. 相关资源

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Arboris Novel 项目主页](https://github.com/t59688/arboris-novel)
- [问题反馈](https://github.com/t59688/arboris-novel/issues)

---

## 更新日志

- **2024-01-15**：初始版本
  - 添加基础配置指南
  - 添加性能监控说明
  - 添加故障排查流程
  - 添加最佳实践和安全建议

---

如有问题或建议，请联系技术支持或在 GitHub 提交 Issue。
