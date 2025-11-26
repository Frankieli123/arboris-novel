<template>
  <div class="h-screen flex flex-col overflow-hidden bg-gradient-to-br from-slate-50 via-blue-50/30 to-indigo-50/40">
    <!-- Header -->
    <header class="sticky top-0 z-40 bg-white/90 backdrop-blur-lg border-b border-slate-200/60 shadow-sm">
      <div class="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div class="flex items-center justify-between">
          <!-- Left: Title & Info -->
          <div class="flex items-center gap-3 flex-1 min-w-0">
            <button
              class="lg:hidden flex-shrink-0 p-2 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all duration-200"
              @click="toggleSidebar"
              aria-label="Toggle sidebar"
            >
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <div class="flex-1 min-w-0">
              <h1 class="text-xl sm:text-2xl lg:text-3xl font-bold text-slate-900 truncate">
                {{ formattedTitle }}
              </h1>
              <p v-if="overviewMeta.updated_at" class="text-xs sm:text-sm text-slate-500 mt-0.5">
                最近更新：{{ overviewMeta.updated_at }}
              </p>
            </div>
          </div>

          <!-- Right: Actions -->
          <div class="flex items-center gap-2 flex-shrink-0">
            <button
              class="px-3 py-2 sm:px-4 text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200 hover:shadow-md"
              @click="goBack"
            >
              <span class="hidden sm:inline">返回列表</span>
              <span class="sm:hidden">返回</span>
            </button>
            <button
              v-if="!isAdmin"
              class="px-3 py-2 sm:px-4 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 rounded-lg transition-all duration-200 shadow-md hover:shadow-lg"
              @click="goToWritingDesk"
            >
              <span class="hidden sm:inline">开始创作</span>
              <span class="sm:hidden">创作</span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <div class="flex max-w-[1800px] mx-auto w-full flex-1 min-h-0 overflow-hidden">
      <!-- Sidebar -->
      <aside
        class="fixed left-0 top-[73px] bottom-0 z-30 w-72 bg-white/95 backdrop-blur-lg border-r border-slate-200/60 shadow-2xl transform transition-transform duration-300 ease-out lg:translate-x-0"
        :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full'"
      >
        <!-- Sidebar Header -->
        <div class="hidden lg:flex items-center justify-between px-6 py-5 border-b border-slate-200/60">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500"></div>
            <span class="text-sm font-semibold text-slate-700 uppercase tracking-wide">
              {{ isAdmin ? '内容视图' : '蓝图导航' }}
            </span>
          </div>
        </div>

        <!-- Navigation -->
        <nav class="px-4 py-6 space-y-1.5 overflow-y-auto h-[calc(100%-5rem)] lg:h-[calc(100%-5rem)]">
          <button
            v-for="section in sections"
            :key="section.key"
            type="button"
            @click="switchSection(section.key)"
            :class="[
              'w-full group flex items-center gap-3 rounded-xl px-4 py-3.5 text-sm font-medium transition-all duration-200',
              activeSection === section.key
                ? 'bg-gradient-to-r from-indigo-50 to-indigo-100/80 text-indigo-700 shadow-sm ring-1 ring-indigo-200/50'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            ]"
          >
            <span
              class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg transition-all duration-200"
              :class="activeSection === section.key
                ? 'bg-gradient-to-br from-indigo-500 to-indigo-600 text-white shadow-md'
                : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'"
            >
              <component :is="getSectionIcon(section.key)" class="w-5 h-5" />
            </span>
            <span class="text-left flex-1">
              <span class="block font-semibold">{{ section.label }}</span>
              <span class="text-xs font-normal opacity-70">{{ section.description }}</span>
            </span>
          </button>
        </nav>
      </aside>

      <!-- Sidebar Overlay (Mobile) -->
      <transition
        enter-active-class="transition-opacity duration-300"
        leave-active-class="transition-opacity duration-300"
        enter-from-class="opacity-0"
        leave-to-class="opacity-0"
      >
        <div
          v-if="isSidebarOpen"
          class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-20 lg:hidden"
          @click="toggleSidebar"
        ></div>
      </transition>

      <!-- Main Content Area -->
      <div class="flex-1 lg:ml-72 min-h-0 flex flex-col h-full">
        <div class="flex-1 min-h-0 h-full px-4 sm:px-6 lg:px-8 xl:px-12 py-6 sm:py-8 flex flex-col overflow-hidden box-border">
          <div class="flex-1 flex flex-col min-h-0 h-full">
            <!-- Content Card -->
            <div class="flex-1 h-full bg-white/95 backdrop-blur-sm rounded-2xl border border-slate-200/60 shadow-xl p-6 sm:p-8 lg:p-10 min-h-[20rem] transition-shadow duration-300 hover:shadow-2xl flex flex-col box-border" :class="contentCardClass">
              <!-- Loading State -->
              <div v-if="isSectionLoading" class="flex flex-col items-center justify-center py-20 sm:py-28">
                <div class="relative">
                  <div class="w-12 h-12 border-4 border-indigo-100 rounded-full"></div>
                  <div class="absolute top-0 left-0 w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                </div>
                <p class="mt-4 text-sm text-slate-500">加载中...</p>
              </div>

              <!-- Error State -->
              <div v-else-if="currentError" class="flex flex-col items-center justify-center py-20 sm:py-28 space-y-4">
                <div class="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center">
                  <svg class="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <p class="text-slate-600 text-center">{{ currentError }}</p>
                <button
                  class="px-6 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 rounded-lg shadow-md hover:shadow-lg transition-all duration-200"
                  @click="reloadSection(activeSection, true)"
                >
                  重试
                </button>
              </div>

              <!-- Content -->
              <component
                v-else
                :is="currentComponent"
                v-bind="componentProps"
                :class="componentContainerClass"
                @edit="handleSectionEdit"
                @add="openOutlineGenerateModal"
                @expand-outline="startExpandOutline"
                @edit-chapter="openEditChapterOutline"
                @delete-chapter="handleChapterOutlineDelete"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Blueprint Edit Modal -->
    <BlueprintEditModal
      v-if="!isAdmin"
      :show="isModalOpen"
      :title="modalTitle"
      :content="modalContent"
      :field="modalField"
      @close="isModalOpen = false"
      @save="handleSave"
    />

    <!-- Outline Generate Modal -->
    <transition
      enter-active-class="transition-all duration-300"
      leave-active-class="transition-all duration-300"
      enter-from-class="opacity-0 scale-95"
      leave-to-class="opacity-0 scale-95"
    >
      <div v-if="isOutlineGenerateModalOpen && !isAdmin" class="fixed inset-0 z-50 flex items-center justify-center px-4">
        <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" @click="closeOutlineGenerateModal"></div>
        <div class="relative bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 sm:p-8 w-full max-w-2xl transform transition-all" @click.stop>
          <h3 class="text-xl font-bold text-slate-900 mb-2">生成大纲</h3>
          <p class="text-sm text-slate-500 mb-6">
            根据当前项目蓝图生成章节大纲，可选择重新生成完整结构，或在现有大纲基础上续写后续章节。
          </p>

          <div class="space-y-6">
            <div>
              <span class="block text-sm font-semibold text-slate-700 mb-2">生成模式</span>
              <div class="inline-flex rounded-full bg-slate-100 p-1">
                <button
                  type="button"
                  class="px-4 py-1.5 text-xs sm:text-sm font-medium rounded-full transition-colors duration-200"
                  :class="outlineGenerateMode === 'new'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-transparent text-slate-600 hover:text-slate-900'"
                  @click="outlineGenerateMode = 'new'"
                >
                  重新生成
                </button>
                <button
                  type="button"
                  class="ml-1 px-4 py-1.5 text-xs sm:text-sm font-medium rounded-full transition-colors duration-200"
                  :class="outlineGenerateMode === 'continue'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-transparent text-slate-600 hover:text-slate-900'"
                  @click="outlineGenerateMode = 'continue'"
                >
                  续写大纲
                </button>
              </div>
            </div>

            <!-- 重新生成模式 -->
            <div v-if="outlineGenerateMode === 'new'" class="space-y-4">
              <div>
                <label for="outline-new-count" class="block text-sm font-semibold text-slate-700 mb-1">
                  大纲章节数量
                </label>
                <input
                  id="outline-new-count"
                  v-model.number="outlineNewTotalChapters"
                  type="number"
                  min="1"
                  max="200"
                  class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200"
                  placeholder="例如：20"
                >
                <p class="mt-1 text-xs text-slate-400">将从第 1 章开始，重新规划整部作品的章节结构。</p>
              </div>
              <div>
                <label for="outline-new-extra" class="block text-sm font-semibold text-slate-700 mb-1">
                  其他要求
                </label>
                <textarea
                  id="outline-new-extra"
                  v-model="outlineNewOtherRequirements"
                  rows="3"
                  class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200 resize-none"
                  placeholder="例如：整体节奏偏快，前期冲突铺垫更多日常细节等"
                ></textarea>
              </div>
              <div>
                <label for="outline-auto-expand-new" class="block text-sm font-semibold text-slate-700 mb-1">
                  自动拆分章节数（可选）
                </label>
                <input
                  id="outline-auto-expand-new"
                  v-model.number="outlineAutoExpandTarget"
                  type="number"
                  min="1"
                  max="10"
                  class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200"
                  placeholder="例如：3 表示每条大纲自动拆成 3 章"
                >
                <p class="mt-1 text-xs text-slate-400">不填写则使用后台设置的自动拆分章节数。</p>
              </div>
            </div>

            <!-- 续写模式 -->
            <div v-else class="space-y-4">
              <div>
                <label for="outline-continue-direction" class="block text-sm font-semibold text-slate-700 mb-1">
                  故事发展方向
                </label>
                <textarea
                  id="outline-continue-direction"
                  v-model="outlineContinueStoryDirection"
                  rows="3"
                  class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200 resize-none"
                  placeholder="例如：主线进入对抗阶段，需要逐步升级冲突并埋下结局伏笔"
                ></textarea>
              </div>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label for="outline-plot-stage" class="block text-sm font-semibold text-slate-700 mb-1">
                    情节阶段
                  </label>
                  <select
                    id="outline-plot-stage"
                    v-model="outlineContinuePlotStage"
                    class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200"
                  >
                    <option value="development">发展阶段（推进矛盾与成长）</option>
                    <option value="climax">高潮阶段（集中爆发冲突）</option>
                    <option value="ending">结局阶段（收束线索与情感）</option>
                  </select>
                </div>
                <div>
                  <label for="outline-continue-count" class="block text-sm font-semibold text-slate-700 mb-1">
                    续写章节数
                  </label>
                  <input
                    id="outline-continue-count"
                    v-model.number="outlineContinueChapters"
                    type="number"
                    min="1"
                    max="100"
                    class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200"
                    placeholder="例如：5"
                  >
                  <p class="mt-1 text-xs text-slate-400">将在现有大纲最后一章之后，继续规划后续若干章节。</p>
                </div>
              </div>
              <div>
                <label for="outline-continue-extra" class="block text-sm font-semibold text-slate-700 mb-1">
                  其他要求
                </label>
                <textarea
                  id="outline-continue-extra"
                  v-model="outlineContinueOtherRequirements"
                  rows="3"
                  class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200 resize-none"
                  placeholder="例如：保持角色成长逻辑一致，适当增加配角线的戏份等"
                ></textarea>
              </div>
              <div>
                <label for="outline-auto-expand-continue" class="block text-sm font-semibold text-slate-700 mb-1">
                  自动拆分章节数（可选）
                </label>
                <input
                  id="outline-auto-expand-continue"
                  v-model.number="outlineAutoExpandTarget"
                  type="number"
                  min="1"
                  max="10"
                  class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all duration-200"
                  placeholder="例如：3 表示每条大纲自动拆成 3 章"
                >
                <p class="mt-1 text-xs text-slate-400">不填写则使用后台设置的自动拆分章节数。</p>
              </div>
            </div>
          </div>

          <div class="mt-8 flex justify-end gap-3">
            <button
              type="button"
              class="px-5 py-2.5 text-sm font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200"
              @click="closeOutlineGenerateModal"
            >
              取消
            </button>
            <button
              type="button"
              class="px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 rounded-lg shadow-md hover:shadow-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="outlineGenerateLoading"
              @click="handleOutlineGenerate"
            >
              {{ outlineGenerateLoading ? '生成中...' : '开始生成' }}
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Edit Single Chapter Outline Modal -->
    <WDEditChapterModal
      v-if="!isAdmin"
      :show="isChapterEditModalOpen"
      :chapter="editingChapterOutline"
      @close="isChapterEditModalOpen = false"
      @save="handleChapterOutlineSave"
    />

    <!-- Existing Expanded Chapters Preview Modal -->
    <transition
      enter-active-class="transition-all duration-300"
      leave-active-class="transition-all duration-300"
      enter-from-class="opacity-0 scale-95"
      leave-to-class="opacity-0 scale-95"
    >
      <div v-if="isExpandPreviewModalOpen && !isAdmin" class="fixed inset-0 z-50 flex items-center justify-center px-4">
        <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" @click="isExpandPreviewModalOpen = false"></div>
        <div class="relative bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 sm:p-8 w-full max-w-4xl" @click.stop>
          <div class="flex items-center justify-between mb-4 gap-3">
            <div>
              <h3 class="text-xl font-bold text-slate-900">
                大纲：第{{ expandTargetOutline?.chapter_number }}章《{{ expandTargetOutline?.title || '未命名章节' }}》
              </h3>
            </div>
          </div>

          <div v-if="existingExpansion && existingExpansion.expansion_plans && existingExpansion.expansion_plans.length" class="mb-4">
            <div class="flex gap-2 overflow-x-auto pb-2">
              <button
                v-for="(plan, idx) in existingExpansion.expansion_plans"
                :key="idx"
                type="button"
                class="px-3 py-1.5 text-xs rounded-lg border transition-all whitespace-nowrap"
                :class="idx === previewActiveIndex
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                  : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'"
                @click="previewActiveIndex = idx"
              >
                章节 {{ plan.sub_index }}：{{ plan.title }}
              </button>
            </div>
          </div>

          <div
            v-if="existingExpansion && existingExpansion.expansion_plans && existingExpansion.expansion_plans.length"
            class="max-h-[26rem] overflow-y-auto space-y-4 pr-3"
          >
            <div
              v-for="(plan, idx) in existingExpansion.expansion_plans"
              v-show="idx === previewActiveIndex"
              :key="idx"
              class="space-y-4"
            >
              <!-- 子章节头部信息 -->
              <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div>
                  <div class="text-base sm:text-lg font-semibold text-slate-900 leading-snug">
                    {{ plan.title || '未命名章节' }}
                  </div>
                </div>
                <div class="flex flex-wrap gap-1.5 text-xs text-slate-600 justify-start md:justify-end">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-lg bg-blue-50 text-blue-600 border border-blue-100">
                    {{ plan.emotional_tone || '情绪未标注' }}
                  </span>
                  <span class="inline-flex items-center px-2 py-0.5 rounded-lg bg-orange-50 text-orange-600 border border-orange-100">
                    {{ plan.conflict_type || '冲突未标注' }}
                  </span>
                  <span class="inline-flex items-center px-2 py-0.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-100">
                    约 {{ plan.estimated_words || 0 }} 字
                  </span>
                </div>
              </div>

              <!-- 主要内容分区 -->
              <div class="grid grid-cols-1 gap-4">
                <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                  <div class="flex items-center justify-between mb-2">
                    <h4 class="text-sm font-semibold text-slate-800">情节概要</h4>
                    <button
                      type="button"
                      class="text-slate-300 hover:text-indigo-500 transition-colors"
                      @click="openPlanFieldEditor(plan, 'plot_summary', idx)"
                    >
                      <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                        <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                      </svg>
                    </button>
                  </div>
                  <div v-if="isEditingPlanField('plot_summary', idx)">
                    <textarea
                      ref="planEditTextarea"
                      v-model="planEditRaw"
                      rows="4"
                      class="w-full rounded-lg border border-slate-300 bg-transparent text-sm text-slate-600 leading-6 px-3 py-2 resize-none focus:outline-none focus:border-slate-400 transition-all duration-200"
                    ></textarea>
                    <div class="mt-3 flex justify-end gap-2">
                      <button
                        type="button"
                        class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200"
                        @click="cancelPlanEdit"
                      >
                        取消
                      </button>
                      <button
                        type="button"
                        class="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-all duration-200 disabled:opacity-50"
                        :disabled="planEditSaving"
                        @click="savePlanEdit"
                      >
                        {{ planEditSaving ? '保存中...' : '保存' }}
                      </button>
                    </div>
                  </div>
                  <p v-else class="text-sm text-slate-600 whitespace-pre-line leading-6">
                    {{ plan.plot_summary || '暂无情节概要' }}
                  </p>
                </div>
                <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                  <div class="flex items-center justify-between mb-2">
                    <h4 class="text-sm font-semibold text-slate-800">叙事目标</h4>
                    <button
                      type="button"
                      class="text-slate-300 hover:text-indigo-500 transition-colors"
                      @click="openPlanFieldEditor(plan, 'narrative_goal', idx)"
                    >
                      <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                        <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                      </svg>
                    </button>
                  </div>
                  <div v-if="isEditingPlanField('narrative_goal', idx)">
                    <textarea
                      ref="planEditTextarea"
                      v-model="planEditRaw"
                      rows="4"
                      class="w-full rounded-lg border border-slate-300 bg-transparent text-sm text-slate-600 leading-6 px-3 py-2 resize-none focus:outline-none focus:border-slate-400 transition-all duration-200"
                    ></textarea>
                    <div class="mt-3 flex justify-end gap-2">
                      <button
                        type="button"
                        class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200"
                        @click="cancelPlanEdit"
                      >
                        取消
                      </button>
                      <button
                        type="button"
                        class="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-all duration-200 disabled:opacity-50"
                        :disabled="planEditSaving"
                        @click="savePlanEdit"
                      >
                        {{ planEditSaving ? '保存中...' : '保存' }}
                      </button>
                    </div>
                  </div>
                  <p v-else class="text-sm text-slate-600 whitespace-pre-line leading-6">
                    {{ plan.narrative_goal || '暂无叙事目标说明' }}
                  </p>
                </div>
              </div>

              <div class="grid grid-cols-1 gap-4">
                <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                  <div class="flex items-center justify-between mb-2">
                    <h4 class="text-sm font-semibold text-slate-800">关键事件</h4>
                    <button
                      type="button"
                      class="text-slate-300 hover:text-indigo-500 transition-colors"
                      @click="openPlanFieldEditor(plan, 'key_events', idx)"
                    >
                      <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                        <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                      </svg>
                    </button>
                  </div>
                  <div v-if="isEditingPlanField('key_events', idx)">
                    <textarea
                      ref="planEditTextarea"
                      v-model="planEditRaw"
                      rows="4"
                      class="w-full rounded-lg border border-slate-300 bg-transparent text-sm text-slate-600 leading-6 px-3 py-2 resize-none focus:outline-none focus:border-slate-400 transition-all duration-200"
                    ></textarea>
                    <div class="mt-3 flex justify-end gap-2">
                      <button
                        type="button"
                        class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200"
                        @click="cancelPlanEdit"
                      >
                        取消
                      </button>
                      <button
                        type="button"
                        class="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-all duration-200 disabled:opacity-50"
                        :disabled="planEditSaving"
                        @click="savePlanEdit"
                      >
                        {{ planEditSaving ? '保存中...' : '保存' }}
                      </button>
                    </div>
                  </div>
                  <ul v-else class="text-sm text-slate-600 space-y-1">
                    <li
                      v-for="(ev, evIdx) in plan.key_events || []"
                      :key="evIdx"
                      class="flex items-start gap-1.5"
                    >
                      <span class="mt-1 h-1.5 w-1.5 rounded-full bg-slate-400 flex-shrink-0"></span>
                      <span>{{ ev }}</span>
                    </li>
                    <li v-if="!plan.key_events || !plan.key_events.length" class="text-xs text-slate-400">
                      暂无关键事件描述
                    </li>
                  </ul>
                </div>

                <div
                  v-if="plan.scenes && plan.scenes.length"
                  class="bg-white rounded-xl border border-slate-200 shadow-sm p-4"
                >
                  <div class="flex items-center justify-between mb-2">
                    <h4 class="text-sm font-semibold text-slate-800">场景列表</h4>
                    <button
                      type="button"
                      class="text-slate-300 hover:text-indigo-500 transition-colors"
                      @click="openPlanFieldEditor(plan, 'scenes', idx)"
                    >
                      <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                        <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                      </svg>
                    </button>
                  </div>
                  <div v-if="isEditingPlanField('scenes', idx)">
                    <textarea
                      ref="planEditTextarea"
                      v-model="planEditRaw"
                      rows="4"
                      class="w-full rounded-lg border border-slate-300 bg-transparent text-sm text-slate-600 leading-6 px-3 py-2 resize-none focus:outline-none focus:border-slate-400 transition-all duration-200"
                    ></textarea>
                    <div class="mt-3 flex justify-end gap-2">
                      <button
                        type="button"
                        class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200"
                        @click="cancelPlanEdit"
                      >
                        取消
                      </button>
                      <button
                        type="button"
                        class="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-all duration-200 disabled:opacity-50"
                        :disabled="planEditSaving"
                        @click="savePlanEdit"
                      >
                        {{ planEditSaving ? '保存中...' : '保存' }}
                      </button>
                    </div>
                  </div>
                  <ol v-else class="text-sm text-slate-600 space-y-1 list-decimal list-inside">
                    <li
                      v-for="(scene, sIdx) in plan.scenes"
                      :key="sIdx"
                      class="whitespace-pre-line"
                    >
                      {{ scene }}
                    </li>
                  </ol>
                </div>

                <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-3">
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <h4 class="text-sm font-semibold text-slate-800">涉及角色</h4>
                      <button
                        type="button"
                        class="text-slate-300 hover:text-indigo-500 transition-colors"
                        @click="openPlanFieldEditor(plan, 'character_focus', idx)"
                      >
                        <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                          <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                          <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                        </svg>
                      </button>
                    </div>
                    <div v-if="isEditingPlanField('character_focus', idx)">
                      <textarea
                        ref="planEditTextarea"
                        v-model="planEditRaw"
                        rows="4"
                        class="w-full rounded-lg border border-slate-300 bg-transparent text-xs text-slate-600 leading-5 px-3 py-2 resize-none focus:outline-none focus:border-slate-400 transition-all duration-200"
                      ></textarea>
                      <div class="mt-3 flex justify-end gap-2">
                        <button
                          type="button"
                          class="px-3 py-1.5 text-xs font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200"
                          @click="cancelPlanEdit"
                        >
                          取消
                        </button>
                        <button
                          type="button"
                          class="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-all duration-200 disabled:opacity-50"
                          :disabled="planEditSaving"
                          @click="savePlanEdit"
                        >
                          {{ planEditSaving ? '保存中...' : '保存' }}
                        </button>
                      </div>
                    </div>
                    <div v-else class="flex flex-wrap gap-1.5 text-xs text-slate-600">
                      <span
                        v-for="(char, cIdx) in plan.character_focus || []"
                        :key="cIdx"
                        class="inline-flex items-center px-2 py-0.5 rounded-lg bg-purple-50 text-purple-600 border border-purple-100"
                      >
                        {{ char }}
                      </span>
                      <span v-if="!plan.character_focus || !plan.character_focus.length" class="text-xs text-slate-400">
                        暂无角色标注
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="text-sm text-slate-500 mt-2">
            当前大纲已创建章节，但缺少详细规划信息。
          </div>

          <div class="mt-6 flex justify-end gap-3">
            <button
              type="button"
              class="px-5 py-2.5 text-sm font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200"
              @click="isExpandPreviewModalOpen = false"
            >
              关闭
            </button>
            <button
              type="button"
              class="px-5 py-2.5 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition-all duration-200 disabled:opacity-50"
              :disabled="deleteExpandedLoading || !existingExpansion || !existingExpansion.chapter_count"
              @click="handleDeleteExpandedChapters"
            >
              {{ deleteExpandedLoading ? '删除中...' : `删除所有展开章节 (${existingExpansion?.chapter_count || 0} 章)` }}
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Outline Expansion Modal -->
    <transition
      enter-active-class="transition-all duration-300"
      leave-active-class="transition-all duration-300"
      enter-from-class="opacity-0 scale-95"
      leave-to-class="opacity-0 scale-95"
    >
      <div v-if="isExpandModalOpen && !isAdmin" class="fixed inset-0 z-50 flex items-center justify-center px-4">
        <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" @click="isExpandModalOpen = false"></div>
        <div class="relative bg-white rounded-2xl shadow-2xl border border-slate-200 p-6 sm:p-8 w-full max-w-3xl" @click.stop>
          <h3 class="text-xl font-bold text-slate-900 mb-2">展开章节大纲</h3>
          <p class="text-sm text-slate-500 mb-6">
            将当前大纲拆分为多章详细规划，可选择是否自动创建章节记录。
          </p>

          <div v-if="expandTargetOutline" class="mb-6 p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
            <div class="text-sm text-slate-500">
              当前大纲：第{{ expandTargetOutline.chapter_number }}章《{{ expandTargetOutline.title || '未命名章节' }}》
            </div>
            <div class="text-sm text-slate-600 whitespace-pre-line">
              {{ expandTargetOutline.summary || '暂无摘要' }}
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">目标章节数</label>
              <input
                v-model.number="expandTargetCount"
                type="number"
                min="1"
                max="10"
                class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
              >
              <p class="mt-1 text-xs text-slate-400">建议 2-5 章，用于细化当前大纲。</p>
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700 mb-1">展开策略</label>
              <select
                v-model="expandStrategy"
                class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
              >
                <option value="balanced">均衡展开（默认）</option>
                <option value="climax">高潮重点</option>
                <option value="detail">细节丰富</option>
              </select>
            </div>
            <div class="flex items-center gap-2">
              <input
                id="enable-scene-analysis"
                v-model="enableSceneAnalysis"
                type="checkbox"
                class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              >
              <label for="enable-scene-analysis" class="text-sm text-slate-700">生成场景级规划</label>
            </div>
            <div class="flex items-center gap-2">
              <input
                id="auto-create-chapters"
                v-model="autoCreateChapters"
                type="checkbox"
                class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              >
              <label for="auto-create-chapters" class="text-sm text-slate-700">自动创建章节记录</label>
            </div>
          </div>

          <div v-if="expandResult" class="mt-4 border-t border-slate-200 pt-4 max-h-80 overflow-y-auto">
            <h4 class="text-sm font-semibold text-slate-800 mb-3">
              展开结果：共 {{ expandResult.actual_chapter_count }} 章规划
            </h4>
            <ol class="space-y-3 text-sm text-slate-700">
              <li
                v-for="plan in expandResult.chapter_plans"
                :key="plan.sub_index + '-' + plan.title"
                class="p-3 rounded-xl bg-slate-50 border border-slate-200"
              >
                <div class="flex items-center justify-between mb-1">
                  <span class="font-semibold">章节 {{ plan.sub_index }}：{{ plan.title }}</span>
                  <span class="text-xs text-slate-400">预计字数：{{ plan.estimated_words }}</span>
                </div>
                <p class="text-xs text-slate-600 mb-1">剧情摘要：{{ plan.plot_summary }}</p>
                <p class="text-xs text-slate-500">情感基调：{{ plan.emotional_tone }} ｜ 叙事目标：{{ plan.narrative_goal }}</p>
              </li>
            </ol>
          </div>

          <div class="mt-8 flex justify-end gap-3">
            <button
              type="button"
              class="px-5 py-2.5 text-sm font-medium text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-all duration-200"
              @click="isExpandModalOpen = false"
            >
              关闭
            </button>
            <button
              type="button"
              class="px-5 py-2.5 text-sm font-medium text-white bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-700 hover:to-indigo-800 rounded-lg shadow-md hover:shadow-lg transition-all duration-200 disabled:opacity-50"
              :disabled="expandLoading || !expandTargetOutline || !expandTargetOutline.id"
              @click="performExpandOutline"
            >
              {{ expandLoading ? '展开中...' : '展开大纲' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, h, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { NovelAPI } from '@/api/novel'
import { AdminAPI } from '@/api/admin'
import type { NovelProject, NovelSectionResponse, NovelSectionType, ChapterOutline, OutlineExpansionResponse, OutlineChaptersResponse, ChapterPlanItem, OrganizationDetail } from '@/api/novel'
import BlueprintEditModal from '@/components/BlueprintEditModal.vue'
import OverviewSection from '@/components/novel-detail/OverviewSection.vue'
import WorldSettingSection from '@/components/novel-detail/WorldSettingSection.vue'
import CharactersSection from '@/components/novel-detail/CharactersSection.vue'
import RelationshipsSection from '@/components/novel-detail/RelationshipsSection.vue'
import ChapterOutlineSection from '@/components/novel-detail/ChapterOutlineSection.vue'
import ChaptersSection from '@/components/novel-detail/ChaptersSection.vue'
import FactionsManagementSection from '@/components/novel-detail/FactionsManagementSection.vue'
import WDEditChapterModal from '@/components/writing-desk/WDEditChapterModal.vue'

interface Props {
  isAdmin?: boolean
}

type SectionKey = NovelSectionType | 'organizations'

type PlanFieldKey = 'plot_summary' | 'narrative_goal' | 'key_events' | 'scenes' | 'character_focus'

const props = withDefaults(defineProps<Props>(), {
  isAdmin: false
})

const route = useRoute()
const router = useRouter()
const novelStore = useNovelStore()

const projectId = route.params.id as string
const isSidebarOpen = ref(typeof window !== 'undefined' ? window.innerWidth >= 1024 : true)

const sections: Array<{ key: SectionKey; label: string; description: string }> = [
  { key: 'overview', label: '项目概览', description: '定位与整体梗概' },
  { key: 'world_setting', label: '世界设定', description: '规则、地点与阵营' },
  { key: 'organizations', label: '阵营管理', description: '主要势力与关键成员' },
  { key: 'characters', label: '主要角色', description: '人物性格与目标' },
  { key: 'relationships', label: '人物关系', description: '角色之间的联系' },
  { key: 'chapter_outline', label: '大纲管理', description: props.isAdmin ? '故事章节规划' : '故事结构规划' },
  { key: 'chapters', label: '章节内容', description: props.isAdmin ? '生成章节与正文' : '生成状态与摘要' }
]

const sectionComponents: Record<SectionKey, any> = {
  overview: OverviewSection,
  world_setting: WorldSettingSection,
  organizations: FactionsManagementSection,
  characters: CharactersSection,
  relationships: RelationshipsSection,
  chapter_outline: ChapterOutlineSection,
  chapters: ChaptersSection
}

// Section icons as functional components
const getSectionIcon = (key: SectionKey) => {
  const icons: Record<SectionKey, any> = {
    overview: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('rect', { x: 3, y: 3, width: 18, height: 18, rx: 2 }),
      h('line', { x1: 3, y1: 9, x2: 21, y2: 9 }),
      h('line', { x1: 9, y1: 21, x2: 9, y2: 9 })
    ]),
    world_setting: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('circle', { cx: 12, cy: 12, r: 10 }),
      h('path', { d: 'M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z' })
    ]),
    organizations: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' })
    ]),
    characters: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2' }),
      h('circle', { cx: 9, cy: 7, r: 4 }),
      h('path', { d: 'M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75' })
    ]),
    relationships: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2' }),
      h('circle', { cx: 9, cy: 7, r: 4 }),
      h('path', { d: 'M22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75' })
    ]),
    chapter_outline: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('line', { x1: 8, y1: 6, x2: 21, y2: 6 }),
      h('line', { x1: 8, y1: 12, x2: 21, y2: 12 }),
      h('line', { x1: 8, y1: 18, x2: 21, y2: 18 }),
      h('line', { x1: 3, y1: 6, x2: 3.01, y2: 6 }),
      h('line', { x1: 3, y1: 12, x2: 3.01, y2: 12 }),
      h('line', { x1: 3, y1: 18, x2: 3.01, y2: 18 })
    ]),
    chapters: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M4 19.5A2.5 2.5 0 016.5 17H20' }),
      h('path', { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' })
    ])
  }
  return icons[key]
}

