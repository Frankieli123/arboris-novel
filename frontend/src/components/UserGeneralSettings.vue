<template>
  <div class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-8">
    <h2 class="text-2xl font-bold text-gray-800 mb-6">常规设置</h2>
    <form @submit.prevent="handleSave" class="space-y-6">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">
          生成蓝图后是否自动拆分章节
        </label>
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 focus:outline-none"
            :class="settings.auto_expand_enabled ? 'bg-indigo-500' : 'bg-gray-300'"
            @click="settings.auto_expand_enabled = !settings.auto_expand_enabled"
            :aria-pressed="settings.auto_expand_enabled"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200"
              :class="settings.auto_expand_enabled ? 'translate-x-4' : 'translate-x-0'"
            />
          </button>
          <span class="text-sm text-gray-700 select-none">
            {{
              settings.auto_expand_enabled
                ? '自动拆分章节'
                : '不自动拆分章节'
            }}
          </span>
        </div>
      </div>

      <div>
        <label for="auto-expand-target" class="block text-sm font-medium text-gray-700">
          自动拆分每条大纲的章节数
        </label>
        <input
          id="auto-expand-target"
          v-model.number="settings.auto_expand_target_chapter_count"
          type="number"
          min="1"
          max="10"
          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          placeholder="例如 3 表示每条大纲拆分为 3 章"
        >
        <p class="mt-1 text-xs text-gray-500">
          若未设置，将使用后台全局配置或系统默认值。
        </p>
      </div>

      <div>
        <label for="chapter-version-count" class="block text-sm font-medium text-gray-700">
          每次生成章节的候选版本数量
        </label>
        <input
          id="chapter-version-count"
          v-model.number="settings.chapter_version_count"
          type="number"
          min="1"
          max="5"
          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
          placeholder="例如 2 表示每次生成 2 个候选版本"
        >
        <p class="mt-1 text-xs text-gray-500">
          仅影响当前账号的章节生成版本数，默认与后台配置保持一致。
        </p>
      </div>

      <div class="flex justify-end space-x-4 pt-4">
        <button
          type="submit"
          :disabled="saving"
          class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getUserGeneralSettings, updateUserGeneralSettings, type UserGeneralSettings } from '@/api/userSettings'

const settings = ref<UserGeneralSettings>({
  auto_expand_enabled: false,
  auto_expand_target_chapter_count: 3,
  chapter_version_count: 3
})

const loading = ref(false)
const saving = ref(false)

const loadSettings = async () => {
  loading.value = true
  try {
    const data = await getUserGeneralSettings()
    settings.value = data
  } catch (err) {
    console.error('加载常规设置失败', err)
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    // 基本边界保护
    if (settings.value.auto_expand_target_chapter_count < 1) {
      settings.value.auto_expand_target_chapter_count = 1
    }
    if (settings.value.auto_expand_target_chapter_count > 10) {
      settings.value.auto_expand_target_chapter_count = 10
    }
    if (settings.value.chapter_version_count < 1) {
      settings.value.chapter_version_count = 1
    }
    if (settings.value.chapter_version_count > 5) {
      settings.value.chapter_version_count = 5
    }

    await updateUserGeneralSettings(settings.value)
    alert('常规设置已保存，对当前账号立即生效！')
  } catch (err) {
    console.error('保存常规设置失败', err)
    alert(err instanceof Error ? err.message : '保存失败，请稍后再试')
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>
