import { useAuthStore } from '@/stores/auth'
import router from '@/router'

// API 配置
export const API_BASE_URL = import.meta.env.MODE === 'production' ? '' : 'http://127.0.0.1:8000'
export const API_PREFIX = '/api'

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

// 类型定义
export interface MCPPlugin {
  id: number
  plugin_name: string
  display_name: string
  plugin_type: string
  server_url: string
  headers?: Record<string, string> | null
  enabled: boolean
  category?: string | null
  config?: Record<string, any> | null
  user_enabled?: boolean | null
  is_default?: boolean
  created_at: string
  updated_at: string
}

export interface MCPPluginCreate {
  plugin_name: string
  display_name: string
  plugin_type?: string
  server_url: string
  headers?: Record<string, string> | null
  enabled?: boolean
  category?: string | null
  config?: Record<string, any> | null
}

export interface MCPPluginUpdate {
  display_name?: string
  server_url?: string
  headers?: Record<string, string> | null
  enabled?: boolean
  category?: string | null
  config?: Record<string, any> | null
}

export interface ToolDefinition {
  type: string
  function: {
    name: string
    description?: string
    parameters?: Record<string, any>
  }
}

export interface PluginTestReport {
  success: boolean
  message: string
  tools_count: number
  suggestions: string[]
  error?: string | null
}

export interface ToolMetrics {
  tool_name: string
  total_calls: number
  success_calls: number
  failed_calls: number
  avg_duration_ms: number
  success_rate: number
}

export interface TogglePluginResponse {
  enabled: boolean
}

export interface DeletePluginResponse {
  status: string
  message: string
}

export interface ClearCacheResponse {
  status: string
  message: string
}

export interface ImportPluginsResponse {
  status: string
  created: string[]
  skipped: string[]
  errors: string[]
  summary: string
}

// API 函数
const MCP_BASE = `${API_BASE_URL}${API_PREFIX}/mcp`

export class MCPAPI {
  /**
   * 获取所有插件列表（包含用户启用状态）
   */
  static async listPlugins(): Promise<MCPPlugin[]> {
    return request(`${MCP_BASE}/plugins`)
  }

  /**
   * 创建新插件（仅管理员）
   */
  static async createPlugin(pluginData: MCPPluginCreate): Promise<MCPPlugin> {
    return request(`${MCP_BASE}/plugins`, {
      method: 'POST',
      body: JSON.stringify(pluginData)
    })
  }

  /**
   * 获取插件详情
   */
  static async getPlugin(pluginId: number): Promise<MCPPlugin> {
    return request(`${MCP_BASE}/plugins/${pluginId}`)
  }

  /**
   * 更新插件配置（仅管理员）
   */
  static async updatePlugin(pluginId: number, pluginData: MCPPluginUpdate): Promise<MCPPlugin> {
    return request(`${MCP_BASE}/plugins/${pluginId}`, {
      method: 'PUT',
      body: JSON.stringify(pluginData)
    })
  }

  /**
   * 删除插件（仅管理员）
   */
  static async deletePlugin(pluginId: number): Promise<DeletePluginResponse> {
    return request(`${MCP_BASE}/plugins/${pluginId}`, {
      method: 'DELETE'
    })
  }

  /**
   * 切换用户的插件启用状态
   */
  static async togglePlugin(pluginId: number, enabled: boolean): Promise<TogglePluginResponse> {
    return request(`${MCP_BASE}/plugins/${pluginId}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled })
    })
  }

  /**
   * 测试插件连接和功能（仅管理员）
   */
  static async testPlugin(pluginId: number): Promise<PluginTestReport> {
    return request(`${MCP_BASE}/plugins/${pluginId}/test`, {
      method: 'POST'
    })
  }

  /**
   * 获取插件提供的工具列表
   */
  static async getPluginTools(pluginId: number): Promise<ToolDefinition[]> {
    return request(`${MCP_BASE}/plugins/${pluginId}/tools`)
  }

  /**
   * 获取工具调用指标（仅管理员）
   */
  static async getMetrics(toolName?: string): Promise<Record<string, ToolMetrics>> {
    const url = toolName 
      ? `${MCP_BASE}/metrics?tool_name=${encodeURIComponent(toolName)}`
      : `${MCP_BASE}/metrics`
    return request(url)
  }

  /**
   * 清空工具定义缓存（仅管理员）
   */
  static async clearCache(): Promise<ClearCacheResponse> {
    return request(`${MCP_BASE}/cache/clear`, {
      method: 'POST'
    })
  }

  /**
   * 从 MCP 配置 JSON 批量导入插件（仅管理员）
   */
  static async importPluginsFromJson(mcpConfig: Record<string, any>): Promise<ImportPluginsResponse> {
    return request(`${MCP_BASE}/plugins/import`, {
      method: 'POST',
      body: JSON.stringify(mcpConfig)
    })
  }
}
