# 前端异步任务使用文档

本文档介绍如何在 Vue.js 前端应用中使用异步任务系统。

## 概述

前端异步任务系统提供了：
- **useTaskPolling** composable: 可复用的任务轮询逻辑
- **TaskProgressModal** 组件: 任务进度显示组件
- **任务 API 客户端**: 封装的 API 调用方法

---

## 快速开始

### 基本使用示例

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useTaskPolling } from '@/composables/useTaskPolling'
import TaskProgressModal from '@/components/TaskProgressModal.vue'
import { NovelAPI } from '@/api/novel'

const showProgress = ref(false)
const taskPolling = useTaskPolling()

async function generateChapter() {
  try {
    // 1. 创建任务
    const response = await NovelAPI.generateChapter(projectId, {
      chapter_number: 1
    })
    
    // 2. 显示进度模态框
    showProgress.value = true
    
    // 3. 开始轮询
    await taskPolling.startPolling({
      taskId: response.task_id,
      onComplete: (result) => {
        // 任务完成，处理结果
        console.log('章节生成完成:', result)
        showProgress.value = false
        // 更新 UI
      },
      onError: (error) => {
        // 任务失败，显示错误
        console.error('生成失败:', error)
        showProgress.value = false
        alert(`生成失败: ${error}`)
      }
    })
  } catch (error) {
    console.error('创建任务失败:', error)
    alert('创建任务失败，请重试')
  }
}
</script>

<template>
  <div>
    <button @click="generateChapter">生成章节</button>
    
    <TaskProgressModal
      v-if="showProgress"
      :status="taskPolling.status.value"
      :progress="taskPolling.progress.value"
      :message="taskPolling.progressMessage.value"
      @close="showProgress = false"
    />
  </div>
</template>
```

---

## useTaskPolling Composable

### 导入

```typescript
import { useTaskPolling } from '@/composables/useTaskPolling'
```

### API

#### startPolling(options)

开始轮询任务状态。

**参数:**

```typescript
interface TaskPollingOptions {
  taskId: string                                    // 任务 ID
  interval?: number                                 // 轮询间隔（毫秒），默认 3000
  maxAttempts?: number                              // 最大轮询次数，默认 200
  onProgress?: (progress: number, message: string) => void  // 进度更新回调
  onComplete?: (result: any) => void                // 任务完成回调
  onError?: (error: string) => void                 // 任务失败回调
}
```

**返回值:**

```typescript
Promise<void>
```

**示例:**

```typescript
const taskPolling = useTaskPolling()

await taskPolling.startPolling({
  taskId: 'task-uuid',
  interval: 3000,
  maxAttempts: 200,
  onProgress: (progress, message) => {
    console.log(`进度: ${progress}% - ${message}`)
  },
  onComplete: (result) => {
    console.log('完成:', result)
  },
  onError: (error) => {
    console.error('失败:', error)
  }
})
```

#### stopPolling()

停止轮询。

```typescript
taskPolling.stopPolling()
```

### 响应式状态

```typescript
const taskPolling = useTaskPolling()

// 任务状态: 'pending' | 'processing' | 'completed' | 'failed'
taskPolling.status.value

// 进度百分比: 0-100
taskPolling.progress.value

// 进度消息
taskPolling.progressMessage.value

// 任务结果（完成后）
taskPolling.result.value

// 错误消息（失败后）
taskPolling.error.value

// 是否正在轮询
taskPolling.isPolling.value
```

---

## TaskProgressModal 组件

### 导入

```typescript
import TaskProgressModal from '@/components/TaskProgressModal.vue'
```

### Props

```typescript
interface Props {
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number        // 0-100
  message?: string        // 进度消息
  showClose?: boolean     // 是否显示关闭按钮，默认 false
}
```

### Events

```typescript
// 用户点击关闭按钮
@close
```

### 使用示例

```vue
<template>
  <TaskProgressModal
    :status="taskStatus"
    :progress="taskProgress"
    :message="taskMessage"
    :show-close="false"
    @close="handleClose"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TaskProgressModal from '@/components/TaskProgressModal.vue'

