# 数据库迁移指南

## 问题描述

如果你遇到以下错误：

```
sqlalchemy.exc.OperationalError: (asyncmy.errors.OperationalError) (1054, "Unknown column 'mcp_plugins.user_id' in 'field list'")
```

这说明你的数据库表结构需要更新。

## 解决方案

### 方法一：自动迁移（推荐）

系统会在启动时自动创建表结构，但如果表已存在，需要手动运行迁移脚本。

### 方法二：手动运行迁移脚本

根据你使用的数据库类型，选择对应的迁移脚本：

#### MySQL 数据库

```bash
# 连接到 MySQL 数据库
mysql -h <host> -u <username> -p <database>

# 运行迁移脚本
source backend/db/migrations/002_add_default_plugin_support_mysql.sql
```

或者使用命令行直接执行：

```bash
mysql -h <host> -u <username> -p <database> < backend/db/migrations/002_add_default_plugin_support_mysql.sql
```

#### SQLite 数据库

```bash
# 连接到 SQLite 数据库
sqlite3 storage/arboris.db

# 运行迁移脚本
.read backend/db/migrations/002_add_default_plugin_support_sqlite.sql
```

#### PostgreSQL 数据库

```bash
# 连接到 PostgreSQL 数据库
psql -h <host> -U <username> -d <database>

# 运行迁移脚本
\i backend/db/migrations/002_add_default_plugin_support.sql
```

### 方法三：使用 Docker 环境

如果你使用 Docker 部署，可以进入容器执行迁移：

```bash
# 进入容器
docker exec -it <container_name> bash

# MySQL
mysql -h host.docker.internal -u root -p arboris < /app/db/migrations/002_add_default_plugin_support_mysql.sql

# 或者使用 Python 脚本
python -c "
from app.db.session import engine
from app.db.base import Base
import asyncio

async def migrate():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Migration completed')

asyncio.run(migrate())
"
```

## 迁移内容

此迁移会：

1. 在 `mcp_plugins` 表中添加 `user_id` 字段（可为 NULL）
2. 添加外键约束，关联到 `users` 表
3. 创建索引以提高查询性能
4. 更新唯一约束，支持默认插件和用户插件
5. 将所有现有插件转换为默认插件（user_id = NULL）

## 验证迁移

迁移完成后，可以验证表结构：

### MySQL

```sql
DESCRIBE mcp_plugins;
SHOW INDEX FROM mcp_plugins;
```

### SQLite

```sql
.schema mcp_plugins
```

### PostgreSQL

```sql
\d mcp_plugins
```

## 回滚迁移

如果需要回滚，可以运行对应的回滚脚本：

```bash
# MySQL/PostgreSQL
source backend/db/migrations/002_add_default_plugin_support_rollback.sql
```

## 注意事项

1. **备份数据库**：在运行迁移前，请务必备份数据库
2. **停止服务**：建议在迁移期间停止应用服务
3. **测试环境**：先在测试环境验证迁移脚本
4. **权限检查**：确保数据库用户有 ALTER TABLE 权限

## 常见问题

### Q: 迁移失败怎么办？

A: 检查错误信息，可能的原因：
- 数据库用户权限不足
- 表中已有数据导致约束冲突
- 数据库版本不兼容

### Q: 如何确认迁移是否成功？

A: 运行以下查询：

```sql
SELECT * FROM mcp_plugins LIMIT 1;
```

如果能看到 `user_id` 字段，说明迁移成功。

### Q: 现有插件会受影响吗？

A: 不会。所有现有插件会自动转换为默认插件（user_id = NULL），对所有用户可见。
