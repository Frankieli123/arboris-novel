import { useAuthStore } from '@/stores/auth'
import router from '@/router'

// API 配置
export const API_BASE_URL = import.meta.env.MODE === 'production' ? '' : 'http://127.0.0.1:8000'

// Task API client for async task polling
export interface TaskStatus {
  task_id: string
  task_type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  progress_message?: string
  result_data?: any
  error_message?: string
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface TaskResponse {
  task_id: string
  status: string
  created_at: string
}

// 统一的请求处理函数
const request = async (url: string, options: RequestInit = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  const response = await fetch(url, { ...options, headers })

  if (response.status === 401) {
    // Token 失效或未授权
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `请求失败，状态码: ${response.status}`)
  }

  return response.json()
}

export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  return request(`${API_BASE_URL}/api/tasks/${taskId}`)
}

export async function createTask(endpoint: string, data: any): Promise<TaskResponse> {
  return request(endpoint, {
    method: 'POST',
    body: JSON.stringify(data)
  })
}

export async function listTasks(status?: string, limit: number = 20): Promise<TaskStatus[]> {
  const params = new URLSearchParams()
  if (status) params.append('status', status)
  params.append('limit', limit.toString())
  
  return request(`${API_BASE_URL}/api/tasks?${params}`)
}