const taskStatus = ref<'pending' | 'processing' | 'completed' | 'failed'>('pending')
const taskProgress = ref(0)
const taskMessage = ref('正在准备...')

function handleClose() {
  // 处理关闭事件
}
</script>
```

---

## 任务 API 客户端

### 导入

```typescript
import { TaskAPI } from '@/api/tasks'
```

### 方法

#### getTaskStatus(taskId)

查询任务状态。

```typescript
const status = await TaskAPI.getTaskStatus('task-uuid')

console.log(status)
// {
//   task_id: 'task-uuid',
//   status: 'processing',
//   progress: 45,
//   progress_message: '正在生成章节内容...',
//   created_at: '2025-11-19T10:30:00Z',
//   started_at: '2025-11-19T10:30:05Z'
// }
```

#### listTasks(params)

查询任务列表。

```typescript
const tasks = await TaskAPI.listTasks({
  status: 'completed',
  limit: 20,
  offset: 0
})

console.log(tasks)
// [
//   {
//     task_id: 'task-uuid-1',
//     task_type: 'chapter_generate',
//     status: 'completed',
//     progress: 100,
//     created_at: '2025-11-19T10:30:00Z'
//   },
//   ...
// ]
```

---

## 完整集成示例

### InspirationMode.vue

概念对话和蓝图生成的完整示例。

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTaskPolling } from '@/composables/useTaskPolling'
import TaskProgressModal from '@/components/TaskProgressModal.vue'
import { NovelAPI } from '@/api/novel'
import { useNovelStore } from '@/stores/novel'

const route = useRoute()
const novelStore = useNovelStore()
const projectId = computed(() => route.params.id as string)

// 对话相关
const userMessage = ref('')
const conversationHistory = ref<Array<{role: string, content: string}>>([])
const isConversing = ref(false)
const conversePolling = useTaskPolling()

// 蓝图生成相关
const isGeneratingBlueprint = ref(false)
const blueprintPolling = useTaskPolling()

// 发送对话消息
async function sendMessage() {
  if (!userMessage.value.trim()) return
  
  const message = userMessage.value
  userMessage.value = ''
  
  // 添加用户消息到历史
  conversationHistory.value.push({
    role: 'user',
    content: message
  })
  
  try {
    isConversing.value = true
    
    // 创建对话任务
    const response = await NovelAPI.converseConcept(projectId.value, {
      message
    })
    
    // 开始轮询
    await conversePolling.startPolling({
      taskId: response.task_id,
      onProgress: (progress, msg) => {
        console.log(`对话进度: ${progress}% - ${msg}`)
      },
      onComplete: (result) => {
        // 添加 AI 回复到历史
        conversationHistory.value.push({
          role: 'assistant',
          content: result.response
        })
        isConversing.value = false
      },
      onError: (error) => {
        console.error('对话失败:', error)
        alert(`对话失败: ${error}`)
        isConversing.value = false
      }
    })
  } catch (error) {
    console.error('创建对话任务失败:', error)
    alert('发送消息失败，请重试')
    isConversing.value = false
  }
}

// 生成蓝图
async function generateBlueprint() {
  try {
    isGeneratingBlueprint.value = true
    
    // 创建蓝图生成任务
    const response = await NovelAPI.generateBlueprint(projectId.value)
    
    // 开始轮询
    await blueprintPolling.startPolling({
      taskId: response.task_id,
      onProgress: (progress, msg) => {
        console.log(`蓝图生成进度: ${progress}% - ${msg}`)
      },
      onComplete: (result) => {
        // 更新 store 中的蓝图数据
        novelStore.updateBlueprint(projectId.value, result.blueprint)
        isGeneratingBlueprint.value = false
        alert('蓝图生成成功！')
      },
      onError: (error) => {
        console.error('蓝图生成失败:', error)
        alert(`蓝图生成失败: ${error}`)
        isGeneratingBlueprint.value = false
      }
    })
  } catch (error) {
    console.error('创建蓝图任务失败:', error)
    alert('创建任务失败，请重试')
    isGeneratingBlueprint.value = false
  }
}
</script>

<template>
  <div class="inspiration-mode">
    <!-- 对话历史 -->
    <div class="conversation-history">
      <div
        v-for="(msg, index) in conversationHistory"
        :key="index"
        :class="['message', msg.role]"
      >
        {{ msg.content }}
      </div>
    </div>
    
    <!-- 输入框 -->
    <div class="input-area">
      <input
        v-model="userMessage"
        placeholder="输入你的想法..."
        @keyup.enter="sendMessage"
        :disabled="isConversing"
      />
      <button @click="sendMessage" :disabled="isConversing">
        发送
      </button>
    </div>
    
    <!-- 生成蓝图按钮 -->
    <button
      @click="generateBlueprint"
      :disabled="isGeneratingBlueprint || conversationHistory.length === 0"
    >
      生成蓝图
    </button>
    
    <!-- 对话进度模态框 -->
    <TaskProgressModal
      v-if="isConversing"
      :status="conversePolling.status.value"
      :progress="conversePolling.progress.value"
      :message="conversePolling.progressMessage.value"
    />
    
    <!-- 蓝图生成进度模态框 -->
    <TaskProgressModal
      v-if="isGeneratingBlueprint"
      :status="blueprintPolling.status.value"
      :progress="blueprintPolling.progress.value"
      :message="blueprintPolling.progressMessage.value"
    />
  </div>
</template>
```

