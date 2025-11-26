import { useAuthStore } from '@/stores/auth'
import router from '@/router'

// API 配置
// 在生产环境中使用相对路径，在开发环境中使用绝对路径
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
export interface NovelProject {
  id: string
  title: string
  initial_prompt: string
  blueprint?: Blueprint
  chapters: Chapter[]
  conversation_history: ConversationMessage[]
}

export interface NovelProjectSummary {
  id: string
  title: string
  genre: string
  last_edited: string
  completed_chapters: number
  total_chapters: number
}

export interface Blueprint {
  title?: string
  target_audience?: string
  genre?: string
  style?: string
  tone?: string
  one_sentence_summary?: string
  full_synopsis?: string
  world_setting?: any
  characters?: Character[]
  relationships?: any[]
  chapter_outline?: ChapterOutline[]
}

export interface OrganizationMemberInfo {
  id: number
  character_id: number
  character_name: string
  position: string
  rank: number
  loyalty: number
  status: string
  joined_at?: string | null
  left_at?: string | null
  notes?: string | null
}

export interface OrganizationDetail {
  id: number
  name: string
  power_level: number
  member_count: number
  location?: string | null
  motto?: string | null
  color?: string | null
  level: number
  parent_org_id?: number | null
  character_id?: number | null
  members: OrganizationMemberInfo[]
}

export interface Character {
  name: string
  description: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
}

export interface OutlineChildChapter {
  chapter_number: number
  sub_index: number
}

export interface ChapterOutline {
  id?: number
  chapter_number: number
  title: string
  summary: string
  children?: OutlineChildChapter[]
}

export interface ChapterVersion {
  content: string
  style?: string
}

export interface Chapter {
  chapter_number: number
  title: string
  summary: string
  content: string | null
  versions: string[] | null  // versions是字符串数组，不是对象数组
  evaluation: string | null
  generation_status: 'not_generated' | 'generating' | 'evaluating' | 'selecting' | 'failed' | 'evaluation_failed' | 'waiting_for_confirm' | 'successful'
  word_count?: number  // 字数统计
}

export interface ConversationMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ConverseResponse {
  ai_message: string
  ui_control: UIControl
  conversation_state: any
  is_complete: boolean
  ready_for_blueprint?: boolean  // 新增：表示准备生成蓝图
}

export interface BlueprintGenerationResponse {
  blueprint: Blueprint
  ai_message: string
}

export interface UIControl {
  type: 'single_choice' | 'text_input'
  options?: Array<{ id: string; label: string }>
  placeholder?: string
}

export interface ChapterGenerationResponse {
  versions: ChapterVersion[] // Renamed from chapter_versions for consistency
  evaluation: string | null
  ai_message: string
  chapter_number: number
}

export interface ChapterPlanItem {
  sub_index: number
  title: string
  plot_summary: string
  key_events: string[]
  character_focus: string[]
  emotional_tone: string
  narrative_goal: string
  conflict_type: string
  estimated_words: number
  scenes?: string[]
}

export interface OutlineExpansionRequest {
  target_chapter_count: number
  expansion_strategy: 'balanced' | 'climax' | 'detail'
  enable_scene_analysis: boolean
  auto_create_chapters: boolean
}

export interface OutlineExpansionResponse {
  outline_id: number
  outline_title: string
  target_chapter_count: number
  actual_chapter_count: number
  expansion_strategy: string
  chapter_plans: ChapterPlanItem[]
  created_chapters?: Array<{
    id: number
    chapter_number: number
    sub_index: number
    title?: string | null
    status: string
  }>
}

export interface ExistingExpandedChapter {
  id: number
  chapter_number: number
  sub_index: number
  title?: string | null
  status: string
}

export interface OutlineChaptersResponse {
  has_chapters: boolean
  chapter_count: number
  chapters: ExistingExpandedChapter[]
  expansion_plans?: ChapterPlanItem[]
}

export interface UpdateExpansionPlanRequest {
  chapter_number: number
  expansion_plan: ChapterPlanItem
}

export interface DeleteNovelsResponse {
  status: string
  message: string
}

export type NovelSectionType = 'overview' | 'world_setting' | 'characters' | 'relationships' | 'chapter_outline' | 'chapters'

export interface NovelSectionResponse {
  section: NovelSectionType
  data: Record<string, any>
}

// API 函数
const NOVELS_BASE = `${API_BASE_URL}${API_PREFIX}/novels`
const WRITER_PREFIX = '/api/writer'
const WRITER_BASE = `${API_BASE_URL}${WRITER_PREFIX}/novels`

export class NovelAPI {
  static async createNovel(title: string, initialPrompt: string): Promise<NovelProject> {
    return request(NOVELS_BASE, {
      method: 'POST',
      body: JSON.stringify({ title, initial_prompt: initialPrompt })
    })
  }

