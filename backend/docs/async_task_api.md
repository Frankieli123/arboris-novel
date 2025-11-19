# 异步任务 API 文档

本文档描述了 Arboris Novel 平台的异步任务处理系统 API。该系统用于处理长时间运行的操作（如 LLM 生成任务），避免 CDN 超时问题。

## 概述

异步任务系统采用任务队列模式：
1. 客户端发起请求，立即收到任务 ID
2. 任务在后台异步执行
3. 客户端通过轮询查询任务状态和结果

## 认证

所有端点都需要用户认证。在请求头中包含 JWT token：

```
Authorization: Bearer <user_token>
```

## 任务状态

任务可能处于以下状态之一：

- `pending`: 待处理，任务已创建但尚未开始执行
- `processing`: 处理中，任务正在执行
- `completed`: 已完成，任务成功完成
- `failed`: 失败，任务执行失败

## 任务类型

系统支持以下任务类型：

- `concept_converse`: 概念对话
- `blueprint_generate`: 蓝图生成
- `chapter_generate`: 章节生成
- `chapter_evaluate`: 章节评估
- `outline_generate`: 大纲生成

---

## API 端点

### 1. 创建概念对话任务

创建一个概念对话任务，用于与 AI 讨论小说创意。

**端点:** `POST /api/novels/{project_id}/concept/converse`

**路径参数:**
- `project_id` (string): 小说项目 ID

**请求体:**
```json
{
  "message": "我想写一个关于时间旅行的科幻小说"
}
```

**响应:** (200 OK)
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2025-11-19T10:30:00Z"
}
```

**示例:**
```bash
curl -X POST "http://localhost:8000/api/novels/123/concept/converse" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "我想写一个关于时间旅行的科幻小说"}'
```

---

### 2. 创建蓝图生成任务

创建一个蓝图生成任务，基于概念对话生成小说蓝图。

**端点:** `POST /api/novels/{project_id}/blueprint/generate`

**路径参数:**
- `project_id` (string): 小说项目 ID

**请求体:** 无

**响应:** (200 OK)
```json
{
  "task_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "pending",
  "created_at": "2025-11-19T10:31:00Z"
}
```

**示例:**
```bash
curl -X POST "http://localhost:8000/api/novels/123/blueprint/generate" \
  -H "Authorization: Bearer <token>"
```

---

### 3. 创建章节生成任务

创建一个章节生成任务，根据大纲生成章节内容。

**端点:** `POST /api/writer/novels/{project_id}/chapters/generate`

**路径参数:**
- `project_id` (string): 小说项目 ID

**请求体:**
```json
{
  "chapter_number": 1,
  "regenerate": false
}
```

**字段说明:**
- `chapter_number` (integer): 章节编号
- `regenerate` (boolean, 可选): 是否重新生成已存在的章节，默认 false

**响应:** (200 OK)
```json
{
  "task_id": "770e8400-e29b-41d4-a716-446655440002",
  "status": "pending",
  "created_at": "2025-11-19T10:32:00Z"
}
```

**示例:**
```bash
curl -X POST "http://localhost:8000/api/writer/novels/123/chapters/generate" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"chapter_number": 1, "regenerate": false}'
```

---

### 4. 创建章节评估任务

创建一个章节评估任务，对已生成的章节进行质量评估。

**端点:** `POST /api/writer/novels/{project_id}/chapters/evaluate`

**路径参数:**
- `project_id` (string): 小说项目 ID

**请求体:**
```json
{
  "chapter_number": 1,
  "version_id": "v1"
}
```

**字段说明:**
- `chapter_number` (integer): 章节编号
- `version_id` (string): 版本 ID

**响应:** (200 OK)
```json
{
  "task_id": "880e8400-e29b-41d4-a716-446655440003",
  "status": "pending",
  "created_at": "2025-11-19T10:33:00Z"
}
```

**示例:**
```bash
curl -X POST "http://localhost:8000/api/writer/novels/123/chapters/evaluate" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"chapter_number": 1, "version_id": "v1"}'
```

---

### 5. 创建大纲生成任务

创建一个大纲生成任务，为章节生成详细大纲。

**端点:** `POST /api/writer/novels/{project_id}/chapters/outline`

**路径参数:**
- `project_id` (string): 小说项目 ID

**请求体:**
```json
{
  "chapter_number": 1
}
```

**字段说明:**
- `chapter_number` (integer): 章节编号

**响应:** (200 OK)
```json
{
  "task_id": "990e8400-e29b-41d4-a716-446655440004",
  "status": "pending",
  "created_at": "2025-11-19T10:34:00Z"
}
```

**示例:**
```bash
curl -X POST "http://localhost:8000/api/writer/novels/123/chapters/outline" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"chapter_number": 1}'
```

---

### 6. 查询任务状态

查询指定任务的当前状态、进度和结果。

**端点:** `GET /api/tasks/{task_id}`

**路径参数:**
- `task_id` (string): 任务 ID

**响应:** (200 OK)

**任务进行中:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "progress_message": "正在生成章节内容...",
  "created_at": "2025-11-19T10:30:00Z",
  "started_at": "2025-11-19T10:30:05Z"
}
```