### WritingDesk.vue

章节生成、评估和大纲生成的完整示例。

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTaskPolling } from '@/composables/useTaskPolling'
import TaskProgressModal from '@/components/TaskProgressModal.vue'
import { NovelAPI } from '@/api/novel'
import { useNovelStore } from '@/stores/novel'

const route = useRoute()
const novelStore = useNovelStore()
const projectId = computed(() => route.params.id as string)

// 章节生成
const isGeneratingChapter = ref(false)
const chapterPolling = useTaskPolling()

// 章节评估
const isEvaluatingChapter = ref(false)
const evaluatePolling = useTaskPolling()

// 大纲生成
const isGeneratingOutline = ref(false)
const outlinePolling = useTaskPolling()

// 生成章节
async function generateChapter(chapterNumber: number) {
  try {
    isGeneratingChapter.value = true
    
    const response = await NovelAPI.generateChapter(projectId.value, {
      chapter_number: chapterNumber,
      regenerate: false
    })
    
    await chapterPolling.startPolling({
      taskId: response.task_id,
      onProgress: (progress, msg) => {
        console.log(`章节生成进度: ${progress}% - ${msg}`)
      },
      onComplete: (result) => {
        // 更新章节数据
        novelStore.updateChapter(projectId.value, chapterNumber, result.chapter)
        isGeneratingChapter.value = false
        alert('章节生成成功！')
      },
      onError: (error) => {
        console.error('章节生成失败:', error)
        alert(`章节生成失败: ${error}`)
        isGeneratingChapter.value = false
      }
    })
  } catch (error) {
    console.error('创建章节任务失败:', error)
    alert('创建任务失败，请重试')
    isGeneratingChapter.value = false
  }
}

// 评估章节
async function evaluateChapter(chapterNumber: number, versionId: string) {
  try {
    isEvaluatingChapter.value = true
    
    const response = await NovelAPI.evaluateChapter(projectId.value, {
      chapter_number: chapterNumber,
      version_id: versionId
    })
    
    await evaluatePolling.startPolling({
      taskId: response.task_id,
      onProgress: (progress, msg) => {
        console.log(`评估进度: ${progress}% - ${msg}`)
      },
      onComplete: (result) => {
        // 显示评估结果
        console.log('评估结果:', result.evaluation)
        isEvaluatingChapter.value = false
        // 可以打开评估结果模态框
      },
      onError: (error) => {
        console.error('评估失败:', error)
        alert(`评估失败: ${error}`)
        isEvaluatingChapter.value = false
      }
    })
  } catch (error) {
    console.error('创建评估任务失败:', error)
    alert('创建任务失败，请重试')
    isEvaluatingChapter.value = false
  }
}