  static async getNovel(projectId: string): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}`)
  }

  static async getChapter(projectId: string, chapterNumber: number): Promise<Chapter> {
    return request(`${NOVELS_BASE}/${projectId}/chapters/${chapterNumber}`)
  }

  static async getSection(projectId: string, section: NovelSectionType): Promise<NovelSectionResponse> {
    return request(`${NOVELS_BASE}/${projectId}/sections/${section}`)
  }

  static async getOrganizations(projectId: string): Promise<OrganizationDetail[]> {
    return request(`${NOVELS_BASE}/${projectId}/organizations`)
  }

  static async converseConcept(
    projectId: string,
    userInput: any,
    conversationState: any = {}
  ): Promise<ConverseResponse> {
    const formattedUserInput = userInput || { id: null, value: null }
    return request(`${NOVELS_BASE}/${projectId}/concept/converse`, {
      method: 'POST',
      body: JSON.stringify({
        user_input: formattedUserInput,
        conversation_state: conversationState
      })
    })
  }

  static async expandOutline(
    projectId: string,
    outlineId: number,
    payload: OutlineExpansionRequest
  ): Promise<OutlineExpansionResponse> {
    return request(`${WRITER_BASE}/${projectId}/outlines/${outlineId}/expand`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static async getOutlineChapters(
    projectId: string,
    outlineId: number
  ): Promise<OutlineChaptersResponse> {
    return request(`${WRITER_BASE}/${projectId}/outlines/${outlineId}/chapters`)
  }

  static async generateBlueprint(projectId: string): Promise<BlueprintGenerationResponse> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint/generate`, {
      method: 'POST'
    })
  }

  static async saveBlueprint(projectId: string, blueprint: Blueprint): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint/save`, {
      method: 'POST',
      body: JSON.stringify(blueprint)
    })
  }

  static async generateChapter(
    projectId: string,
    chapterNumber: number,
    enableMcp: boolean = true
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/generate`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        enable_mcp: enableMcp
      })
    })
  }

  static async evaluateChapter(projectId: string, chapterNumber: number): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/evaluate`, {
      method: 'POST',
      body: JSON.stringify({ chapter_number: chapterNumber })
    })
  }

  static async selectChapterVersion(
    projectId: string,
    chapterNumber: number,
    versionIndex: number
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/select`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        version_index: versionIndex
      })
    })
  }

  static async getAllNovels(): Promise<NovelProjectSummary[]> {
    return request(NOVELS_BASE)
  }

  static async deleteNovels(projectIds: string[]): Promise<DeleteNovelsResponse> {
    return request(NOVELS_BASE, {
      method: 'DELETE',
      body: JSON.stringify(projectIds)
    })
  }

  static async updateChapterOutline(
    projectId: string,
    chapterOutline: ChapterOutline
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/update-outline`, {
      method: 'POST',
      body: JSON.stringify(chapterOutline)
    })
  }

  static async updateChapterExpansionPlan(
    projectId: string,
    chapterNumber: number,
    expansionPlan: ChapterPlanItem
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/update-expansion-plan`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        expansion_plan: expansionPlan
      } as UpdateExpansionPlanRequest)
    })
  }

  static async deleteChapter(
    projectId: string,
    chapterNumbers: number[]
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/delete`, {
      method: 'POST',
      body: JSON.stringify({ chapter_numbers: chapterNumbers })
    })
  }

  static async generateChapterOutline(
    projectId: string,
    startChapter: number,
    numChapters: number,
    options?: {
      mode?: 'auto' | 'new' | 'continue'
      story_direction?: string
      plot_stage?: 'development' | 'climax' | 'ending'
      keep_existing?: boolean
      auto_expand_target_chapter_count?: number
    }
  ): Promise<NovelProject> {
    const payload: any = {
      start_chapter: startChapter,
      num_chapters: numChapters
    }

    if (options) {
      if (options.mode) {
        payload.mode = options.mode
      }
      if (typeof options.story_direction === 'string' && options.story_direction.trim()) {
        payload.story_direction = options.story_direction.trim()
      }
      if (options.plot_stage) {
        payload.plot_stage = options.plot_stage
      }
      if (typeof options.keep_existing === 'boolean') {
        payload.keep_existing = options.keep_existing
      }
      if (
        typeof options.auto_expand_target_chapter_count === 'number' &&
        options.auto_expand_target_chapter_count > 0
      ) {
        payload.auto_expand_target_chapter_count = options.auto_expand_target_chapter_count
      }
    }

    return request(`${WRITER_BASE}/${projectId}/chapters/outline`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static async updateBlueprint(projectId: string, data: Record<string, any>): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  }

  static async editChapterContent(
    projectId: string,
    chapterNumber: number,
    content: string
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/edit`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        content: content
      })
    })
  }
}
