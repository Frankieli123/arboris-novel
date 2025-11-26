<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">阵营管理</h2>
        <p class="text-sm text-slate-500">查看世界中的主要势力结构与关键成员</p>
      </div>
      <div v-if="editable" class="flex items-center gap-2 text-xs sm:text-sm text-slate-500">
        <span class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-slate-100 text-slate-600">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          共 {{ organizations.length }} 个阵营 · {{ totalMembers }} 名成员
        </span>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- 阵营列表 -->
      <div class="lg:col-span-1 space-y-3">
        <div class="text-xs text-slate-500 flex items-center justify-between">
          <span>阵营列表</span>
          <span v-if="organizations.length" class="text-slate-400">点击查看详情</span>
        </div>
        <div class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm divide-y divide-slate-100 max-h-[420px] overflow-y-auto">
          <button
            v-for="org in organizations"
            :key="org.id"
            type="button"
            class="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-slate-50 transition-colors"
            :class="org.id === selectedId ? 'bg-indigo-50/70 border-l-4 border-indigo-400 pl-3' : ''"
            @click="selectOrg(org.id)"
          >
            <div class="mt-0.5 flex-shrink-0">
              <div
                class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold"
                :class="org.id === selectedId ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'"
              >
                {{ org.name.slice(0, 2) || '阵营' }}
              </div>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between gap-2">
                <p class="text-sm font-semibold text-slate-900 truncate">{{ org.name || '未命名阵营' }}</p>
                <span class="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 whitespace-nowrap">
                  势力 {{ org.power_level }} / 成员 {{ org.member_count }}
                </span>
              </div>
              <p v-if="org.location" class="mt-1 text-xs text-slate-500 truncate">
                {{ org.location }}
              </p>
              <p v-else class="mt-1 text-xs text-slate-400 truncate">
                暂无所在地描述
              </p>
            </div>
          </button>
          <div v-if="!organizations.length" class="px-4 py-10 text-center text-slate-400 text-sm">
            暂无阵营数据，可先在世界设定中完善阵营设定
          </div>
        </div>
      </div>

      <!-- 阵营详情 & 成员列表 -->
      <div class="lg:col-span-2 space-y-4">
        <div
          v-if="currentOrg"
          class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6 space-y-4"
        >
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h3 class="text-xl font-semibold text-slate-900 flex items-center gap-2">
                <span>{{ currentOrg.name || '未命名阵营' }}</span>
                <span
                  v-if="currentOrg.color"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border border-slate-200 text-xs text-slate-500"
                >
                  <span
                    class="w-3 h-3 rounded-full border border-slate-200"
                    :style="{ backgroundColor: currentOrg.color }
                    "
                  ></span>
                  {{ currentOrg.color }}
                </span>
              </h3>
              <p class="mt-1 text-xs text-slate-500">
                势力等级：<span class="font-medium text-slate-800">{{ currentOrg.power_level }}</span>
                <span class="mx-1">·</span>
                层级：<span class="font-medium text-slate-800">{{ currentOrg.level }}</span>
                <span class="mx-1">·</span>
                成员数：<span class="font-medium text-slate-800">{{ currentOrg.member_count }}</span>
              </p>
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-slate-50/80 rounded-xl border border-slate-100 p-4 space-y-2">
              <h4 class="text-xs font-semibold text-slate-700 tracking-wide">阵营定位</h4>
              <p class="text-sm text-slate-600 whitespace-pre-line">
                {{ currentOrg.motto || '暂无宗旨或使命描述' }}
              </p>
            </div>
            <div class="bg-slate-50/80 rounded-xl border border-slate-100 p-4 space-y-2">
              <h4 class="text-xs font-semibold text-slate-700 tracking-wide">活动范围</h4>
              <p class="text-sm text-slate-600 whitespace-pre-line">
                {{ currentOrg.location || '暂无所在地或势力范围描述' }}
              </p>
            </div>
          </div>
        </div>
        <div
          v-else
          class="bg-white/95 rounded-2xl border border-dashed border-slate-300 p-10 text-center text-slate-400 text-sm flex items-center justify-center"
        >
          请选择左侧的一个阵营查看详情和成员
        </div>

        <div
          v-if="currentOrg"
          class="bg-white/95 rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6 space-y-4"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <h3 class="text-sm font-semibold text-slate-800">成员列表</h3>
              <span class="text-xs text-slate-400">共 {{ currentOrg.members.length }} 人</span>
            </div>
          </div>

          <div class="overflow-x-auto -mx-2 sm:mx-0">
            <table class="min-w-full text-xs sm:text-sm text-left text-slate-700">
              <thead class="bg-slate-50 border-b border-slate-200 text-[11px] sm:text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th class="px-3 py-2 font-medium">角色</th>
                  <th class="px-3 py-2 font-medium">职位</th>
                  <th class="px-3 py-2 font-medium">等级</th>
                  <th class="px-3 py-2 font-medium">忠诚</th>
                  <th class="px-3 py-2 font-medium">状态</th>
                  <th class="px-3 py-2 font-medium hidden sm:table-cell">加入时间</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="member in currentOrg.members"
                  :key="member.id"
                  class="border-b border-slate-100 hover:bg-slate-50/80 transition-colors"
                >
                  <td class="px-3 py-2 whitespace-nowrap">
                    <div class="flex items-center gap-2">
                      <div class="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center text-[11px] text-indigo-700 font-semibold">
                        {{ member.character_name.slice(0, 1) || '角' }}
                      </div>
                      <div class="min-w-0">
                        <p class="text-xs sm:text-sm font-medium text-slate-900 truncate">{{ member.character_name || '未知角色' }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="px-3 py-2 whitespace-nowrap text-xs sm:text-sm text-slate-700">
                    {{ member.position || '成员' }}
                  </td>
                  <td class="px-3 py-2 whitespace-nowrap text-xs sm:text-sm text-slate-700">
                    {{ member.rank ?? 0 }}
                  </td>
                  <td class="px-3 py-2 whitespace-nowrap">
                    <div class="flex items-center gap-2">
                      <div class="h-1.5 w-16 rounded-full bg-slate-100 overflow-hidden">
                        <div
                          class="h-1.5 rounded-full bg-emerald-500"
                          :style="{ width: Math.max(0, Math.min(100, member.loyalty)).toString() + '%' }"
                        ></div>
                      </div>
                      <span class="text-[11px] text-slate-500">
                        {{ member.loyalty }}
                      </span>
                    </div>
                  </td>
                  <td class="px-3 py-2 whitespace-nowrap text-xs sm:text-sm">
                    <span
                      class="inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] sm:text-xs"
                      :class="statusClass(member.status)"
                    >
                      {{ statusLabel(member.status) }}
                    </span>
                  </td>
                  <td class="px-3 py-2 whitespace-nowrap text-[11px] text-slate-500 hidden sm:table-cell">
                    {{ member.joined_at || '—' }}
                  </td>
                </tr>
                <tr v-if="!currentOrg.members.length">
                  <td class="px-3 py-6 text-center text-slate-400 text-xs" colspan="6">
                    暂无成员记录
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineProps, ref } from 'vue'
import type { OrganizationDetail } from '@/api/novel'

