<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">大纲管理</h2>
        <p class="text-sm text-slate-500">故事结构与章节节奏一目了然</p>
      </div>
      <div v-if="editable" class="flex items-center gap-2">
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
          @click="$emit('add')"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
          </svg>
          新增章节
        </button>
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm text-gray-500 hover:text-indigo-600 transition-colors"
          @click="emitEdit('chapter_outline', '大纲管理', outline)"
        >
          <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
          编辑大纲
        </button>
      </div>
    </div>

    <ol class="relative border-l border-slate-200 ml-3 space-y-8">
      <li
        v-for="chapter in outline"
        :key="chapter.chapter_number"
        class="ml-6"
      >
        <span class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500 text-white text-xs font-semibold">
          {{ chapter.chapter_number }}
        </span>
        <div class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm p-5">
          <div class="flex items-stretch justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-4">
                <h3 class="text-lg font-semibold text-slate-900">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
              </div>
              <p class="mt-3 text-sm text-slate-600 leading-6 whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>
              <div
                v-if="chapter.children && chapter.children.length"
                class="mt-2 text-xs text-slate-500"
              >
                当前大纲下章节：
                <span class="font-medium">
                  第{{ chapter.children.map(child => child.chapter_number).join('、') }}章
                </span>
              </div>
            </div>
            <div
              v-if="editable"
              class="flex flex-col sm:flex-row items-center justify-center gap-2 text-sm flex-shrink-0 self-stretch"
            >
              <button
                type="button"
                class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-indigo-600 hover:bg-indigo-50 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                :disabled="checkingOutlineId === chapter.id"
                @click="$emit('expand-outline', chapter)"
              >
                <svg
                  v-if="checkingOutlineId !== chapter.id"
                  class="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path d="M4 4h6v6H4V4zm6 6h6v6h-6v-6z" />
                </svg>
                <svg
                  v-else
                  class="h-4 w-4 animate-spin"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="9"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-dasharray="2 4"
                    class="opacity-80"
                  />
                </svg>
                展开
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-slate-600 hover:bg-slate-50 transition-colors"
                @click="$emit('edit-chapter', chapter)"
              >
                <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                  <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                </svg>
                编辑
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-red-600 hover:bg-red-50 transition-colors"
                @click="$emit('delete-chapter', chapter.chapter_number)"
              >
                <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd" />
                </svg>
                删除
              </button>
            </div>
          </div>
        </div>
      </li>
      <li v-if="!outline.length" class="ml-6 text-slate-400 text-sm">暂无章节大纲</li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { defineEmits, defineProps } from 'vue'

interface OutlineChildItem {
  chapter_number: number
  sub_index: number
}

interface OutlineItem {
  id?: number
  chapter_number: number
  title: string
  summary: string
  children?: OutlineChildItem[]
}

const props = defineProps<{
  outline: OutlineItem[]
  editable?: boolean
  checkingOutlineId?: number | null
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'add'): void
  (e: 'expand-outline', outline: OutlineItem): void
  (e: 'edit-chapter', outline: OutlineItem): void
  (e: 'delete-chapter', chapterNumber: number): void
}>()

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineSection'
})
</script>
