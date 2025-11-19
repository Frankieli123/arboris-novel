# 异步任务系统部署指南

本指南介绍如何部署和配置 Arboris Novel 的异步任务处理系统。

## 概述

异步任务系统包含以下组件：
- **AsyncTask 数据模型**: 存储任务信息的数据库表
- **TaskService**: 任务管理服务层
- **TaskWorker**: 后台任务执行器
- **API 路由**: 任务创建和查询端点

## 前置要求

- Python 3.10+
- MySQL 5.7+ 或 SQLite 3.35+
- 已部署的 Arboris Novel 后端服务
- 配置好的 LLM API（OpenAI 或兼容接口）

---

## 数据库迁移

### 步骤 1: 检查当前数据库版本

```bash
cd backend

# 查看当前迁移状态
alembic current
```

### 步骤 2: 执行迁移

异步任务系统需要创建 `async_tasks` 表。迁移脚本位于 `backend/db/migrations/001_create_async_tasks_table.sql`。

**使用 Alembic (推荐):**

```bash
# 升级到最新版本
alembic upgrade head
```

**手动执行 SQL (如果不使用 Alembic):**

```bash
# MySQL
mysql -u <username> -p <database_name> < db/migrations/001_create_async_tasks_table.sql

# SQLite
sqlite3 <database_file> < db/migrations/001_create_async_tasks_table.sql
```

### 步骤 3: 验证迁移

```bash
# 检查表是否创建成功
# MySQL
mysql -u <username> -p -e "DESCRIBE async_tasks;" <database_name>

# SQLite
sqlite3 <database_file> ".schema async_tasks"
```

预期输出应包含以下字段：
- id (VARCHAR/TEXT, PRIMARY KEY)
- user_id (INTEGER)
- task_type (VARCHAR/TEXT)
- status (VARCHAR/TEXT)
- progress (INTEGER)
- progress_message (TEXT, nullable)
- input_data (JSON/TEXT)
- result_data (JSON/TEXT, nullable)
- error_message (TEXT, nullable)
- retry_count (INTEGER)
- max_retries (INTEGER)
- created_at (DATETIME)
- started_at (DATETIME, nullable)
- completed_at (DATETIME, nullable)
- expires_at (DATETIME)

### 步骤 4: 验证索引

确认以下索引已创建：

```sql
-- 查看索引
SHOW INDEX FROM async_tasks;  -- MySQL
.indexes async_tasks          -- SQLite
```

应该存在的索引：
- `idx_async_tasks_user_status` (user_id, status)
- `idx_async_tasks_status_created` (status, created_at)
- `idx_async_tasks_expires` (expires_at)

---

## 配置项

### 环境变量

在 `.env` 文件中添加或更新以下配置：

```bash
# ============================================
# 异步任务系统配置
# ============================================

# TaskWorker 最大并发数（默认: 3）
# 根据服务器性能和 LLM API 限制调整
TASK_WORKER_MAX_WORKERS=3

# 任务最大执行时间（秒，默认: 600）
# 超过此时间的任务将被标记为超时
TASK_MAX_EXECUTION_TIME=600

# 任务保留天数（默认: 7）
# 完成后的任务保留多少天后自动清理
TASK_RETENTION_DAYS=7

# 任务清理间隔（秒，默认: 3600）
# 多久执行一次过期任务清理
TASK_CLEANUP_INTERVAL=3600

# 任务超时检查间隔（秒，默认: 60）
# 多久检查一次是否有任务超时
TASK_TIMEOUT_CHECK_INTERVAL=60
```

### 配置说明

#### TASK_WORKER_MAX_WORKERS

控制同时执行的任务数量。

**建议值:**
- 小型部署（单用户/测试）: 1-2
- 中型部署（< 100 用户）: 3-5
- 大型部署（> 100 用户）: 5-10

**注意事项:**
- 过高的并发数可能导致 LLM API 限流
- 需要考虑服务器 CPU 和内存资源
- 建议根据实际负载逐步调整

#### TASK_MAX_EXECUTION_TIME

单个任务的最大执行时间。

**建议值:**
- 概念对话: 240 秒
- 蓝图生成: 600 秒
- 章节生成: 600 秒
- 章节评估: 360 秒
- 大纲生成: 360 秒

**注意事项:**
- 设置过短可能导致正常任务超时
- 设置过长会延迟失败任务的检测
- 可以根据使用的 LLM 模型调整

#### TASK_RETENTION_DAYS

任务完成后的保留时间。

**建议值:**
- 开发环境: 1-3 天
- 生产环境: 7-14 天

**注意事项:**
- 保留时间过短可能导致用户无法查看历史任务
- 保留时间过长会占用数据库空间
- 建议定期监控数据库大小