const props = defineProps<{
  data: { organizations?: OrganizationDetail[] } | null
  editable?: boolean
}>()

const selectedId = ref<number | null>(null)

const organizations = computed<OrganizationDetail[]>(() => props.data?.organizations || [])

const currentOrg = computed<OrganizationDetail | null>(() => {
  if (!organizations.value.length) return null
  const byId = organizations.value.find((o) => o.id === selectedId.value)
  return byId || organizations.value[0]
})

const totalMembers = computed(() => {
  return organizations.value.reduce((sum, org) => sum + (org.member_count || 0), 0)
})

const editable = computed(() => props.editable !== false)

const selectOrg = (id: number) => {
  selectedId.value = id
}

const statusLabel = (status: string) => {
  switch (status) {
    case 'active':
      return '在职'
    case 'retired':
      return '退休'
    case 'expelled':
      return '开除'
    case 'deceased':
      return '已故'
    default:
      return status || '未知'
  }
}

const statusClass = (status: string) => {
  switch (status) {
    case 'active':
      return 'bg-emerald-50 text-emerald-700 border-emerald-100'
    case 'retired':
      return 'bg-slate-50 text-slate-600 border-slate-200'
    case 'expelled':
      return 'bg-red-50 text-red-600 border-red-100'
    case 'deceased':
      return 'bg-slate-800 text-slate-100 border-slate-700'
    default:
      return 'bg-slate-50 text-slate-500 border-slate-200'
  }
}
</script>