const sectionData = reactive<Partial<Record<SectionKey, any>>>({})
const sectionLoading = reactive<Record<SectionKey, boolean>>({
  overview: false,
  world_setting: false,
  organizations: false,
  characters: false,
  relationships: false,
  chapter_outline: false,
  chapters: false
})
const sectionError = reactive<Record<SectionKey, string | null>>({
  overview: null,
  world_setting: null,
  organizations: null,
  characters: null,
  relationships: null,
  chapter_outline: null,
  chapters: null
})

const overviewMeta = reactive<{ title: string; updated_at: string | null }>({
  title: '加载中...',
  updated_at: null
})

const activeSection = ref<SectionKey>('overview')

// Modal state (user mode only)
const isModalOpen = ref(false)
const modalTitle = ref('')
const modalContent = ref<any>('')
const modalField = ref('')

// Outline generate modal state (user mode only)
const isOutlineGenerateModalOpen = ref(false)
const outlineGenerateMode = ref<'new' | 'continue'>('continue')
const outlineNewTotalChapters = ref<number | null>(null)
const outlineNewOtherRequirements = ref('')
const outlineContinueStoryDirection = ref('')
const outlineContinuePlotStage = ref<'development' | 'climax' | 'ending'>('development')
const outlineContinueChapters = ref<number | null>(null)
const outlineContinueOtherRequirements = ref('')
const outlineAutoExpandTarget = ref<number | null>(null)
const outlineGenerateLoading = ref(false)
const originalBodyOverflow = ref('')