// 生成大纲
async function generateOutline(chapterNumber: number) {
  try {
    isGeneratingOutline.value = true
    
    const response = await NovelAPI.generateChapterOutline(projectId.value, {
      chapter_number: chapterNumber
    })
    
    await outlinePolling.startPolling({
      taskId: response.task_id,
      onProgress: (progress, msg) => {
        console.log(`大纲生成进度: ${progress}% - ${msg}`)
      },
      onComplete: (result) => {
        // 更新大纲数据
        novelStore.updateChapterOutline(projectId.value, chapterNumber, result.outline)
        isGeneratingOutline.value = false
        alert('大纲生成成功！')
      },
      onError: (error) => {
        console.error('大纲生成失败:', error)
        alert(`大纲生成失败: ${error}`)
        isGeneratingOutline.value = false
      }
    })
  } catch (error) {
    console.error('创建大纲任务失败:', error)
    alert('创建任务失败，请重试')
    isGeneratingOutline.value = false
  }
}
</script>

<template>
  <div class="writing-desk">
    <!-- 章节列表和操作按钮 -->
    <div class="chapter-list">
      <div v-for="chapter in chapters" :key="chapter.number">
        <h3>第 {{ chapter.number }} 章</h3>
        <button @click="generateChapter(chapter.number)">
          生成章节
        </button>
        <button @click="evaluateChapter(chapter.number, 'v1')">
          评估章节
        </button>
        <button @click="generateOutline(chapter.number)">
          生成大纲
        </button>
      </div>
    </div>
    
    <!-- 进度模态框 -->
    <TaskProgressModal
      v-if="isGeneratingChapter"
      :status="chapterPolling.status.value"
      :progress="chapterPolling.progress.value"
      :message="chapterPolling.progressMessage.value"
    />
    
    <TaskProgressModal
      v-if="isEvaluatingChapter"
      :status="evaluatePolling.status.value"
      :progress="evaluatePolling.progress.value"
      :message="evaluatePolling.progressMessage.value"
    />
    
    <TaskProgressModal
      v-if="isGeneratingOutline"
      :status="outlinePolling.status.value"
      :progress="outlinePolling.progress.value"
      :message="outlinePolling.progressMessage.value"
    />
  </div>
</template>
```

---

## 错误处理

### 网络错误

```typescript
try {
  await taskPolling.startPolling({
    taskId: 'task-uuid',
    onError: (error) => {
      // 处理任务执行错误
      if (error.includes('超时')) {
        alert('任务执行超时，请稍后重试')
      } else if (error.includes('API')) {
        alert('AI 服务暂时不可用，请稍后重试')
      } else {
        alert(`任务失败: ${error}`)
      }
    }
  })
} catch (error) {
  // 处理网络错误或轮询错误
  console.error('轮询错误:', error)
  alert('网络连接失败，请检查网络后重试')
}
```

### 超时处理

```typescript
await taskPolling.startPolling({
  taskId: 'task-uuid',
  maxAttempts: 100,  // 100 次 * 3 秒 = 5 分钟
  onError: (error) => {
    if (error.includes('超过最大轮询次数')) {
      alert('任务执行时间过长，请稍后在任务列表中查看结果')
    }
  }
})
```

### 用户取消

```vue
<script setup lang="ts">
const taskPolling = useTaskPolling()
const showProgress = ref(false)

function cancelTask() {
  taskPolling.stopPolling()
  showProgress.value = false
  alert('已取消任务')
}
</script>

<template>
  <TaskProgressModal
    v-if="showProgress"
    :status="taskPolling.status.value"
    :progress="taskPolling.progress.value"
    :message="taskPolling.progressMessage.value"
    :show-close="true"
    @close="cancelTask"
  />
</template>
```

---

## 最佳实践

### 1. 合理设置轮询间隔

```typescript
// ✅ 推荐：3-5 秒
await taskPolling.startPolling({
  taskId: 'task-uuid',
  interval: 3000
})

