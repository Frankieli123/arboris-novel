# 设计文档

## 概述

本设计实现了一个异步任务处理系统，用于解决小说创作平台中长时间运行的LLM操作导致的CDN超时问题（524错误）。系统采用任务队列模式，将耗时操作（如概念对话、蓝图生成、章节生成等）转换为后台异步任务，前端通过轮询机制获取任务状态和结果。

核心设计原则：
- **快速响应**: API立即返回任务ID，不等待操作完成
- **可靠性**: 任务状态持久化到数据库，支持故障恢复
- **简单性**: 使用数据库作为任务队列，避免引入额外的消息队列依赖
- **渐进式迁移**: 保持现有API接口兼容，逐步迁移到异步模式

## 架构

### 系统组件

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Frontend  │────────▶│  FastAPI     │────────▶│  Database   │
│   (Vue.js)  │◀────────│  Backend     │◀────────│  (MySQL)    │
└─────────────┘         └──────────────┘         └─────────────┘
      │                        │                         │
      │ 1. POST /task          │ 2. Create Task          │
      │ ─────────────────────▶ │ ──────────────────────▶ │
      │                        │                         │
      │ 3. Return task_id      │                         │
      │ ◀───────────────────── │                         │
      │                        │                         │
      │ 4. Poll GET /task/{id} │ 5. Query Task           │
      │ ─────────────────────▶ │ ──────────────────────▶ │
      │                        │                         │
      │ 6. Return status       │                         │
      │ ◀───────────────────── │                         │
      │                        │                         │
      │                        ▼                         │
      │                 ┌──────────────┐                 │
      │                 │ Task Worker  │                 │
      │                 │  (Thread)    │                 │
      │                 └──────────────┘                 │
      │                        │                         │
      │                        │ 7. Fetch & Execute      │
      │                        │ ──────────────────────▶ │
      │                        │                         │
      │                        │ 8. Update Status        │
      │                        │ ──────────────────────▶ │
      └────────────────────────┴─────────────────────────┘
```

### 技术栈选择

- **任务队列**: 使用数据库表作为任务队列（简单、可靠、无需额外依赖）
- **任务执行器**: 使用Python线程池（`concurrent.futures.ThreadPoolExecutor`）
- **前端轮询**: 使用Vue 3 Composition API实现可复用的轮询逻辑
- **状态管理**: 使用Pinia store管理任务状态

## 组件和接口

### 1. 数据模型

#### AsyncTask 模型

```python
class AsyncTask(Base):
    """异步任务表"""
    __tablename__ = "async_tasks"
    
    id: Mapped[str]  # UUID
    user_id: Mapped[int]  # 任务所属用户
    task_type: Mapped[str]  # 任务类型: concept_converse, blueprint_generate, chapter_generate等
    status: Mapped[str]  # pending, processing, completed, failed
    progress: Mapped[int]  # 0-100
    progress_message: Mapped[Optional[str]]  # 进度描述
    input_data: Mapped[dict]  # JSON: 任务输入参数
    result_data: Mapped[Optional[dict]]  # JSON: 任务结果
    error_message: Mapped[Optional[str]]  # 错误信息
    retry_count: Mapped[int]  # 重试次数
    max_retries: Mapped[int]  # 最大重试次数
    created_at: Mapped[datetime]
    started_at: Mapped[Optional[datetime]]
    completed_at: Mapped[Optional[datetime]]
    expires_at: Mapped[datetime]  # 任务过期时间
```

### 2. 后端服务层

#### TaskService

```python
class TaskService:
    """任务管理服务"""
    
    async def create_task(
        self,
        user_id: int,
        task_type: str,
        input_data: dict,
        max_retries: int = 3
    ) -> AsyncTask
    
    async def get_task(
        self,
        task_id: str,
        user_id: int
    ) -> AsyncTask
    
    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int = None,
        progress_message: str = None,
        result_data: dict = None,
        error_message: str = None
    ) -> None
    
    async def get_pending_tasks(
        self,
        limit: int = 10
    ) -> List[AsyncTask]
    
    async def cleanup_expired_tasks(self) -> int