// Single chapter outline edit modal (user mode only)
const isChapterEditModalOpen = ref(false)
const editingChapterOutline = ref<ChapterOutline | null>(null)

// Expansion plan field inline edit (user mode only)
const planEditField = ref<PlanFieldKey | null>(null)
const planEditRaw = ref('')
const planEditChapterNumber = ref<number | null>(null)
const planEditPlanIndex = ref<number | null>(null)
const planEditSaving = ref(false)

const planEditTextarea = ref<HTMLTextAreaElement | null>(null)

const resizePlanEditTextarea = () => {
  const el = planEditTextarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

watch(planEditRaw, () => {
  nextTick(resizePlanEditTextarea)
})

const isEditingPlanField = (field: PlanFieldKey, index: number) =>
  planEditField.value === field && planEditPlanIndex.value === index

const openPlanFieldEditor = (plan: ChapterPlanItem, field: PlanFieldKey, index: number) => {
  const chapters = existingExpansion.value?.chapters || []
  const chapterMeta = chapters[index]

  planEditField.value = field

  const rawValue = (plan as any)[field]
  if (Array.isArray(rawValue)) {
    planEditRaw.value = rawValue.join('\n')
  } else {
    planEditRaw.value = rawValue || ''
  }

  planEditChapterNumber.value = chapterMeta?.chapter_number ?? null
  planEditPlanIndex.value = index
  nextTick(resizePlanEditTextarea)
}

const cancelPlanEdit = () => {
  planEditField.value = null
  planEditPlanIndex.value = null
  planEditRaw.value = ''
  planEditChapterNumber.value = null
}

const savePlanEdit = async () => {
  if (planEditSaving.value) return
  planEditSaving.value = true
  try {
    if (!planEditField.value || planEditChapterNumber.value == null || planEditPlanIndex.value == null) {
      return
    }

    const expansion = existingExpansion.value
    if (!expansion || !expansion.expansion_plans || !expansion.expansion_plans[planEditPlanIndex.value]) {
      return
    }

    const originalPlan = expansion.expansion_plans[planEditPlanIndex.value]

    let newValue: any = planEditRaw.value
    if (['key_events', 'scenes', 'character_focus'].includes(planEditField.value)) {
      newValue = planEditRaw.value
        .split('\n')
        .map(line => line.trim())
        .filter(line => line.length > 0)
    }

    const updatedPlan: ChapterPlanItem = {
      ...originalPlan,
      [planEditField.value]: newValue
    }

    await NovelAPI.updateChapterExpansionPlan(projectId, planEditChapterNumber.value, updatedPlan)

    // 同步更新本地预览数据
    expansion.expansion_plans.splice(planEditPlanIndex.value, 1, updatedPlan)
  } catch (error) {
    console.error('保存变更失败:', error)
  } finally {
    planEditSaving.value = false
    cancelPlanEdit()
  }
}

// Outline expansion modal (user mode only)
const isExpandModalOpen = ref(false)
const expandTargetOutline = ref<ChapterOutline | null>(null)
const expandTargetCount = ref(3)
const expandStrategy = ref<'balanced' | 'climax' | 'detail'>('balanced')
const enableSceneAnalysis = ref(false)
const autoCreateChapters = ref(true)
const expandLoading = ref(false)
const expandResult = ref<OutlineExpansionResponse | null>(null)

// Existing expanded chapters preview
const isExpandPreviewModalOpen = ref(false)
const existingExpansion = ref<OutlineChaptersResponse | null>(null)
const previewActiveIndex = ref(0)
const deleteExpandedLoading = ref(false)

// 当前正在检查是否已有展开章节的大纲 ID（仅用户模式）
const checkingOutlineId = ref<number | null>(null)

const novel = computed(() => !props.isAdmin ? novelStore.currentProject as NovelProject | null : null)

const formattedTitle = computed(() => {
  const title = overviewMeta.title || '加载中...'
  return title.startsWith('《') && title.endsWith('》') ? title : `《${title}》`
})

const componentContainerClass = computed(() => {
  const fillSections: SectionKey[] = ['chapters']
  return fillSections.includes(activeSection.value)
    ? 'flex-1 min-h-0 h-full flex flex-col overflow-hidden'
    : 'overflow-y-auto'
})

const contentCardClass = computed(() => {
  const fillSections: SectionKey[] = ['chapters']
  return fillSections.includes(activeSection.value)
    ? 'overflow-hidden'
    : 'overflow-visible'
})

// 懒加载完整项目（仅在需要编辑时）
const ensureProjectLoaded = async () => {
  if (props.isAdmin || !projectId) return
  if (novel.value) return // 已加载
  await novelStore.loadProject(projectId)
}

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const handleResize = () => {
  if (typeof window === 'undefined') return
  isSidebarOpen.value = window.innerWidth >= 1024
}

const loadSection = async (section: SectionKey, force = false) => {
  if (!projectId) return
  if (!force && sectionData[section]) {
    return
  }

  sectionLoading[section] = true
  sectionError[section] = null
  try {
    if (section === 'organizations') {
      // 阵营管理使用单独的组织接口
      if (props.isAdmin) {
        sectionData[section] = { organizations: [] as OrganizationDetail[] }
      } else {
        const organizations = await NovelAPI.getOrganizations(projectId)
        sectionData[section] = { organizations }
      }
    } else {
      const response: NovelSectionResponse = props.isAdmin
        ? await AdminAPI.getNovelSection(projectId, section as NovelSectionType)
        : await NovelAPI.getSection(projectId, section as NovelSectionType)
      sectionData[section] = response.data
      if (section === 'overview') {
        overviewMeta.title = response.data?.title || overviewMeta.title
        overviewMeta.updated_at = response.data?.updated_at || null
      }
    }
  } catch (error) {
    console.error('加载模块失败:', error)
    sectionError[section] = error instanceof Error ? error.message : '加载失败'
  } finally {
    sectionLoading[section] = false
  }
}

const reloadSection = (section: SectionKey, force = false) => {
  loadSection(section, force)
}

const switchSection = (section: SectionKey) => {
  activeSection.value = section
  if (typeof window !== 'undefined' && window.innerWidth < 1024) {
    isSidebarOpen.value = false
  }
  loadSection(section)
}

const goBack = () => router.push(props.isAdmin ? '/admin' : '/workspace')

const goToWritingDesk = async () => {
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return
  const path = project.title === '未命名灵感' ? `/inspiration?project_id=${project.id}` : `/novel/${project.id}`
  router.push(path)
}

const currentComponent = computed(() => sectionComponents[activeSection.value])
const isSectionLoading = computed(() => sectionLoading[activeSection.value])
const currentError = computed(() => sectionError[activeSection.value])

const componentProps = computed(() => {
  const data = sectionData[activeSection.value]
  const editable = !props.isAdmin

  switch (activeSection.value) {
    case 'overview':
      return { data: data || null, editable }
    case 'world_setting':
      return { data: data || null, editable }
    case 'characters':
      return { data: data || null, editable }
    case 'relationships':
      return { data: data || null, editable }
    case 'organizations':
      return { data: data || null, editable }
    case 'chapter_outline':
      return { outline: data?.chapter_outline || [], editable, checkingOutlineId: checkingOutlineId.value }
    case 'chapters':
      return { chapters: data?.chapters || [], isAdmin: props.isAdmin }
    default:
      return {}
  }
})

const handleSectionEdit = (payload: { field: string; title: string; value: any }) => {
  if (props.isAdmin) return
  modalField.value = payload.field
  modalTitle.value = payload.title
  modalContent.value = payload.value
  isModalOpen.value = true
}

const resolveSectionKey = (field: string): SectionKey => {
  if (field.startsWith('world_setting')) return 'world_setting'
  if (field.startsWith('characters')) return 'characters'
  if (field.startsWith('relationships')) return 'relationships'
  if (field.startsWith('chapter_outline')) return 'chapter_outline'
  return 'overview'
}

const handleSave = async (data: { field: string; content: any }) => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  const { field, content } = data
  const payload: Record<string, any> = {}

  if (field.includes('.')) {
    const [parentField, childField] = field.split('.')
    payload[parentField] = {
      ...(project.blueprint?.[parentField as keyof typeof project.blueprint] as Record<string, any> | undefined),
      [childField]: content
    }
  } else {
    payload[field] = content
  }

  try {
    const updatedProject = await NovelAPI.updateBlueprint(project.id, payload)
    novelStore.setCurrentProject(updatedProject)
    const sectionToReload = resolveSectionKey(field)
    await loadSection(sectionToReload, true)
    if (sectionToReload !== 'overview') {
      await loadSection('overview', true)
    }
    isModalOpen.value = false
  } catch (error) {
    console.error('保存变更失败:', error)
  }
}