**任务完成:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "progress_message": "任务完成",
  "result": {
    "content": "生成的章节内容...",
    "metadata": {}
  },
  "created_at": "2025-11-19T10:30:00Z",
  "started_at": "2025-11-19T10:30:05Z",
  "completed_at": "2025-11-19T10:31:20Z"
}
```

**任务失败:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "progress": 50,
  "progress_message": "任务执行失败",
  "error_message": "LLM API 超时，请稍后重试",
  "created_at": "2025-11-19T10:30:00Z",
  "started_at": "2025-11-19T10:30:05Z",
  "completed_at": "2025-11-19T10:31:20Z"
}
```

**示例:**
```bash
curl -X GET "http://localhost:8000/api/tasks/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <token>"
```

---

### 7. 查询用户任务列表

查询当前用户的任务列表，支持按状态过滤和分页。

**端点:** `GET /api/tasks`

**查询参数:**
- `status` (string, 可选): 按状态过滤 (pending, processing, completed, failed)
- `limit` (integer, 可选, 默认: 50): 返回的最大任务数
- `offset` (integer, 可选, 默认: 0): 分页偏移量

**响应:** (200 OK)
```json
[
  {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "task_type": "chapter_generate",
    "status": "completed",
    "progress": 100,
    "created_at": "2025-11-19T10:30:00Z"
  },
  {
    "task_id": "660e8400-e29b-41d4-a716-446655440001",
    "task_type": "blueprint_generate",
    "status": "processing",
    "progress": 60,
    "created_at": "2025-11-19T10:31:00Z"
  }
]
```

**示例:**

查询所有任务:
```bash
curl -X GET "http://localhost:8000/api/tasks" \
  -H "Authorization: Bearer <token>"
```

查询进行中的任务:
```bash
curl -X GET "http://localhost:8000/api/tasks?status=processing" \
  -H "Authorization: Bearer <token>"
```

分页查询:
```bash
curl -X GET "http://localhost:8000/api/tasks?limit=20&offset=40" \
  -H "Authorization: Bearer <token>"
```

---

## 错误响应

### 400 Bad Request
请求参数无效。

```json
{
  "detail": "无效的章节编号"
}
```

### 401 Unauthorized
未提供有效的认证 token。

```json
{
  "detail": "无效的凭证"
}
```

### 403 Forbidden
用户无权访问该任务。

```json
{
  "detail": "无权访问该任务"
}
```

### 404 Not Found
任务不存在。

```json
{
  "detail": "任务不存在"
}
```

### 500 Internal Server Error
服务器内部错误。

```json
{
  "detail": "服务器内部错误，请稍后重试"
}
```

---

## 使用流程

### 典型工作流程

1. **创建任务**
   ```bash
   # 发起章节生成请求
   response=$(curl -X POST "http://localhost:8000/api/writer/novels/123/chapters/generate" \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"chapter_number": 1}')
   
   # 提取 task_id
   task_id=$(echo $response | jq -r '.task_id')
   ```

2. **轮询任务状态**
   ```bash
   # 每 3 秒查询一次任务状态
   while true; do
     status=$(curl -s -X GET "http://localhost:8000/api/tasks/$task_id" \
       -H "Authorization: Bearer <token>" | jq -r '.status')
     
     if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
       break
     fi
     
     sleep 3
   done
   ```

3. **获取结果**
   ```bash
   # 任务完成后获取完整结果
   curl -X GET "http://localhost:8000/api/tasks/$task_id" \
     -H "Authorization: Bearer <token>" | jq '.result'
   ```

### 前端集成示例

参见 [前端使用文档](./frontend_task_usage.md) 了解如何在 Vue.js 应用中集成异步任务。

---

## 性能和限制

### 任务执行时间

不同任务类型的典型执行时间：

| 任务类型 | 典型执行时间 | 最大超时时间 |
|---------|------------|------------|
| concept_converse | 30-60 秒 | 240 秒 |
| blueprint_generate | 60-120 秒 | 600 秒 |
| chapter_generate | 120-300 秒 | 600 秒 |
| chapter_evaluate | 30-90 秒 | 360 秒 |
| outline_generate | 30-90 秒 | 360 秒 |

### 并发限制

- 系统默认最多同时处理 3 个任务
- 超出限制的任务会在队列中等待
- 管理员可以通过配置调整并发数

### 任务保留期限

- 已完成的任务保留 7 天
- 过期任务会被自动清理
- 建议及时获取任务结果

### 轮询建议

- 推荐轮询间隔: 2-5 秒
- 避免过于频繁的轮询（< 1 秒）
- 设置合理的最大轮询次数（建议 200 次）

---

## 故障排查

### 任务一直处于 pending 状态

**可能原因:**
- TaskWorker 未启动
- 数据库连接问题
- 系统资源不足

**解决方案:**
- 检查后端日志
- 确认 TaskWorker 正在运行
- 联系管理员

### 任务失败并显示超时错误

**可能原因:**
- LLM API 响应慢
- 网络连接问题
- 任务执行时间超过限制

**解决方案:**
- 重试任务
- 检查 LLM API 配置
- 联系管理员调整超时设置

### 无法查询任务状态

**可能原因:**
- 任务 ID 错误
- 任务已过期被清理
- 权限问题

**解决方案:**
- 确认任务 ID 正确
- 检查任务是否属于当前用户
- 及时保存任务结果

---

## 相关文档

- [管理员监控端点](./admin_task_endpoints.md)
- [前端使用文档](./frontend_task_usage.md)
- [部署指南](./deployment_guide.md)