```

#### TaskWorker

```python
class TaskWorker:
    """任务执行器"""
    
    def __init__(self, max_workers: int = 3):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
    
    def start(self) -> None:
        """启动任务工作器"""
    
    def stop(self) -> None:
        """停止任务工作器"""
    
    async def process_task(self, task: AsyncTask) -> None:
        """处理单个任务"""
    
    async def _execute_concept_converse(
        self,
        task: AsyncTask
    ) -> dict:
        """执行概念对话任务"""
    
    async def _execute_blueprint_generate(
        self,
        task: AsyncTask
    ) -> dict:
        """执行蓝图生成任务"""
    
    async def _execute_chapter_generate(
        self,
        task: AsyncTask
    ) -> dict:
        """执行章节生成任务"""
```

### 3. API路由

#### 任务管理路由

```python
# POST /api/tasks/concept-converse
async def create_concept_converse_task(
    project_id: str,
    request: ConverseRequest,
    session: AsyncSession,
    current_user: UserInDB
) -> TaskResponse

# POST /api/tasks/blueprint-generate
async def create_blueprint_generate_task(
    project_id: str,
    session: AsyncSession,
    current_user: UserInDB
) -> TaskResponse

# POST /api/tasks/chapter-generate
async def create_chapter_generate_task(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession,
    current_user: UserInDB
) -> TaskResponse

# GET /api/tasks/{task_id}
async def get_task_status(
    task_id: str,
    session: AsyncSession,
    current_user: UserInDB
) -> TaskStatusResponse

# GET /api/tasks
async def list_user_tasks(
    status: Optional[str],
    limit: int,
    session: AsyncSession,
    current_user: UserInDB
) -> List[TaskSummary]
```

### 4. 前端组件

#### useTaskPolling Composable

```typescript
interface UseTaskPollingOptions {
  taskId: string
  interval?: number  // 轮询间隔（毫秒）
  maxAttempts?: number  // 最大轮询次数
  onProgress?: (progress: number, message: string) => void
  onComplete?: (result: any) => void
  onError?: (error: string) => void
}

function useTaskPolling(options: UseTaskPollingOptions) {
  const status = ref<TaskStatus>('pending')
  const progress = ref(0)
  const result = ref(null)
  const error = ref(null)
  
  const startPolling = () => void
  const stopPolling = () => void
  
  return {
    status,
    progress,
    result,
    error,
    startPolling,
    stopPolling
  }
}
```

#### TaskProgressModal 组件

```vue
<template>
  <div class="task-progress-modal">
    <div class="progress-bar">
      <div class="progress-fill" :style="{ width: `${progress}%` }"></div>
    </div>
    <p class="progress-message">{{ progressMessage }}</p>
    <p class="status">{{ statusText }}</p>
  </div>
</template>
```

## 数据模型

### 任务状态流转

```
pending ──▶ processing ──▶ completed
   │            │              
   │            ▼              
   └────────▶ failed ◀─────┘