const openOutlineGenerateModal = async () => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  const existingOutline = project.blueprint?.chapter_outline || []

  if (existingOutline.length > 0) {
    outlineGenerateMode.value = 'continue'
    const lastNumber = Math.max(...existingOutline.map(ch => ch.chapter_number))
    const defaultContinueCount = Math.min(10, Math.max(3, existingOutline.length - lastNumber + 3))
    outlineContinueChapters.value = defaultContinueCount
    outlineNewTotalChapters.value = existingOutline.length
  } else {
    outlineGenerateMode.value = 'new'
    outlineNewTotalChapters.value = 20
    outlineContinueChapters.value = null
  }

  outlineNewOtherRequirements.value = ''
  outlineContinueStoryDirection.value = ''
  outlineContinuePlotStage.value = 'development'
  outlineContinueOtherRequirements.value = ''
  outlineAutoExpandTarget.value = null

  isOutlineGenerateModalOpen.value = true
}

const closeOutlineGenerateModal = () => {
  isOutlineGenerateModalOpen.value = false
}

const handleOutlineGenerate = async () => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  const existingOutline = project.blueprint?.chapter_outline || []

  let startChapter = 1
  let numChapters = 0

  if (outlineGenerateMode.value === 'new') {
    if (!outlineNewTotalChapters.value || outlineNewTotalChapters.value <= 0) {
      alert('请填写有效的大纲章节数量')
      return
    }
    startChapter = 1
    numChapters = outlineNewTotalChapters.value
  } else {
    if (!existingOutline.length) {
      alert('当前项目暂无章节大纲，无法续写，请先生成完整大纲。')
      return
    }
    if (!outlineContinueChapters.value || outlineContinueChapters.value <= 0) {
      alert('请填写有效的续写章节数')
      return
    }
    const lastNumber = Math.max(...existingOutline.map(ch => ch.chapter_number))
    startChapter = lastNumber + 1
    numChapters = outlineContinueChapters.value
  }

  if (outlineAutoExpandTarget.value != null) {
    if (outlineAutoExpandTarget.value <= 0 || outlineAutoExpandTarget.value > 10) {
      alert('自动拆分章节数需在 1 到 10 之间')
      return
    }
  }

  let storyDirection = ''
  let plotStage: 'development' | 'climax' | 'ending' = 'development'
  let keepExisting = true

  if (outlineGenerateMode.value === 'new') {
    storyDirection = outlineNewOtherRequirements.value.trim()
    plotStage = 'development'
    keepExisting = false
  } else {
    const baseDirection = outlineContinueStoryDirection.value.trim()
    const extra = outlineContinueOtherRequirements.value.trim()
    if (baseDirection && extra) {
      storyDirection = `${baseDirection}\n其他要求：${extra}`
    } else if (baseDirection) {
      storyDirection = baseDirection
    } else if (extra) {
      storyDirection = `其他要求：${extra}`
    }
    plotStage = outlineContinuePlotStage.value
    keepExisting = true
  }

  if (outlineGenerateMode.value === 'new') {
    const confirmationMessage = '重新生成大纲将清空当前项目的所有章节大纲和章节内容，此操作无法撤销，是否继续？'
    if (!window.confirm(confirmationMessage)) {
      return
    }
  }

  outlineGenerateLoading.value = true
  try {
    const options: any = {
      mode: outlineGenerateMode.value,
      story_direction: storyDirection,
      plot_stage: plotStage,
      keep_existing: keepExisting
    }
    if (outlineAutoExpandTarget.value != null) {
      options.auto_expand_target_chapter_count = outlineAutoExpandTarget.value
    }

    const updatedProject = await NovelAPI.generateChapterOutline(
      project.id,
      startChapter,
      numChapters,
      options
    )
    novelStore.setCurrentProject(updatedProject)
    await loadSection('chapter_outline', true)
    await loadSection('overview', true)
    isOutlineGenerateModalOpen.value = false
  } catch (error) {
    console.error('生成大纲失败:', error)
  } finally {
    outlineGenerateLoading.value = false
  }
}

