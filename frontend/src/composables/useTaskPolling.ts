import { ref, onUnmounted, type Ref } from 'vue'
import { getTaskStatus, type TaskStatus } from '@/api/tasks'

export interface UseTaskPollingOptions {
  taskId: string
  interval?: number
  maxAttempts?: number
  onProgress?: (progress: number, message: string) => void
  onComplete?: (result: any) => void
  onError?: (error: string) => void
}

export interface UseTaskPollingReturn {
  status: Ref<'pending' | 'processing' | 'completed' | 'failed' | 'idle'>
  progress: Ref<number>
  progressMessage: Ref<string>
  result: Ref<any>
  error: Ref<string | null>
  isPolling: Ref<boolean>
  startPolling: () => void
  stopPolling: () => void
}

export function useTaskPolling(options: UseTaskPollingOptions): UseTaskPollingReturn {
  const {
    taskId,
    interval = 3000,
    maxAttempts = 100,
    onProgress,
    onComplete,
    onError
  } = options

  const status = ref<'pending' | 'processing' | 'completed' | 'failed' | 'idle'>('idle')
  const progress = ref(0)
  const progressMessage = ref('')
  const result = ref<any>(null)
  const error = ref<string | null>(null)
  const isPolling = ref(false)

  let pollTimeout: number | null = null
  let attemptCount = 0
  let backoffMultiplier = 1

  const stopPolling = () => {
    if (pollTimeout !== null) {
      clearTimeout(pollTimeout)
      pollTimeout = null
    }
    isPolling.value = false
    attemptCount = 0
    backoffMultiplier = 1
  }

  const poll = async () => {
    try {
      attemptCount++

      if (attemptCount > maxAttempts) {
        stopPolling()
        error.value = '任务查询超时，请稍后重试'
        status.value = 'failed'
        if (onError) {
          onError(error.value)
        }
        return
      }

      const taskStatus: TaskStatus = await getTaskStatus(taskId)
      
      status.value = taskStatus.status
      progress.value = taskStatus.progress
      progressMessage.value = taskStatus.progress_message || ''

      if (onProgress && (taskStatus.status === 'pending' || taskStatus.status === 'processing')) {
        onProgress(taskStatus.progress, taskStatus.progress_message || '')
      }

      if (taskStatus.status === 'completed') {
        stopPolling()
        result.value = taskStatus.result_data
        if (onComplete) {
          onComplete(taskStatus.result_data)
        }
        return
      } else if (taskStatus.status === 'failed') {
        stopPolling()
        error.value = taskStatus.error_message || '任务执行失败'
        if (onError) {
          onError(error.value)
        }
        return
      }

      // Reset backoff on successful poll and schedule next poll
      backoffMultiplier = 1
      if (isPolling.value) {
        pollTimeout = window.setTimeout(() => poll(), interval * backoffMultiplier)
      }
    } catch (err) {
      // Network error - use exponential backoff
      backoffMultiplier = Math.min(backoffMultiplier * 2, 8)
      
      if (attemptCount >= maxAttempts) {
        stopPolling()
        error.value = err instanceof Error ? err.message : '网络错误'
        status.value = 'failed'
        if (onError) {
          onError(error.value)
        }
        return
      }
      
      // Schedule next poll with increased backoff
      if (isPolling.value) {
        pollTimeout = window.setTimeout(() => poll(), interval * backoffMultiplier)
      }
    }
  }

  const startPolling = () => {
    if (isPolling.value) {
      return
    }

    isPolling.value = true
    attemptCount = 0
    backoffMultiplier = 1
    error.value = null

    // Poll immediately
    poll()
  }

  onUnmounted(() => {
    stopPolling()
  })

  return {
    status,
    progress,
    progressMessage,
    result,
    error,
    isPolling,
    startPolling,
    stopPolling
  }
}