---

## 应用启动配置

### 修改 main.py

确保 `backend/app/main.py` 包含 TaskWorker 初始化代码：

```python
from app.services.task_worker import TaskWorker
from app.services.task_service import TaskService

# 创建 TaskWorker 实例
task_worker = None

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global task_worker
    
    # 初始化数据库
    await init_db()
    
    # 恢复中断的任务
    async with get_session() as session:
        task_service = TaskService(session)
        recovered = await task_service.recover_interrupted_tasks()
        logger.info(f"恢复了 {recovered} 个中断的任务")
    
    # 启动 TaskWorker
    max_workers = settings.task_worker_max_workers
    task_worker = TaskWorker(max_workers=max_workers)
    task_worker.start()
    logger.info(f"TaskWorker 已启动，最大并发数: {max_workers}")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    global task_worker
    
    # 停止 TaskWorker
    if task_worker:
        task_worker.stop()
        logger.info("TaskWorker 已停止")
```

### 验证启动

启动应用后，检查日志确认 TaskWorker 正常启动：

```bash
# 启动应用
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 查看日志
tail -f logs/app.log
```

预期日志输出：
```
INFO: 恢复了 0 个中断的任务
INFO: TaskWorker 已启动，最大并发数: 3
INFO: Application startup complete.
```

---

## Docker 部署

### 使用现有 Docker Compose

项目已包含 Docker Compose 配置，异步任务系统会自动启动。

```bash
# 使用 SQLite
docker compose up -d

# 使用 MySQL
DB_PROVIDER=mysql docker compose --profile mysql up -d
```

### 验证 Docker 部署

```bash
# 查看容器日志
docker compose logs -f backend

# 检查 TaskWorker 状态
docker compose exec backend python -c "
from app.services.task_worker import TaskWorker
print('TaskWorker 可用')
"
```

### Docker 环境变量

在 `deploy/.env` 或 `docker-compose.yml` 中配置：

```yaml
services:
  backend:
    environment:
      - TASK_WORKER_MAX_WORKERS=3
      - TASK_MAX_EXECUTION_TIME=600
      - TASK_RETENTION_DAYS=7
```

---

## 监控和日志

### 日志配置

异步任务系统会记录以下事件：

- 任务创建
- 任务状态变更
- 任务执行错误
- 任务超时
- 任务清理

**日志级别:**
- INFO: 正常操作（任务创建、完成）
- WARNING: 可恢复错误（重试、超时）
- ERROR: 严重错误（任务失败、数据库错误）

**日志位置:**
- 标准输出（Docker）
- `logs/app.log`（本地部署）

### 监控端点

#### 健康检查

```bash
# 检查 TaskWorker 状态
curl http://localhost:8000/api/health/tasks
```

响应示例：
```json
{
  "status": "healthy",
  "worker_running": true,
  "processing_tasks": 2,
  "pending_tasks": 5
}
```

#### 管理员统计

```bash
# 获取任务统计（需要管理员权限）
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/admin/tasks/stats
```

响应示例：
```json
{
  "total_tasks": 150,
  "pending_tasks": 5,
  "processing_tasks": 2,
  "completed_tasks": 130,
  "failed_tasks": 13,
  "avg_execution_time_seconds": 45.2,
  "success_rate_percent": 91.3
}
```

### 监控指标

建议监控以下指标：

1. **任务成功率**: 应保持在 90% 以上
2. **平均执行时间**: 根据任务类型监控
3. **待处理任务数**: 持续增长表示处理能力不足
4. **失败任务数**: 突然增加可能表示 LLM API 问题

---

## 故障排查

### TaskWorker 未启动

**症状:**
- 任务一直处于 pending 状态
- 健康检查显示 `worker_running: false`

**排查步骤:**

1. 检查应用日志
   ```bash
   tail -f logs/app.log | grep TaskWorker
   ```

2. 检查配置
   ```bash
   # 确认环境变量已加载
   python -c "from app.core.config import settings; print(settings.task_worker_max_workers)"
   ```

3. 手动测试
   ```python
   from app.services.task_worker import TaskWorker
   worker = TaskWorker(max_workers=1)
   worker.start()
   # 应该没有错误
   ```

### 任务执行失败

**症状:**
- 任务状态变为 failed
- error_message 包含错误信息

**常见原因和解决方案:**

1. **LLM API 超时**
   - 检查网络连接
   - 增加 `TASK_MAX_EXECUTION_TIME`
   - 检查 LLM API 配置

2. **LLM API 限流**
   - 降低 `TASK_WORKER_MAX_WORKERS`
   - 联系 LLM 服务提供商增加配额