const openEditChapterOutline = (outline: any) => {
  if (props.isAdmin) return
  editingChapterOutline.value = {
    id: outline.id,
    chapter_number: outline.chapter_number,
    title: outline.title || '',
    summary: outline.summary || ''
  }
  isChapterEditModalOpen.value = true
}

const handleChapterOutlineSave = async (updated: ChapterOutline) => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  try {
    await novelStore.updateChapterOutline(updated)
    await loadSection('chapter_outline', true)
    isChapterEditModalOpen.value = false
  } catch (error) {
    console.error('更新章节大纲失败:', error)
  }
}

const handleChapterOutlineDelete = async (chapterNumber: number) => {
  if (props.isAdmin) return
  if (!window.confirm('确定删除该章节大纲以及对应章节吗？')) return
  await ensureProjectLoaded()
  try {
    await novelStore.deleteChapter(chapterNumber)
    await loadSection('chapter_outline', true)
    await loadSection('chapters', true)
  } catch (error) {
    console.error('删除章节失败:', error)
  }
}

const startExpandOutline = async (outline: ChapterOutline) => {
  if (props.isAdmin) return
  expandTargetOutline.value = outline

  if (!projectId || !outline.id) {
    // 缺少必要 ID 时退化为直接展开配置
    expandTargetCount.value = 3
    expandStrategy.value = 'balanced'
    enableSceneAnalysis.value = false
    autoCreateChapters.value = true
    expandResult.value = null
    isExpandModalOpen.value = true
    return
  }

  try {
    checkingOutlineId.value = outline.id
    const existing = await NovelAPI.getOutlineChapters(projectId, outline.id)
    if (existing.has_chapters && existing.expansion_plans && existing.expansion_plans.length > 0) {
      existingExpansion.value = existing
      previewActiveIndex.value = 0
      isExpandPreviewModalOpen.value = true
      return
    }
  } catch (error) {
    console.error('检查已展开章节失败:', error)
    // 检查失败时不阻塞用户，继续走普通展开流程
  } finally {
    checkingOutlineId.value = null
  }

  expandTargetCount.value = 3
  expandStrategy.value = 'balanced'
  enableSceneAnalysis.value = false
  autoCreateChapters.value = true
  expandResult.value = null
  isExpandModalOpen.value = true
}

