# Admin Task Monitoring Endpoints

This document describes the admin-only endpoints for monitoring and managing async tasks.

## Authentication

All endpoints require admin authentication. Include the admin JWT token in the Authorization header:

```
Authorization: Bearer <admin_token>
```

## Endpoints

### GET /api/admin/tasks/stats

Get comprehensive task statistics including counts by status, task type distribution, and performance metrics.

**Query Parameters:**
- `time_window_hours` (optional, default: 24): Time window in hours for performance metrics

**Response:**
```json
{
  "total_tasks": 150,
  "pending_tasks": 5,
  "processing_tasks": 2,
  "completed_tasks": 130,
  "failed_tasks": 13,
  "tasks_by_type": {
    "concept_converse": 45,
    "blueprint_generate": 30,
    "chapter_generate": 50,
    "chapter_evaluate": 15,
    "outline_generate": 10
  },
  "avg_execution_time_seconds": 45.2,
  "success_rate_percent": 91.3,
  "avg_waiting_time_seconds": 2.5
}
```

**Example:**
```bash
curl -X GET "http://localhost:8000/api/admin/tasks/stats?time_window_hours=24" \
  -H "Authorization: Bearer <admin_token>"
```

### GET /api/admin/tasks

Get a list of all tasks with optional filtering.

**Query Parameters:**
- `status` (optional): Filter by task status (pending, processing, completed, failed)
- `task_type` (optional): Filter by task type
- `limit` (optional, default: 100): Maximum number of tasks to return
- `offset` (optional, default: 0): Offset for pagination

**Response:**
```json
[
  {
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": 1,
    "task_type": "chapter_generate",
    "status": "completed",
    "progress": 100,
    "created_at": "2025-11-19T10:30:00Z",
    "started_at": "2025-11-19T10:30:05Z",
    "completed_at": "2025-11-19T10:31:20Z",
    "error_message": null
  },
  {
    "task_id": "660e8400-e29b-41d4-a716-446655440001",
    "user_id": 2,
    "task_type": "blueprint_generate",
    "status": "failed",
    "progress": 50,
    "created_at": "2025-11-19T10:25:00Z",
    "started_at": "2025-11-19T10:25:03Z",
    "completed_at": "2025-11-19T10:26:15Z",
    "error_message": "LLM API timeout"
  }
]
```

**Examples:**

Get all pending tasks:
```bash
curl -X GET "http://localhost:8000/api/admin/tasks?status=pending" \
  -H "Authorization: Bearer <admin_token>"
```

Get all chapter generation tasks:
```bash
curl -X GET "http://localhost:8000/api/admin/tasks?task_type=chapter_generate" \
  -H "Authorization: Bearer <admin_token>"
```

Get tasks with pagination:
```bash
curl -X GET "http://localhost:8000/api/admin/tasks?limit=50&offset=100" \
  -H "Authorization: Bearer <admin_token>"
```

## Error Responses

### 401 Unauthorized
Returned when no valid authentication token is provided.

```json
{
  "detail": "无效的凭证"
}
```

### 403 Forbidden
Returned when the authenticated user is not an admin.

```json
{
  "detail": "需要管理员权限"
}
```

## Use Cases

### Monitoring System Health
Use the stats endpoint to monitor overall system health and identify issues:
- High failure rate indicates problems with LLM API or system configuration
- Long average execution times may indicate performance issues
- Long average waiting times suggest the need for more workers

### Debugging Failed Tasks
Use the tasks list endpoint with `status=failed` to identify and debug failed tasks:
```bash
curl -X GET "http://localhost:8000/api/admin/tasks?status=failed&limit=20" \
  -H "Authorization: Bearer <admin_token>"
```

### User Support
When a user reports issues, use the tasks endpoint filtered by user_id to investigate their specific tasks.

### Performance Analysis
Use the stats endpoint with different time windows to analyze performance trends:
```bash
# Last hour
curl -X GET "http://localhost:8000/api/admin/tasks/stats?time_window_hours=1" \
  -H "Authorization: Bearer <admin_token>"

# Last 24 hours
curl -X GET "http://localhost:8000/api/admin/tasks/stats?time_window_hours=24" \
  -H "Authorization: Bearer <admin_token>"

# Last week
curl -X GET "http://localhost:8000/api/admin/tasks/stats?time_window_hours=168" \
  -H "Authorization: Bearer <admin_token>"
```
