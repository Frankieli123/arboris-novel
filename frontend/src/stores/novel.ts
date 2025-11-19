import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { NovelProject, NovelProjectSummary, ConverseResponse, BlueprintGenerationResponse, Blueprint, DeleteNovelsResponse, ChapterOutline } from '@/api/novel'
import { NovelAPI } from '@/api/novel'
import { getTaskStatus, type TaskStatus } from '@/api/tasks'

export const useNovelStore = defineStore('novel', () => {
  // State
  const projects = ref<NovelProjectSummary[]>([])
  const currentProject = ref<NovelProject | null>(null)
  const currentConversationState = ref<any>({})
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  
  // Task management state
  const activeTasks = ref<Map<string, TaskStatus>>(new Map())
  const taskResults = ref<Map<string, any>>(new Map())

  // Getters
  const projectsCount = computed(() => projects.value.length)
  const hasCurrentProject = computed(() => currentProject.value !== null)

  // Actions
  async function loadProjects() {
    isLoading.value = true
    error.value = null
    try {
      projects.value = await NovelAPI.getAllNovels()
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载项目失败'
    } finally {
      isLoading.value = false
    }
  }

  async function createProject(title: string, initialPrompt: string) {
    isLoading.value = true
    error.value = null
    try {
      const project = await NovelAPI.createNovel(title, initialPrompt)
      currentProject.value = project
      currentConversationState.value = {}
      return project
    } catch (err) {
      error.value = err instanceof Error ? err.message : '创建项目失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function loadProject(projectId: string, silent: boolean = false) {
    if (!silent) {
      isLoading.value = true
    }
    error.value = null
    try {
      currentProject.value = await NovelAPI.getNovel(projectId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载项目失败'
    } finally {
      if (!silent) {
        isLoading.value = false
      }
    }
  }

  async function loadChapter(chapterNumber: number) {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const chapter = await NovelAPI.getChapter(currentProject.value.id, chapterNumber)
      const project = currentProject.value
      if (!Array.isArray(project.chapters)) {
        project.chapters = []
      }
      const index = project.chapters.findIndex(ch => ch.chapter_number === chapterNumber)
      if (index >= 0) {
        project.chapters.splice(index, 1, chapter)
      } else {
        project.chapters.push(chapter)
      }
      project.chapters.sort((a, b) => a.chapter_number - b.chapter_number)
      return chapter
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载章节失败'
      throw err
    }
  }

  async function sendConversation(userInput: any): Promise<{ task_id: string; status: string; created_at: string }> {
    isLoading.value = true
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const response = await NovelAPI.converseConcept(
        currentProject.value.id,
        userInput,
        currentConversationState.value
      )
      return response
    } catch (err) {
      error.value = err instanceof Error ? err.message : '对话失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function generateBlueprint(): Promise<{ task_id: string; status: string; created_at: string }> {
    // Generate blueprint from conversation history
    isLoading.value = true
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      return await NovelAPI.generateBlueprint(currentProject.value.id)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成蓝图失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function saveBlueprint(blueprint: Blueprint) {
    isLoading.value = true
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      if (!blueprint) {
        throw new Error('缺少蓝图数据')
      }
      currentProject.value = await NovelAPI.saveBlueprint(currentProject.value.id, blueprint)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '保存蓝图失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function generateChapter(chapterNumber: number, writingNotes?: string): Promise<{ task_id: string; status: string; created_at: string }> {
    // 注意：这里不设置全局 isLoading，因为 WritingDesk.vue 有自己的局部加载状态
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      return await NovelAPI.generateChapter(currentProject.value.id, chapterNumber, writingNotes)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成章节失败'
      throw err
    }
  }

  async function evaluateChapter(chapterNumber: number): Promise<{ task_id: string; status: string; created_at: string }> {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      return await NovelAPI.evaluateChapter(currentProject.value.id, chapterNumber)
    } catch (err) {
      error.value = err instanceof Error ? err.message : '评估章节失败'
      throw err
    }
  }

  async function selectChapterVersion(chapterNumber: number, versionIndex: number) {
    // 不设置全局 isLoading，让调用方处理局部加载状态
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const updatedProject = await NovelAPI.selectChapterVersion(
        currentProject.value.id,
        chapterNumber,
        versionIndex
      )
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '选择章节版本失败'
      throw err
    }
  }

  async function deleteProjects(projectIds: string[]): Promise<DeleteNovelsResponse> {
    isLoading.value = true
    error.value = null
    try {
      const response = await NovelAPI.deleteNovels(projectIds)
      
      // 从本地项目列表中移除已删除的项目
      projects.value = projects.value.filter(project => !projectIds.includes(project.id))
      
      // 如果当前项目被删除，清空当前项目
      if (currentProject.value && projectIds.includes(currentProject.value.id)) {
        currentProject.value = null
        currentConversationState.value = {}
      }
      
      return response
    } catch (err) {
      error.value = err instanceof Error ? err.message : '删除项目失败'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function updateChapterOutline(chapterOutline: ChapterOutline) {
    // 不设置全局 isLoading，让调用方处理局部加载状态
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const updatedProject = await NovelAPI.updateChapterOutline(
        currentProject.value.id,
        chapterOutline
      )
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '更新章节大纲失败'
      throw err
    }
  }

  async function deleteChapter(chapterNumbers: number | number[]) {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      const numbersToDelete = Array.isArray(chapterNumbers) ? chapterNumbers : [chapterNumbers]
      const updatedProject = await NovelAPI.deleteChapter(
        currentProject.value.id,
        numbersToDelete
      )
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '删除章节失败'
      throw err
    }
  }

  async function generateChapterOutline(startChapter: number, numChapters: number): Promise<{ task_id: string; status: string; created_at: string }> {
    error.value = null
    try {
      if (!currentProject.value) {
        throw new Error('没有当前项目')
      }
      return await NovelAPI.generateChapterOutline(
        currentProject.value.id,
        startChapter,
        numChapters
      )
    } catch (err) {
      error.value = err instanceof Error ? err.message : '生成大纲失败'
      throw err
    }
  }

  async function editChapterContent(projectId: string, chapterNumber: number, content: string) {
    error.value = null
    try {
      const updatedProject = await NovelAPI.editChapterContent(projectId, chapterNumber, content)
      currentProject.value = updatedProject // 更新 store
    } catch (err) {
      error.value = err instanceof Error ? err.message : '编辑章节内容失败'
      throw err
    }
  }

  function clearError() {
    error.value = null
  }

  function setCurrentProject(project: NovelProject | null) {
    currentProject.value = project
  }

  // Task management methods
  async function pollTaskStatus(taskId: string): Promise<TaskStatus> {
    try {
      const status = await getTaskStatus(taskId)
      activeTasks.value.set(taskId, status)
      return status
    } catch (err) {
      error.value = err instanceof Error ? err.message : '查询任务状态失败'
      throw err
    }
  }

  function getTaskById(taskId: string): TaskStatus | undefined {
    return activeTasks.value.get(taskId)
  }

  function setTaskResult(taskId: string, result: any) {
    taskResults.value.set(taskId, result)
  }

  function getTaskResult(taskId: string): any {
    return taskResults.value.get(taskId)
  }

  function clearTask(taskId: string) {
    activeTasks.value.delete(taskId)
    taskResults.value.delete(taskId)
  }

  async function handleTaskCompletion(taskId: string, taskType: string) {
    const taskStatus = activeTasks.value.get(taskId)
    if (!taskStatus || taskStatus.status !== 'completed') {
      return
    }

    const result = taskStatus.result_data

    // Handle different task types
    switch (taskType) {
      case 'concept_converse':
        if (result && result.conversation_state) {
          currentConversationState.value = result.conversation_state
        }
        setTaskResult(taskId, result)
        break

      case 'blueprint_generate':
        if (result && result.blueprint && currentProject.value) {
          currentProject.value.blueprint = result.blueprint
        }
        setTaskResult(taskId, result)
        break

      case 'chapter_generate':
      case 'chapter_evaluate':
      case 'outline_generate':
        // Reload the project to get updated data
        if (currentProject.value) {
          await loadProject(currentProject.value.id, true)
        }
        setTaskResult(taskId, result)
        break

      default:
        setTaskResult(taskId, result)
    }
  }

  return {
    // State
    projects,
    currentProject,
    currentConversationState,
    isLoading,
    error,
    activeTasks,
    taskResults,
    // Getters
    projectsCount,
    hasCurrentProject,
    // Actions
    loadProjects,
    createProject,
    loadProject,
    loadChapter,
    sendConversation,
    generateBlueprint,
    saveBlueprint,
    generateChapter,
    evaluateChapter,
    selectChapterVersion,
    deleteProjects,
    updateChapterOutline,
    deleteChapter,
    generateChapterOutline,
    editChapterContent,
    clearError,
    setCurrentProject,
    // Task management
    pollTaskStatus,
    getTaskById,
    setTaskResult,
    getTaskResult,
    clearTask,
    handleTaskCompletion
  }
})