const handleDeleteExpandedChapters = async () => {
  if (props.isAdmin) return
  if (!existingExpansion.value || !existingExpansion.value.chapter_count) {
    isExpandPreviewModalOpen.value = false
    return
  }

  if (!window.confirm(`此操作将删除当前大纲已展开的所有 ${existingExpansion.value.chapter_count} 个章节，章节内容删除后无法恢复，确认继续？`)) {
    return
  }

  await ensureProjectLoaded()
  const chapterNumbers = existingExpansion.value.chapters.map(ch => ch.chapter_number)
  if (!chapterNumbers.length || !projectId) {
    return
  }

  deleteExpandedLoading.value = true
  try {
    await novelStore.deleteChapter(chapterNumbers)
    await loadSection('chapter_outline', true)
    await loadSection('chapters', true)
    isExpandPreviewModalOpen.value = false
  } catch (error) {
    console.error('删除展开章节失败:', error)
  } finally {
    deleteExpandedLoading.value = false
  }
}

const performExpandOutline = async () => {
  if (props.isAdmin) return
  if (!projectId || !expandTargetOutline.value || !expandTargetOutline.value.id) {
    alert('当前大纲缺少必要信息，无法展开')
    return
  }
  expandLoading.value = true
  try {
    const response = await NovelAPI.expandOutline(projectId, expandTargetOutline.value.id, {
      target_chapter_count: expandTargetCount.value,
      expansion_strategy: expandStrategy.value,
      enable_scene_analysis: enableSceneAnalysis.value,
      auto_create_chapters: autoCreateChapters.value
    })
    expandResult.value = response
    await loadSection('chapter_outline', true)
    await loadSection('chapters', true)
  } catch (error) {
    console.error('展开大纲失败:', error)
  } finally {
    expandLoading.value = false
  }
}

onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', handleResize)
  }
  if (typeof document !== 'undefined') {
    originalBodyOverflow.value = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }

  // 只加载必要的 section 数据，不预加载完整项目
  await loadSection('overview', true)
  loadSection('world_setting')
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleResize)
  }
  if (typeof document !== 'undefined') {
    document.body.style.overflow = originalBodyOverflow.value || ''
  }
})
</script>

<style scoped>
/* Smooth scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