// ❌ 不推荐：过于频繁
await taskPolling.startPolling({
  taskId: 'task-uuid',
  interval: 500  // 太频繁，增加服务器负担
})
```

### 2. 设置合理的最大轮询次数

```typescript
// 根据任务类型设置不同的最大次数
const maxAttempts = {
  concept_converse: 80,      // 80 * 3s = 4 分钟
  blueprint_generate: 200,   // 200 * 3s = 10 分钟
  chapter_generate: 200,     // 200 * 3s = 10 分钟
  chapter_evaluate: 120,     // 120 * 3s = 6 分钟
  outline_generate: 120      // 120 * 3s = 6 分钟
}

await taskPolling.startPolling({
  taskId: 'task-uuid',
  maxAttempts: maxAttempts[taskType]
})
```

### 3. 提供清晰的用户反馈

```vue
<script setup lang="ts">
const statusText = computed(() => {
  switch (taskPolling.status.value) {
    case 'pending':
      return '任务排队中...'
    case 'processing':
      return '正在处理...'
    case 'completed':
      return '完成！'
    case 'failed':
      return '失败'
    default:
      return '未知状态'
  }
})
</script>

<template>
  <div class="status-indicator">
    <span>{{ statusText }}</span>
    <span v-if="taskPolling.status.value === 'processing'">
      {{ taskPolling.progress.value }}%
    </span>
  </div>
</template>
```

### 4. 清理资源

```vue
<script setup lang="ts">
import { onUnmounted } from 'vue'

const taskPolling = useTaskPolling()

// 组件卸载时停止轮询
onUnmounted(() => {
  taskPolling.stopPolling()
})
</script>
```

### 5. 处理多个并发任务

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useTaskPolling } from '@/composables/useTaskPolling'

// 为每个任务创建独立的轮询实例
const task1Polling = useTaskPolling()
const task2Polling = useTaskPolling()

async function startMultipleTasks() {
  // 同时启动多个任务
  await Promise.all([
    task1Polling.startPolling({ taskId: 'task-1', ... }),
    task2Polling.startPolling({ taskId: 'task-2', ... })
  ])
}
</script>
```

---

## 调试技巧

### 启用详细日志

```typescript
await taskPolling.startPolling({
  taskId: 'task-uuid',
  onProgress: (progress, message) => {
    console.log(`[${new Date().toISOString()}] 进度: ${progress}% - ${message}`)
  }
})
```

### 查看任务详情

```typescript
import { TaskAPI } from '@/api/tasks'

// 手动查询任务状态
const status = await TaskAPI.getTaskStatus('task-uuid')
console.log('任务详情:', status)
```

### 查看任务历史

```typescript
// 查询最近的任务
const recentTasks = await TaskAPI.listTasks({
  limit: 10,
  offset: 0
})
console.log('最近任务:', recentTasks)
```

---

## 常见问题

### Q: 轮询会不会消耗太多资源？

A: 不会。默认 3 秒轮询一次，对服务器和客户端的负担都很小。而且任务完成后会自动停止轮询。

### Q: 如果用户刷新页面会怎样？

A: 轮询会停止，但任务仍在后台执行。用户可以通过任务列表查看任务状态，或者重新开始轮询。

### Q: 可以同时轮询多个任务吗？

A: 可以。为每个任务创建独立的 `useTaskPolling` 实例即可。

### Q: 如何处理长时间运行的任务？

A: 增加 `maxAttempts` 参数，或者提示用户稍后在任务列表中查看结果。

### Q: 任务失败后可以重试吗？

A: 可以。重新调用创建任务的 API 即可创建新任务。

---

## 相关文档

- [异步任务 API 文档](./async_task_api.md)
- [部署指南](./deployment_guide.md)
- [管理员监控端点](./admin_task_endpoints.md)

---

## 代码示例仓库

完整的代码示例可以在以下文件中找到：

- `frontend/src/composables/useTaskPolling.ts`
- `frontend/src/components/TaskProgressModal.vue`
- `frontend/src/views/InspirationMode.vue`
- `frontend/src/views/WritingDesk.vue`
