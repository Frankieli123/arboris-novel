# 修复 MCP 插件 500 错误

## 问题原因

你遇到的 500 错误是因为数据库表结构缺少 `user_id` 字段。错误信息：

```
Unknown column 'mcp_plugins.user_id' in 'field list'
```

## 快速修复方法

### 方法一：使用 Python 迁移脚本（推荐）

在 Docker 容器中运行：

```bash
# 进入后端容器
docker exec -it <你的容器名> bash

# 运行迁移脚本
cd /app
python db/migrations/run_migration.py
```

或者在本地运行：

```bash
cd backend
python db/migrations/run_migration.py
```

### 方法二：手动执行 SQL

#### 如果使用 MySQL：

```bash
# 进入容器
docker exec -it <你的容器名> bash

# 连接数据库
mysql -h host.docker.internal -u root -p

# 选择数据库
USE arboris;

# 执行以下 SQL：
ALTER TABLE mcp_plugins ADD COLUMN user_id INT NULL AFTER id;
ALTER TABLE mcp_plugins ADD CONSTRAINT fk_mcp_plugins_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_mcp_plugins_user ON mcp_plugins(user_id);
ALTER TABLE mcp_plugins DROP INDEX IF EXISTS plugin_name;
ALTER TABLE mcp_plugins ADD CONSTRAINT uq_user_plugin_name UNIQUE (user_id, plugin_name);
UPDATE mcp_plugins SET category = 'general' WHERE category IS NULL;
```

#### 如果使用 SQLite：

```bash
cd backend
sqlite3 storage/arboris.db < db/migrations/002_add_default_plugin_support_sqlite.sql
```

### 方法三：重建数据库（会丢失数据）

如果你的数据不重要，可以删除数据库重新初始化：

```bash
# 停止容器
docker-compose down

# 删除数据库（根据你的配置）
# MySQL: 删除数据库
# SQLite: 删除 storage/arboris.db 文件

# 重新启动
docker-compose up -d
```

## 验证修复

修复后，访问 MCP 插件管理页面，应该能正常显示。

你可以：
1. 点击"JSON导入"按钮
2. 粘贴 MCP 配置 JSON
3. 批量导入插件

## JSON 导入示例

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

## 需要帮助？

查看详细文档：
- `backend/db/migrations/MIGRATION_GUIDE.md` - 完整迁移指南
- `docs/MCP_JSON_IMPORT_GUIDE.md` - JSON 导入使用指南
