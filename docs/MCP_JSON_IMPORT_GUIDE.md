# MCP 插件 JSON 导入指南

## 功能说明

管理员可以通过 JSON 配置批量导入 MCP 插件，无需逐个手动添加。

## 使用步骤

1. 登录管理员账号
2. 进入"插件管理"页面
3. 点击"JSON导入"按钮
4. 粘贴 MCP 配置 JSON
5. 选择插件分类（可选）
6. 点击"导入"按钮

## JSON 格式

支持标准的 MCP 配置格式：

```json
{
  "mcpServers": {
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?exaApiKey=YOUR_API_KEY",
      "headers": {}
    },
    "brave-search": {
      "type": "http",
      "url": "https://mcp.brave.com/search",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      },
      "category": "search"
    }
  }
}
```

## 配置字段说明

### 必填字段

- `plugin_name`: 插件唯一标识符（从 mcpServers 的 key 自动提取）
- `url`: MCP 服务器地址

### 可选字段

- `type`: 插件类型，默认为 "http"
- `display_name`: 显示名称，默认使用 plugin_name
- `headers`: 认证请求头，JSON 对象
- `enabled`: 是否启用，默认为 true
- `category`: 插件分类，如 search、filesystem、database 等
- `config`: 额外配置，JSON 对象

## 插件分类

建议为插件设置合适的分类，便于 AI 智能匹配使用场景：

- `search`: 搜索类 - 网络搜索、信息查询
- `filesystem`: 文件系统 - 文件读写、目录操作
- `database`: 数据库 - 数据查询、数据管理
- `api`: API集成 - 第三方服务调用
- `tools`: 工具类 - 实用工具、辅助功能
- `other`: 其他

## 导入结果

导入完成后会显示：

- **成功导入**: 新创建的插件列表
- **已跳过**: 已存在的插件（不会覆盖）
- **导入失败**: 配置错误的插件及错误信息

## 示例配置

### Exa 搜索插件

```json
{
  "mcpServers": {
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?exaApiKey=YOUR_API_KEY",
      "headers": {},
      "category": "search"
    }
  }
}
```

### 多个插件批量导入

```json
{
  "mcpServers": {
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?exaApiKey=YOUR_API_KEY",
      "category": "search"
    },
    "filesystem": {
      "type": "http",
      "url": "http://localhost:3000/mcp",
      "category": "filesystem"
    },
    "database": {
      "type": "http",
      "url": "http://localhost:3001/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      },
      "category": "database"
    }
  }
}
```

## 注意事项

1. 导入的插件为**默认插件**，对所有用户生效
2. 如果插件名称已存在，会自动跳过，不会覆盖
3. JSON 格式必须正确，否则导入失败
4. 建议先在测试环境验证配置正确性
5. 导入后可以在插件列表中编辑或删除

## API 接口

如需通过 API 导入，可以调用：

```
POST /api/mcp/plugins/import
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "mcpServers": {
    ...
  }
}
```

响应：

```json
{
  "status": "success",
  "created": ["exa", "filesystem"],
  "skipped": ["database"],
  "errors": [],
  "summary": "成功导入 2 个插件，跳过 1 个已存在的插件，0 个失败"
}
```