```

### 任务类型定义

```python
TASK_TYPES = {
    "concept_converse": {
        "handler": "_execute_concept_converse",
        "timeout": 240,
        "max_retries": 2
    },
    "blueprint_generate": {
        "handler": "_execute_blueprint_generate",
        "timeout": 600,
        "max_retries": 2
    },
    "chapter_generate": {
        "handler": "_execute_chapter_generate",
        "timeout": 600,
        "max_retries": 1
    },
    "chapter_evaluate": {
        "handler": "_execute_chapter_evaluate",
        "timeout": 360,
        "max_retries": 2
    },
    "outline_generate": {
        "handler": "_execute_outline_generate",
        "timeout": 360,
        "max_retries": 2
    }
}
```

### 数据库索引策略

```sql
-- 任务查询优化
CREATE INDEX idx_async_tasks_user_status ON async_tasks(user_id, status);
CREATE INDEX idx_async_tasks_status_created ON async_tasks(status, created_at);
CREATE INDEX idx_async_tasks_expires ON async_tasks(expires_at);
```


## 正确性属性

*属性是一个特征或行为，应该在系统的所有有效执行中保持为真——本质上是关于系统应该做什么的正式声明。属性作为人类可读规范和机器可验证正确性保证之间的桥梁。*

### Property 1: 任务创建立即响应
*对于任何*长时间操作请求（概念对话、蓝图生成、章节生成等），API应该在3秒内返回包含任务ID和pending状态的响应
**验证: 需求 1.1, 1.2, 1.4, 1.5**

### Property 2: 任务持久化
*对于任何*创建的任务，数据库中应该存在对应的任务记录，且包含所有必需字段（ID、用户ID、类型、状态、输入数据、创建时间）
**验证: 需求 1.3**

### Property 3: 任务查询权限控制
*对于任何*任务查询请求，如果任务ID不存在应返回404，如果任务不属于请求用户应返回403，否则应返回任务的完整状态信息
**验证: 需求 2.1, 2.2, 2.3**

### Property 4: 任务状态转换正确性
*对于任何*被worker处理的任务，状态应该按照 pending → processing → (completed | failed) 的顺序转换，且每次转换都应持久化到数据库
**验证: 需求 3.1, 3.2, 3.3, 3.4**

### Property 5: 异常处理完整性
*对于任何*在处理过程中抛出异常的任务，系统应该捕获异常，将任务状态设置为failed，并将错误信息保存到error_message字段
**验证: 需求 3.5**

### Property 6: 轮询行为正确性
*对于任何*未完成的任务（pending或processing状态），前端轮询客户端应该持续查询状态，直到任务完成（completed或failed）或达到最大重试次数
**验证: 需求 4.1, 4.2, 4.3, 4.4**

### Property 7: 网络错误重试策略
*对于任何*轮询过程中发生的网络错误，客户端应该使用指数退避策略重试，每次重试的间隔应该是上次的2倍
**验证: 需求 4.5**

### Property 8: 任务超时处理
*对于任何*执行时间超过配置的最大执行时间的任务，系统应该将其标记为超时状态并记录日志
**验证: 需求 5.2**

### Property 9: 故障恢复机制
*对于任何*系统重启事件，所有处于processing状态的任务应该被重置为pending状态，以便重新处理
**验证: 需求 5.3, 8.3**

### Property 10: 任务清理机制
*对于任何*完成时间超过保留期限（默认7天）的任务，清理程序应该将其从数据库中删除
**验证: 需求 5.4**

### Property 11: 并发控制
*对于任何*时刻，TaskWorker同时执行的任务数量不应超过配置的最大并发数（默认3）
**验证: 需求 5.5**

### Property 12: 进度信息完整性
*对于任何*处于processing状态的任务，查询其状态应该返回当前的进度百分比（0-100）和进度描述信息
**验证: 需求 6.1, 6.2, 6.3**

### Property 13: 错误消息用户友好性
*对于任何*失败的任务，error_message字段应该包含用户友好的错误描述，而不是技术性的堆栈跟踪
**验证: 需求 6.5**

### Property 14: API异步迁移一致性
*对于任何*长时间操作的API端点（概念对话、蓝图生成、章节生成、章节评估、大纲生成），调用后应该立即返回任务ID，而不是等待操作完成
**验证: 需求 7.1, 7.2, 7.3, 7.4, 7.5**

### Property 15: 任务重试机制
*对于任何*配置了重试策略的失败任务，系统应该自动重试，直到成功或达到最大重试次数（max_retries）
**验证: 需求 8.1, 8.2**

### Property 16: 数据库故障恢复
*对于任何*数据库连接失败事件，系统应该记录错误日志，并在连接恢复后继续处理待处理的任务
**验证: 需求 8.4**

### Property 17: 优雅关闭
*对于任何*系统关闭信号，TaskWorker应该停止接受新任务，等待当前任务完成或超时，并保存所有任务的当前状态
**验证: 需求 8.5**

## 错误处理

### 错误类型

1. **任务创建错误**
   - 无效的输入参数: 返回400 Bad Request
   - 用户权限不足: 返回403 Forbidden
   - 数据库写入失败: 返回500 Internal Server Error

2. **任务查询错误**
   - 任务不存在: 返回404 Not Found
   - 无权访问任务: 返回403 Forbidden

3. **任务执行错误**
   - LLM API调用失败: 标记任务为failed，记录错误信息
   - 超时: 标记任务为failed，错误信息为"任务执行超时"
   - 数据库操作失败: 记录日志，根据重试策略决定是否重试

4. **前端轮询错误**
   - 网络错误: 使用指数退避重试
   - 超过最大轮询次数: 显示超时提示，停止轮询

### 错误恢复策略

```python
ERROR_RECOVERY_STRATEGIES = {
    "llm_api_timeout": {
        "retry": True,
        "max_retries": 2,
        "backoff_factor": 2
    },
    "llm_api_error": {
        "retry": True,
        "max_retries": 3,
        "backoff_factor": 1.5
    },
    "database_error": {
        "retry": True,
        "max_retries": 5,
        "backoff_factor": 2
    },
    "validation_error": {
        "retry": False,
        "user_message": "输入参数不正确，请检查后重试"
    }
}
```

### 日志记录

所有错误都应该记录到日志系统，包含以下信息：
- 任务ID
- 用户ID
- 错误类型
- 错误消息
- 堆栈跟踪（仅用于调试）
- 时间戳

## 测试策略

### 单元测试

1. **TaskService测试**
   - 测试任务创建、查询、更新功能
   - 测试权限验证逻辑
   - 测试任务清理功能

2. **TaskWorker测试**
   - 测试任务获取和执行流程
   - 测试状态转换逻辑
   - 测试错误处理和重试机制
   - 测试并发控制

3. **API路由测试**
   - 测试各个端点的请求和响应
   - 测试认证和授权
   - 测试错误响应

4. **前端组件测试**
   - 测试useTaskPolling composable的轮询逻辑
   - 测试TaskProgressModal组件的渲染
   - 测试错误处理和用户反馈

### 属性测试

使用pytest和hypothesis库进行属性测试：

1. **Property 1-2测试**: 生成随机任务创建请求，验证响应时间和数据持久化
2. **Property 3测试**: 生成随机任务ID和用户ID组合，验证权限控制
3. **Property 4-5测试**: 模拟任务执行流程，验证状态转换和异常处理
4. **Property 6-7测试**: 模拟轮询场景，验证轮询行为和重试策略
5. **Property 8-11测试**: 测试超时、故障恢复、清理和并发控制
6. **Property 12-13测试**: 验证进度信息和错误消息的格式
7. **Property 14-17测试**: 测试API迁移、重试机制和优雅关闭

### 集成测试

1. **端到端任务流程测试**
   - 创建任务 → 任务执行 → 前端轮询 → 获取结果
   - 测试所有任务类型（概念对话、蓝图生成等）

2. **故障场景测试**
   - 模拟数据库连接失败
   - 模拟LLM API超时
   - 模拟系统重启

3. **性能测试**
   - 并发创建大量任务
   - 测试系统在高负载下的表现
   - 验证响应时间符合要求

### 测试工具和框架

- **后端**: pytest, pytest-asyncio, hypothesis, pytest-mock
- **前端**: Vitest, @vue/test-utils, msw (Mock Service Worker)
- **集成测试**: pytest, httpx, docker-compose（用于测试环境）

### 测试覆盖率目标

- 单元测试覆盖率: ≥ 80%
- 属性测试: 每个属性至少100次随机测试
- 集成测试: 覆盖所有主要用户流程