3. **数据库连接失败**
   - 检查数据库连接配置
   - 检查数据库服务状态
   - 查看数据库日志

4. **内存不足**
   - 增加服务器内存
   - 降低并发数
   - 优化任务处理逻辑

### 数据库迁移失败

**症状:**
- 应用启动时报错
- 提示表不存在

**解决方案:**

1. 检查迁移状态
   ```bash
   alembic current
   ```

2. 手动执行迁移
   ```bash
   alembic upgrade head
   ```

3. 如果仍然失败，手动创建表
   ```bash
   mysql -u <user> -p <database> < db/migrations/001_create_async_tasks_table.sql
   ```

### 任务清理不工作

**症状:**
- 过期任务未被清理
- 数据库持续增长

**排查步骤:**

1. 检查清理任务是否运行
   ```bash
   # 查看日志
   grep "清理过期任务" logs/app.log
   ```

2. 手动触发清理
   ```python
   from app.services.task_service import TaskService
   from app.db.session import get_session
   
   async with get_session() as session:
       service = TaskService(session)
       count = await service.cleanup_expired_tasks()
       print(f"清理了 {count} 个任务")
   ```

3. 检查配置
   ```bash
   # 确认保留期限配置
   echo $TASK_RETENTION_DAYS
   ```

---

## 性能优化

### 数据库优化

1. **确保索引存在**
   ```sql
   -- 检查索引
   SHOW INDEX FROM async_tasks;
   
   -- 如果缺失，手动创建
   CREATE INDEX idx_async_tasks_user_status ON async_tasks(user_id, status);
   CREATE INDEX idx_async_tasks_status_created ON async_tasks(status, created_at);
   CREATE INDEX idx_async_tasks_expires ON async_tasks(expires_at);
   ```

2. **定期清理过期任务**
   - 确保 `TASK_RETENTION_DAYS` 设置合理
   - 监控数据库大小
   - 考虑归档历史任务

3. **数据库连接池**
   ```python
   # 在 settings.py 中调整
   SQLALCHEMY_POOL_SIZE = 10
   SQLALCHEMY_MAX_OVERFLOW = 20
   ```

### 应用优化

1. **调整并发数**
   - 根据服务器性能调整 `TASK_WORKER_MAX_WORKERS`
   - 监控 CPU 和内存使用率
   - 避免过度并发导致资源竞争

2. **优化轮询间隔**
   - 前端轮询间隔建议 3-5 秒
   - 避免过于频繁的数据库查询

3. **使用连接池**
   - 确保数据库连接池配置合理
   - 监控连接池使用情况

---

## 升级指南

### 从同步 API 升级到异步 API

如果你的应用当前使用同步 API，按以下步骤升级：

1. **执行数据库迁移**（见上文）

2. **更新后端代码**
   - 代码已更新，无需手动修改

3. **更新前端代码**
   - 使用 `useTaskPolling` composable
   - 集成 `TaskProgressModal` 组件
   - 参见 [前端使用文档](./frontend_task_usage.md)

4. **测试**
   - 测试所有任务类型
   - 验证轮询机制
   - 测试错误处理

5. **逐步迁移**
   - 可以先迁移部分功能
   - 监控错误率和性能
   - 收集用户反馈

---

## 安全考虑

### 任务权限

- 用户只能查询自己的任务
- 管理员可以查询所有任务
- 任务 ID 使用 UUID，难以猜测

### 数据保护

- 敏感数据（如 API Key）不存储在任务记录中
- 任务结果在过期后自动清理
- 建议启用数据库加密

### 速率限制

考虑添加速率限制防止滥用：

```python
# 在 API 路由中添加
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/tasks/...")
@limiter.limit("10/minute")
async def create_task(...):
    ...
```

---

## 备份和恢复

### 备份任务数据

```bash
# MySQL
mysqldump -u <user> -p <database> async_tasks > async_tasks_backup.sql

# SQLite
sqlite3 <database_file> ".dump async_tasks" > async_tasks_backup.sql
```

### 恢复任务数据

```bash
# MySQL
mysql -u <user> -p <database> < async_tasks_backup.sql

# SQLite
sqlite3 <database_file> < async_tasks_backup.sql
```

### 定期备份建议

- 每日备份数据库
- 保留最近 7 天的备份
- 测试恢复流程

---

## 相关文档

- [异步任务 API 文档](./async_task_api.md)
- [管理员监控端点](./admin_task_endpoints.md)
- [前端使用文档](./frontend_task_usage.md)

---

## 支持

如有问题，请：
1. 查看日志文件
2. 检查配置是否正确
3. 参考故障排查部分
4. 在 GitHub 提交 Issue
