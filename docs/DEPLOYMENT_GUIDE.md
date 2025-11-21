# Arboris Novel 部署指南

本指南详细说明如何部署 Arboris Novel 平台，包括 MCP 插件系统的配置。

## 目录

- [系统要求](#系统要求)
- [快速部署（Docker）](#快速部署docker)
- [手动部署](#手动部署)
- [数据库迁移](#数据库迁移)
- [MCP 插件系统配置](#mcp-插件系统配置)
- [环境变量配置](#环境变量配置)
- [生产环境优化](#生产环境优化)
- [故障排查](#故障排查)

---

## 系统要求

### 最低配置

- **CPU**：2 核
- **内存**：4 GB
- **存储**：20 GB
- **操作系统**：Linux (Ubuntu 20.04+, CentOS 7+) / macOS / Windows

### 推荐配置

- **CPU**：4 核或更多
- **内存**：8 GB 或更多
- **存储**：50 GB SSD
- **操作系统**：Linux (Ubuntu 22.04 LTS)

### 软件依赖

- **Docker**：20.10+ 和 Docker Compose 2.0+（推荐）
- **Python**：3.10+ (手动部署)
- **Node.js**：18+ (手动部署)
- **数据库**：SQLite (默认) 或 MySQL 8.0+

---

## 快速部署（Docker）

### 1. 克隆项目

```bash
git clone https://github.com/t59688/arboris-novel.git
cd arboris-novel
```

### 2. 配置环境变量

```bash
# 复制示例配置文件
cp deploy/.env.example deploy/.env

# 编辑配置文件
nano deploy/.env  # 或使用你喜欢的编辑器
```

**必填配置项：**

```bash
# 安全密钥（随机生成，至少 32 字符）
SECRET_KEY=your-super-secret-key-change-this-in-production

# OpenAI API 配置
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_API_BASE_URL=https://api.openai.com/v1  # 可选，默认 OpenAI
OPENAI_MODEL_NAME=gpt-3.5-turbo  # 可选，默认模型

# 管理员配置
ADMIN_DEFAULT_PASSWORD=change-this-password  # 首次登录后请修改

# 数据库配置（使用 SQLite 可跳过）
DB_PROVIDER=sqlite  # 或 mysql
```

### 3. 启动服务

#### 使用 SQLite（推荐新手）

```bash
cd deploy
docker compose up -d
```

#### 使用 MySQL

```bash
cd deploy
DB_PROVIDER=mysql docker compose --profile mysql up -d
```

#### 使用外部 MySQL

```bash
# 在 .env 中配置 MySQL 连接信息
DB_PROVIDER=mysql
DB_HOST=your-mysql-host
DB_PORT=3306
DB_USER=arboris
DB_PASSWORD=your-db-password
DB_NAME=arboris_novel

# 启动服务
docker compose up -d
```

### 4. 验证部署

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f

# 访问应用
# 浏览器打开 http://localhost:8080 (或你配置的端口)
```

### 5. 初始化管理员账号

首次部署后，使用以下凭据登录：

- **用户名**：`admin`
- **密码**：`.env` 中配置的 `ADMIN_DEFAULT_PASSWORD`

**重要**：登录后立即修改管理员密码！

---

## 手动部署

### 1. 后端部署

#### 安装依赖

```bash
cd backend

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖（包含 MCP SDK）
pip install -r requirements.txt
```

#### 配置环境变量

```bash
# 复制示例配置
cp env.example .env

# 编辑配置
nano .env
```

#### 初始化数据库

```bash
# SQLite（默认）
python -c "from app.db.init_db import init_db; import asyncio; asyncio.run(init_db())"

# MySQL
# 1. 创建数据库
mysql -u root -p -e "CREATE DATABASE arboris_novel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 运行迁移
python -c "from app.db.init_db import init_db; import asyncio; asyncio.run(init_db())"
```

#### 运行数据库迁移（MCP 插件表）

```bash
# 执行 MCP 插件系统迁移
mysql -u root -p arboris_novel < db/migrations/001_add_mcp_plugin_tables.sql

# 或使用 SQLite
sqlite3 arboris.db < db/migrations/001_add_mcp_plugin_tables_sqlite.sql
```

#### 启动后端服务

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 2. 前端部署

#### 安装依赖

```bash
cd frontend
npm install
```

#### 配置 API 地址

编辑 `frontend/.env.production`：

```bash
VITE_API_BASE_URL=http://your-backend-domain:8000
```

#### 构建生产版本

```bash
npm run build
```

构建产物位于 `frontend/dist/` 目录。

#### 部署静态文件

使用 Nginx 托管：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
    
    # 后端 API 代理
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 数据库迁移

### MCP 插件系统表结构

MCP 插件系统需要两个新表：

1. **mcp_plugins**：存储插件配置
2. **user_plugin_preferences**：存储用户插件偏好

### 执行迁移

#### MySQL

```bash
# 进入后端目录
cd backend

# 执行迁移脚本
mysql -u your_user -p your_database < db/migrations/001_add_mcp_plugin_tables.sql

# 验证表创建
mysql -u your_user -p your_database -e "SHOW TABLES LIKE 'mcp%';"
```

#### SQLite

SQLite 版本的迁移脚本：

```sql
-- backend/db/migrations/001_add_mcp_plugin_tables_sqlite.sql

CREATE TABLE IF NOT EXISTS mcp_plugins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    plugin_type VARCHAR(50) NOT NULL DEFAULT 'http',
    server_url VARCHAR(500) NOT NULL,
    headers TEXT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    category VARCHAR(50) NULL,
    config TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_plugin_name ON mcp_plugins(plugin_name);

CREATE TABLE IF NOT EXISTS user_plugin_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plugin_id INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plugin_id) REFERENCES mcp_plugins(id) ON DELETE CASCADE,
    UNIQUE(user_id, plugin_id)
);

CREATE INDEX idx_user_plugin_prefs_user ON user_plugin_preferences(user_id);
CREATE INDEX idx_user_plugin_prefs_plugin ON user_plugin_preferences(plugin_id);
```

执行 SQLite 迁移：

```bash
sqlite3 arboris.db < db/migrations/001_add_mcp_plugin_tables_sqlite.sql
```

### 回滚迁移

如需回滚 MCP 插件表：

```bash
# MySQL
mysql -u your_user -p your_database < db/migrations/001_add_mcp_plugin_tables_rollback.sql

# SQLite
sqlite3 arboris.db "DROP TABLE IF EXISTS user_plugin_preferences; DROP TABLE IF EXISTS mcp_plugins;"
```

---

## MCP 插件系统配置

### 1. 系统配置

MCP 插件系统的核心配置位于 `backend/app/mcp/config.py`：

```python
@dataclass(frozen=True)
class MCPConfig:
    # 连接池配置
    MAX_CLIENTS_PER_USER: int = 5  # 每个用户最大连接数
    CLIENT_TTL_SECONDS: int = 600  # 连接存活时间（秒）
    CLEANUP_INTERVAL_SECONDS: int = 60  # 清理间隔（秒）
    
    # 超时配置
    CONNECTION_TIMEOUT_SECONDS: float = 10.0  # 连接超时
    TOOL_CALL_TIMEOUT_SECONDS: float = 30.0  # 工具调用超时
    
    # 重试配置
    MAX_RETRIES: int = 3  # 最大重试次数
    BASE_RETRY_DELAY_SECONDS: float = 1.0  # 基础重试延迟
    MAX_RETRY_DELAY_SECONDS: float = 10.0  # 最大重试延迟
    
    # 缓存配置
    TOOL_CACHE_TTL_MINUTES: int = 30  # 工具缓存有效期（分钟）
```

**生产环境建议：**

- 根据服务器资源调整 `MAX_CLIENTS_PER_USER`
- 增加 `CLIENT_TTL_SECONDS` 以减少频繁重连
- 根据网络情况调整超时时间

### 2. 配置第一个插件

部署完成后，以管理员身份登录，配置第一个 MCP 插件：

#### 示例：Exa Search

```json
{
  "plugin_name": "exa_search",
  "display_name": "Exa 搜索引擎",
  "plugin_type": "http",
  "server_url": "https://api.exa.ai/mcp",
  "headers": {
    "Authorization": "Bearer YOUR_EXA_API_KEY"
  },
  "category": "search",
  "enabled": true
}
```

**获取 Exa API Key：**
1. 访问 [Exa.ai](https://exa.ai/)
2. 注册并获取 API Key
3. 在插件配置中填入

### 3. 测试插件

配置完成后，使用"测试插件"功能验证：

1. 在插件列表中找到新添加的插件
2. 点击"测试"按钮
3. 查看测试报告，确认连接正常

---

## 环境变量配置

### 核心配置

```bash
# ============================================
# 安全配置
# ============================================
SECRET_KEY=your-super-secret-key-min-32-chars
ADMIN_DEFAULT_PASSWORD=change-this-password

# ============================================
# 数据库配置
# ============================================
DB_PROVIDER=sqlite  # sqlite 或 mysql
DB_HOST=localhost  # MySQL 主机
DB_PORT=3306  # MySQL 端口
DB_USER=arboris  # MySQL 用户名
DB_PASSWORD=your-db-password  # MySQL 密码
DB_NAME=arboris_novel  # 数据库名

# SQLite 数据存储路径（仅 SQLite）
SQLITE_STORAGE_SOURCE=./storage  # 或 Docker 卷名

# ============================================
# AI 服务配置
# ============================================
OPENAI_API_KEY=sk-your-api-key
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-3.5-turbo

# ============================================
# 应用配置
# ============================================
ALLOW_USER_REGISTRATION=false  # 是否允许用户注册
BACKEND_PORT=8000  # 后端端口
FRONTEND_PORT=8080  # 前端端口

# ============================================
# 邮件配置（开启注册时必填）
# ============================================
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com

# ============================================
# MCP 插件系统配置（可选）
# ============================================
# 这些配置在代码中有默认值，通常不需要修改
# 如需自定义，可以添加以下环境变量：

# MCP_MAX_CLIENTS_PER_USER=5
# MCP_CLIENT_TTL_SECONDS=600
# MCP_CONNECTION_TIMEOUT=10.0
# MCP_TOOL_CALL_TIMEOUT=30.0
# MCP_MAX_RETRIES=3
# MCP_TOOL_CACHE_TTL_MINUTES=30
```

### 环境变量优先级

1. 系统环境变量（最高优先级）
2. `.env` 文件
3. 代码中的默认值（最低优先级）

---

## 生产环境优化

### 1. 性能优化

#### 后端优化

```bash
# 使用多个 worker 进程
uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000

# 或使用 Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

#### 数据库优化

```sql
-- MySQL 索引优化
CREATE INDEX idx_novels_user_id ON novels(user_id);
CREATE INDEX idx_chapters_novel_id ON chapters(novel_id);
CREATE INDEX idx_mcp_plugins_enabled ON mcp_plugins(enabled);
CREATE INDEX idx_user_plugin_prefs_enabled ON user_plugin_preferences(enabled);

-- 定期优化表
OPTIMIZE TABLE novels, chapters, mcp_plugins, user_plugin_preferences;
```

#### MCP 连接池优化

根据并发用户数调整连接池大小：

```python
# backend/app/mcp/config.py
MAX_CLIENTS_PER_USER = 10  # 增加到 10
CLIENT_TTL_SECONDS = 1800  # 增加到 30 分钟
```

### 2. 安全加固

#### HTTPS 配置

使用 Nginx + Let's Encrypt：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # SSL 配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # 其他配置...
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

#### 防火墙配置

```bash
# 只开放必要端口
ufw allow 22/tcp  # SSH
ufw allow 80/tcp  # HTTP
ufw allow 443/tcp  # HTTPS
ufw enable
```

#### 密钥管理

```bash
# 生成强密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 定期轮换密钥
# 1. 生成新密钥
# 2. 更新 .env 文件
# 3. 重启服务
```

### 3. 监控和日志

#### 日志配置

```python
# backend/app/core/config.py
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/arboris.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "default"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["file"]
    }
}
```

#### 监控指标

使用 Prometheus + Grafana 监控：

```yaml
# docker-compose.yml 添加监控服务
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### 4. 备份策略

#### 数据库备份

```bash
# MySQL 备份脚本
#!/bin/bash
BACKUP_DIR="/backup/mysql"
DATE=$(date +%Y%m%d_%H%M%S)
mysqldump -u root -p arboris_novel > "$BACKUP_DIR/arboris_$DATE.sql"

# 保留最近 7 天的备份
find $BACKUP_DIR -name "arboris_*.sql" -mtime +7 -delete

# 添加到 crontab
# 0 2 * * * /path/to/backup.sh
```

#### SQLite 备份

```bash
# SQLite 备份脚本
#!/bin/bash
BACKUP_DIR="/backup/sqlite"
DATE=$(date +%Y%m%d_%H%M%S)
cp arboris.db "$BACKUP_DIR/arboris_$DATE.db"

# 保留最近 7 天的备份
find $BACKUP_DIR -name "arboris_*.db" -mtime +7 -delete
```

---

## 故障排查

### 1. 服务无法启动

#### 检查端口占用

```bash
# 检查端口是否被占用
netstat -tuln | grep 8000
lsof -i :8000

# 杀死占用进程
kill -9 <PID>
```

#### 检查日志

```bash
# Docker 日志
docker compose logs -f backend

# 手动部署日志
tail -f logs/arboris.log
```

### 2. 数据库连接失败

#### MySQL 连接问题

```bash
# 测试连接
mysql -h localhost -u arboris -p arboris_novel

# 检查用户权限
mysql -u root -p -e "SHOW GRANTS FOR 'arboris'@'localhost';"

# 授予权限
mysql -u root -p -e "GRANT ALL PRIVILEGES ON arboris_novel.* TO 'arboris'@'localhost';"
```

#### SQLite 权限问题

```bash
# 检查文件权限
ls -la arboris.db

# 修复权限
chmod 644 arboris.db
chown www-data:www-data arboris.db  # 根据运行用户调整
```

### 3. MCP 插件问题

#### 插件连接失败

```bash
# 测试 MCP 服务器连接
curl -v https://api.exa.ai/mcp

# 检查认证
curl -H "Authorization: Bearer YOUR_KEY" https://api.exa.ai/mcp

# 查看 MCP 相关日志
docker compose logs backend | grep "MCP"
```

#### 工具调用失败

1. 检查插件配置是否正确
2. 使用管理界面的"测试插件"功能
3. 查看详细错误日志
4. 验证 API Key 是否有效

### 4. 性能问题

#### 慢查询分析

```sql
-- MySQL 慢查询日志
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';

-- 查看慢查询
SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 10;
```

#### 资源监控

```bash
# CPU 和内存使用
docker stats

# 磁盘使用
df -h
du -sh /var/lib/docker/volumes/*

# 网络连接
netstat -an | grep ESTABLISHED | wc -l
```

---

## 更新和维护

### 更新应用

```bash
# 拉取最新代码
git pull origin main

# 重新构建镜像
docker compose build

# 重启服务
docker compose down
docker compose up -d

# 执行新的数据库迁移（如有）
docker compose exec backend python -c "from app.db.init_db import init_db; import asyncio; asyncio.run(init_db())"
```

### 清理旧数据

```bash
# 清理 Docker 未使用的资源
docker system prune -a

# 清理旧日志
find logs/ -name "*.log" -mtime +30 -delete

# 清理旧备份
find /backup -name "*.sql" -mtime +30 -delete
```

---

## 相关资源

- [项目主页](https://github.com/t59688/arboris-novel)
- [MCP 管理员指南](./MCP_ADMIN_GUIDE.md)
- [问题反馈](https://github.com/t59688/arboris-novel/issues)
- [MCP 官方文档](https://modelcontextprotocol.io/)

---

## 技术支持

如遇到部署问题，请：

1. 查看本文档的故障排查部分
2. 搜索 [GitHub Issues](https://github.com/t59688/arboris-novel/issues)
3. 提交新的 Issue 并附上详细日志
4. 加入社区群组寻求帮助

---

**祝部署顺利！**
