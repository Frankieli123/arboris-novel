import { useAuthStore } from '@/stores/auth'

const API_PREFIX = '/api'
const USER_SETTINGS_BASE = `${API_PREFIX}/user-settings/general`

export interface UserGeneralSettings {
  auto_expand_enabled: boolean
  auto_expand_target_chapter_count: number
  chapter_version_count: number
}

const getHeaders = () => {
  const authStore = useAuthStore()
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${authStore.token}`
  }
}

export const getUserGeneralSettings = async (): Promise<UserGeneralSettings> => {
  const response = await fetch(USER_SETTINGS_BASE, {
    method: 'GET',
    headers: getHeaders()
  })
  if (!response.ok) {
    throw new Error('获取常规设置失败')
  }
  return response.json()
}

export const updateUserGeneralSettings = async (
  payload: UserGeneralSettings
): Promise<UserGeneralSettings> => {
  const response = await fetch(USER_SETTINGS_BASE, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify(payload)
  })
  if (!response.ok) {
    throw new Error('保存常规设置失败')
  }
  return response.json()
}
