<template>
  <div class="plugin-management">
    <div class="outer-plugin-card">
      <div class="card-header">
        <span class="card-title">MCP 插件管理</span>
        <div class="card-actions">
          <button
            type="button"
            class="card-refresh-button"
            :disabled="refreshLoading"
            @click="refreshPlugins"
          >
            {{ refreshLoading ? '刷新中...' : '刷新' }}
          </button>
          <button
            v-if="isAdmin"
            type="button"
            class="primary-gradient-button"
            @click="openCreateModal"
          >
            添加插件
          </button>
        </div>
      </div>
      <n-alert type="info" class="plugin-info-alert" :bordered="false">
        默认插件由管理员配置，你可以启用/禁用它们，或添加自己的插件
      </n-alert>

      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <div class="plugin-content-area">
        <n-spin :show="loading">
          <template #icon>
            <div class="test-loading-spinner"></div>
          </template>
          <div v-if="plugins.length" class="plugin-list">
            <n-card
              v-for="plugin in plugins"
              :key="plugin.id"
              class="plugin-card"
              :bordered="true"
            >
            <div class="plugin-card-body">
              <div class="plugin-main">
                <div class="plugin-title-row">
                  <span class="plugin-name">{{ plugin.display_name }}</span>
                  <n-tag
                    size="small"
                    :type="plugin.enabled ? 'primary' : 'default'"
                  >
                    {{ plugin.enabled ? '运行中' : '已停用' }}
                  </n-tag>
                  <n-tag
                    v-if="plugin.plugin_type"
                    size="small"
                    type="info"
                  >
                    {{ plugin.plugin_type.toUpperCase() }}
                  </n-tag>
                  <n-tag
                    v-if="plugin.category"
                    size="small"
                    type="info"
                  >
                    {{ plugin.category }}
                  </n-tag>
                  <n-tag
                    v-if="plugin.is_default"
                    size="small"
                    type="warning"
                  >
                    默认
                  </n-tag>
                </div>
                <div class="plugin-subtitle-row">
                  {{ plugin.plugin_name }}
                </div>
                <div class="plugin-url-row">
                  {{ maskSensitiveUrl(plugin.server_url) }}
                </div>
              </div>

              <div class="plugin-actions">
                <div class="plugin-switch">
                  <span class="plugin-switch-label">
                    {{
                      plugin.user_enabled === null
                        ? '我的状态：未设置'
                        : plugin.user_enabled
                          ? '我的状态：已启用'
                          : '我的状态：已禁用'
                    }}
                  </span>
                  <n-switch
                    :value="plugin.user_enabled === null ? false : plugin.user_enabled"
                    size="small"
                    :rail-style="primarySwitchRailStyle"
                    @update:value="() => togglePlugin(plugin)"
                  />
                </div>
                <n-space size="small" class="plugin-action-buttons">
                  <n-button
                    v-if="isAdmin"
                    size="small"
                    quaternary
                    class="icon-button"
                    aria-label="测试连接"
                    title="测试连接"
                    @click="testPlugin(plugin.id)"
                  >
                    <svg
                      v-if="!(testing && testingPluginId === plugin.id)"
                      class="w-4 h-4"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path d="M13 2L4 14h7l-1 8L20 10h-7z" />
                    </svg>
                    <svg
                      v-else
                      class="w-4 h-4 icon-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <circle
                        cx="12"
                        cy="12"
                        r="7"
                        stroke-dasharray="3 3"
                      />
                    </svg>
                  </n-button>
                  <n-button
                    size="small"
                    quaternary
                    class="icon-button"
                    aria-label="查看工具"
                    title="查看工具"
                    @click="() => viewTools(plugin)"
                  >
                    <svg
                      v-if="!(toolsLoading && currentToolsPlugin && currentToolsPlugin.id === plugin.id)"
                      class="w-4 h-4"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path
                        d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"
                      />
                    </svg>
                    <svg
                      v-else
                      class="w-4 h-4 icon-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <circle
                        cx="12"
                        cy="12"
                        r="7"
                        stroke-dasharray="3 3"
                      />
                    </svg>
                  </n-button>
                  <n-button
                    v-if="isAdmin"
                    size="small"
                    quaternary
                    class="icon-button"
                    aria-label="编辑插件"
                    title="编辑插件"
                    @click="() => openEditPluginModal(plugin)"
                  >
                    <svg
                      class="w-4 h-4"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path d="M4 20h16" />
                      <path d="M15.5 4.5l4 4L10 18H6v-4z" />
                    </svg>
                  </n-button>
                  <n-popconfirm
                    v-if="isAdmin"
                    :positive-text="'删除'"
                    :negative-text="'取消'"
                    type="error"
                    placement="left"
                    @positive-click="() => deletePlugin(plugin.id)"
                  >
                    <template #trigger>
                      <n-button
                        size="small"
                        quaternary
                        class="icon-button icon-button-danger"
                        type="error"
                        aria-label="删除插件"
                        title="删除插件"
                      >
                        <svg
                          class="w-4 h-4"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        >
                          <path d="M9.75 9.75v7.5" />
                          <path d="M14.25 9.75v7.5" />
                          <path
                            d="M5.25 6.75h13.5M9.75 4.5h4.5a1.5 1.5 0 011.5 1.5v0H8.25v0a1.5 1.5 0 011.5-1.5z"
                          />
                          <path
                            d="M18 6.75v10.5A2.25 2.25 0 0115.75 19.5H8.25A2.25 2.25 0 016 17.25V6.75"
                          />
                        </svg>
                      </n-button>
                    </template>
                    确认删除该插件？
                  </n-popconfirm>
                </n-space>
              </div>
            </div>
          </n-card>
          </div>

          <n-result
            v-else
            status="info"
            title="暂无插件"
            description="点击右上角“添加插件”导入 MCP 插件"
          />
        </n-spin>
      </div>
    </div>
  </div>

  <!-- 创建/编辑插件模态框（原生结构） -->
  <div
    v-if="pluginModalVisible"
    class="pm-overlay"
  >
    <div
      class="pm-overlay-backdrop"
      @click="closePluginModal"
    ></div>
    <div class="pm-modal-card pm-modal-lg">
      <div class="pm-modal-header">
        <h3 class="pm-modal-title">
          {{ modalTitle }}
        </h3>
        <button
          type="button"
          class="pm-modal-close"
          aria-label="关闭"
          @click="closePluginModal"
        >
          <svg
            viewBox="0 0 20 20"
            class="pm-close-icon"
          >
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>

      <div class="pm-modal-body">
        <div class="pm-form">
          <div class="pm-info-block">
            粘贴标准 MCP 配置 JSON，系统会自动提取插件名称，支持 HTTP 和 Stdio 类型。
          </div>

          <div class="pm-field">
            <label class="pm-field-label">* MCP 配置 JSON</label>
            <textarea
              v-model="importJson"
              class="pm-textarea"
              rows="16"
              placeholder='{
  "mcpServers": {
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?exaApiKey=YOUR_API_KEY",
      "headers": {}
    }
  }
}'
            ></textarea>
            <p class="pm-field-hint">请粘贴完整的 MCP 配置 JSON，确保格式合法。</p>
          </div>

          <div class="pm-field">
            <label class="pm-field-label">插件分类（可选）</label>
            <select
              v-model="importCategory"
              class="pm-select"
            >
              <option :value="null">不指定分类</option>
              <option
                v-for="opt in categoryOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
            <p class="pm-field-hint">用于帮助 AI 更好地匹配插件使用场景。</p>
          </div>
        </div>
      </div>

      <div class="pm-modal-footer">
        <div class="pm-footer-actions">
          <button
            type="button"
            class="pm-btn-secondary"
            @click="closePluginModal"
          >
            取消
          </button>
          <button
            type="button"
            class="pm-btn-primary"
            :disabled="saving"
            @click="submitPlugin"
          >
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 导入结果模态框（原生结构） -->
  <div
    v-if="importResultModalVisible"
    class="pm-overlay"
  >
    <div
      class="pm-overlay-backdrop"
      @click="importResultModalVisible = false"
    ></div>
    <div class="pm-modal-card pm-modal-sm">
      <div class="pm-modal-header">
        <h3 class="pm-modal-title">导入结果</h3>
        <button
          type="button"
          class="pm-modal-close"
          aria-label="关闭"
          @click="importResultModalVisible = false"
        >
          <svg
            viewBox="0 0 20 20"
            class="pm-close-icon"
          >
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>

      <div class="pm-modal-body import-result-body">
        <div v-if="!importResult" class="import-result-empty">
          暂无导入结果
        </div>
        <div v-else class="import-result-content">
          <div
            class="import-status-block"
            :class="importResult.errors.length === 0 ? 'import-status-success' : 'import-status-error'"
          >
            <h3 class="import-status-title">
              {{ importResult.summary }}
            </h3>
          </div>

          <div v-if="importResult.created.length > 0" class="import-section-card">
            <div class="import-section-title">成功导入</div>
            <ul class="import-section-list">
              <li v-for="name in importResult.created" :key="name">{{ name }}</li>
            </ul>
          </div>

          <div v-if="importResult.skipped.length > 0" class="import-section-card">
            <div class="import-section-title">已跳过（已存在）</div>
            <ul class="import-section-list">
              <li v-for="name in importResult.skipped" :key="name">{{ name }}</li>
            </ul>
          </div>

          <div
            v-if="importResult.errors.length > 0"
            class="import-section-card import-section-error-card"
          >
            <div class="import-section-title">导入失败</div>
            <ul class="import-section-list">
              <li v-for="error in importResult.errors" :key="error">{{ error }}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 测试结果模态框（原生结构） -->
  <div
    v-if="testModalVisible"
    class="pm-overlay"
  >
    <div
      class="pm-overlay-backdrop"
      @click="testModalVisible = false"
    ></div>
    <div class="pm-modal-card pm-modal-sm">
      <div class="pm-modal-header">
        <h3 class="pm-modal-title">插件测试结果</h3>
        <button
          type="button"
          class="pm-modal-close"
          aria-label="关闭"
          @click="testModalVisible = false"
        >
          <svg viewBox="0 0 20 20" class="pm-close-icon">
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>

      <div class="pm-modal-body test-modal-body">
        <div v-if="testing" class="test-modal-loading">
          <div class="test-loading-spinner"></div>
          <p class="test-loading-text">正在测试插件连接...</p>
        </div>
        <div v-else-if="testReport" class="test-modal-content">
          <div
            class="test-status-block"
            :class="testReport.success ? 'test-status-block-success' : 'test-status-block-error'"
          >
            <div class="test-status-icon">
              <svg
                v-if="testReport.success"
                viewBox="0 0 24 24"
                class="test-status-svg"
              >
                <path d="M5 13l4 4 10-10" />
              </svg>
              <svg
                v-else
                viewBox="0 0 24 24"
                class="test-status-svg"
              >
                <path d="M6 6l12 12" />
                <path d="M18 6l-12 12" />
              </svg>
            </div>
            <div class="test-status-text">
              <h3 class="test-status-title">
                {{ testReport.success ? '测试成功' : '测试失败' }}
              </h3>
              <p class="test-status-desc">
                {{ testReport.message }}
              </p>
            </div>
          </div>

          <div class="test-section-card">
            <div class="test-section-label">工具数量</div>
            <div class="test-section-value">{{ testReport.tools_count }}</div>
            <div v-if="testReport.error" class="test-section-label">错误信息</div>
            <div v-if="testReport.error" class="test-section-value test-section-error">
              {{ testReport.error }}
            </div>
          </div>

          <div v-if="testReport.suggestions.length > 0" class="test-section-card">
            <div class="test-section-title">建议</div>
            <ul class="test-suggestion-list">
              <li
                v-for="(suggestion, index) in testReport.suggestions"
                :key="index"
              >
                {{ suggestion }}
              </li>
            </ul>
          </div>
        </div>
        <div v-else class="test-modal-empty">
          暂无测试结果
        </div>
      </div>
    </div>
  </div>

  <!-- 工具列表模态框（原生结构） -->
  <div
    v-if="toolsModalVisible"
    class="pm-overlay"
  >
    <div
      class="pm-overlay-backdrop"
      @click="toolsModalVisible = false"
    ></div>
    <div class="pm-modal-card pm-modal-md">
      <div class="pm-modal-header">
        <h3 class="pm-modal-title">
          {{ currentToolsPlugin ? `工具列表 - ${currentToolsPlugin.display_name}` : '工具列表' }}
        </h3>
        <button
          type="button"
          class="pm-modal-close"
          aria-label="关闭"
          @click="toolsModalVisible = false"
        >
          <svg viewBox="0 0 20 20" class="pm-close-icon">
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>

      <div class="pm-modal-body tools-modal-body">
        <div v-if="toolsLoading" class="tools-modal-loading">
          <div class="test-loading-spinner"></div>
          <p class="test-loading-text">正在加载工具列表...</p>
        </div>
        <div v-else-if="tools.length === 0" class="tools-empty-state">
          <h3 class="tools-empty-title">暂无工具</h3>
          <p class="tools-empty-desc">该插件未提供任何工具定义</p>
        </div>
        <div v-else class="tools-list">
          <div
            v-for="tool in tools"
            :key="tool.function.name"
            class="tool-card"
          >
            <div
              v-if="tool.type && tool.type !== 'function'"
              class="tool-card-header"
            >
              <span class="tool-type-tag">{{ tool.type }}</span>
            </div>
            <div class="tool-field">
              <div class="tool-field-label">工具名称</div>
              <div class="tool-field-value">{{ tool.function.name }}</div>
            </div>
            <div
              v-if="tool.function.description"
              class="tool-field"
            >
              <div class="tool-field-label">描述</div>
              <div class="tool-field-value">
                {{ tool.function.description }}
              </div>
            </div>
            <div
              v-if="tool.function.parameters"
              class="tool-field"
            >
              <div class="tool-field-label">输入参数</div>
              <pre class="tool-params-json">
{{ formatParameters(tool.function.parameters) }}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 编辑插件模态框（原生结构） -->
  <div
    v-if="pluginEditModalVisible"
    class="pm-overlay"
  >
    <div
      class="pm-overlay-backdrop"
      @click="closeEditPluginModal"
    ></div>
    <div class="pm-modal-card pm-modal-md">
      <div class="pm-modal-header">
        <h3 class="pm-modal-title">编辑插件</h3>
        <button
          type="button"
          class="pm-modal-close"
          aria-label="关闭"
          @click="closeEditPluginModal"
        >
          <svg viewBox="0 0 20 20" class="pm-close-icon">
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>

      <div class="pm-modal-body">
        <div class="pm-form">
          <div class="pm-field">
            <label class="pm-field-label">插件标识符 (plugin_name)</label>
            <input
              v-model="pluginForm.plugin_name"
              class="pm-input pm-input-disabled"
              type="text"
              disabled
            />
          </div>

          <div class="pm-field">
            <label class="pm-field-label">显示名称</label>
            <input
              v-model="pluginForm.display_name"
              class="pm-input"
              type="text"
              placeholder="用于在界面中展示的名称"
            />
          </div>

          <div class="pm-field">
            <label class="pm-field-label">服务器地址</label>
            <input
              v-model="pluginForm.server_url"
              class="pm-input"
              type="text"
              placeholder="例如：https://.../mcp?key=***"
            />
          </div>

          <div class="pm-field">
            <label class="pm-field-label">分类</label>
            <select
              v-model="pluginForm.category"
              class="pm-select"
            >
              <option :value="null">未分类</option>
              <option
                v-for="opt in categoryOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div class="pm-field pm-field-inline">
            <label class="pm-field-label">启用状态</label>
            <div class="pm-switch-row">
              <input
                id="edit-plugin-enabled"
                v-model="pluginForm.enabled"
                type="checkbox"
                class="pm-switch-input"
              />
              <label for="edit-plugin-enabled" class="pm-switch-label">
                {{ pluginForm.enabled ? '已启用' : '已禁用' }}
              </label>
            </div>
          </div>

          <div class="pm-field">
            <label class="pm-field-label">Headers JSON（可选）</label>
            <textarea
              v-model="headersJson"
              class="pm-textarea"
              rows="4"
              placeholder='例如：{"Authorization": "Bearer ..."}'
            ></textarea>
          </div>

          <div class="pm-field">
            <label class="pm-field-label">Config JSON（可选）</label>
            <textarea
              v-model="configJson"
              class="pm-textarea"
              rows="6"
              placeholder="插件自定义配置 JSON"
            ></textarea>
          </div>
        </div>
      </div>

      <div class="pm-modal-footer">
        <div class="pm-footer-actions">
          <button
            type="button"
            class="pm-btn-secondary"
            @click="closeEditPluginModal"
          >
            取消
          </button>
          <button
            type="button"
            class="pm-btn-primary"
            :disabled="editSaving"
            @click="submitEditPlugin"
          >
            {{ editSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NDataTable,
  NPopconfirm,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  type DataTableColumns
} from 'naive-ui'

import {
  MCPAPI,
  type MCPPlugin,
  type MCPPluginCreate,
  type PluginTestReport,
  type ImportPluginsResponse,
  type ToolDefinition
} from '@/api/mcp'
import { useAlert } from '@/composables/useAlert'
import { useAuthStore } from '@/stores/auth'

const { showAlert } = useAlert()
const authStore = useAuthStore()

const isAdmin = computed(() => authStore.user?.is_admin || false)

const plugins = ref<MCPPlugin[]>([])
const loading = ref(false)
const refreshLoading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testingPluginId = ref<number | null>(null)
const error = ref<string | null>(null)

const pluginModalVisible = ref(false)
const testModalVisible = ref(false)
const importResultModalVisible = ref(false)
const isCreateMode = ref(true)
const testReport = ref<PluginTestReport | null>(null)
const importResult = ref<ImportPluginsResponse | null>(null)

const toolsModalVisible = ref(false)
const toolsLoading = ref(false)
const tools = ref<ToolDefinition[]>([])
const currentToolsPlugin = ref<MCPPlugin | null>(null)

const pluginEditModalVisible = ref(false)
const editSaving = ref(false)

const importJson = ref('')
const importCategory = ref<string | null>(null)

const categoryOptions = [
  { label: '搜索类 (Search) - 网络搜索、信息查询', value: 'search' },
  { label: '文件系统 (Filesystem) - 文件读写、目录操作', value: 'filesystem' },
  { label: '数据库 (Database) - 数据查询、数据管理', value: 'database' },
  { label: '分析类 (Analysis) - 数据分析 / 文本处理', value: 'analysis' },
  { label: 'API集成 (API) - 第三方服务调用', value: 'api' },
  { label: '工具类 (Tools) - 实用工具、辅助功能', value: 'tools' },
  { label: '其他 (Other)', value: 'other' }
]

const pluginForm = reactive<MCPPluginCreate & { id?: number}>(
  {
    plugin_name: '',
    display_name: '',
    plugin_type: 'http',
    server_url: '',
    headers: null,
    enabled: true,
    category: null,
    config: null
  }
)

const headersJson = ref('')
const configJson = ref('')

const rowKey = (row: MCPPlugin) => row.id

const modalTitle = computed(() => (isCreateMode.value ? '添加插件' : '编辑插件'))

const formatParameters = (params: Record<string, any>) => JSON.stringify(params, null, 2)

const primarySwitchRailStyle = ({ checked }: any) => {
  return {
    background: checked
      ? 'linear-gradient(to right, #4f46e5, #6366f1)'
      : '#e5e7eb'
  }
}

const maskSensitiveUrl = (url: string | null | undefined): string => {
  if (!url) return ''
  try {
    const [base, query] = url.split('?', 2)
    if (!query) return url
    const masked = query
      .split('&')
      .map((part) => {
        const [rawKey, rawValue = ''] = part.split('=', 2)
        if (!rawValue) return part
        const keyLower = rawKey.toLowerCase()
        if (keyLower === 'key' || keyLower === 'api_key' || keyLower.endsWith('key')) {
          return `${rawKey}=***`
        }
        return part
      })
      .join('&')
    return `${base}?${masked}`
  } catch {
    return url
  }
}

const fetchPlugins = async () => {
  loading.value = true
  error.value = null
  try {
    plugins.value = await MCPAPI.listPlugins()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载插件列表失败'
  } finally {
    loading.value = false
  }
}

const refreshPlugins = async () => {
  refreshLoading.value = true
  try {
    await fetchPlugins()
  } finally {
    refreshLoading.value = false
  }
}

const openCreateModal = () => {
  isCreateMode.value = true
  importJson.value = ''
  importCategory.value = null
  pluginModalVisible.value = true
}

const openEditPluginModal = (plugin: MCPPlugin) => {
  pluginForm.id = plugin.id
  pluginForm.plugin_name = plugin.plugin_name
  pluginForm.display_name = plugin.display_name
  pluginForm.plugin_type = plugin.plugin_type
  pluginForm.server_url = plugin.server_url
  pluginForm.headers = plugin.headers || null
  pluginForm.enabled = plugin.enabled
  pluginForm.category = plugin.category || null
  pluginForm.config = plugin.config || null
  headersJson.value = plugin.headers ? JSON.stringify(plugin.headers, null, 2) : ''
  configJson.value = plugin.config ? JSON.stringify(plugin.config, null, 2) : ''
  pluginEditModalVisible.value = true
}

const closeEditPluginModal = () => {
  pluginEditModalVisible.value = false
  editSaving.value = false
}

const submitEditPlugin = async () => {
  if (!pluginForm.id) {
    showAlert('缺少插件ID，无法保存', 'error')
    return
  }

  if (headersJson.value.trim()) {
    try {
      pluginForm.headers = JSON.parse(headersJson.value)
    } catch {
      showAlert('Headers JSON 格式错误', 'error')
      return
    }
  } else {
    pluginForm.headers = null
  }

  if (configJson.value.trim()) {
    try {
      pluginForm.config = JSON.parse(configJson.value)
    } catch {
      showAlert('Config JSON 格式错误', 'error')
      return
    }
  } else {
    pluginForm.config = null
  }

  editSaving.value = true
  try {
    const updated = await MCPAPI.updatePlugin(pluginForm.id, {
      display_name: pluginForm.display_name,
      server_url: pluginForm.server_url,
      headers: pluginForm.headers || null,
      enabled: pluginForm.enabled,
      category: pluginForm.category || null,
      config: pluginForm.config || null
    })
    const index = plugins.value.findIndex((p) => p.id === updated.id)
    if (index !== -1) {
      plugins.value.splice(index, 1, updated)
    }
    showAlert('插件已更新', 'success')
    closeEditPluginModal()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '更新失败', 'error')
  } finally {
    editSaving.value = false
  }
}

const viewTools = async (plugin: MCPPlugin) => {
  toolsLoading.value = true
  currentToolsPlugin.value = plugin
  tools.value = []
  try {
    tools.value = await MCPAPI.getPluginTools(plugin.id)
    toolsModalVisible.value = true
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '获取工具列表失败', 'error')
  } finally {
    toolsLoading.value = false
  }
}

const closePluginModal = () => {
  pluginModalVisible.value = false
  saving.value = false
}

const submitPlugin = async () => {
  if (!importJson.value.trim()) {
    showAlert('请输入 MCP 配置 JSON', 'error')
    return
  }

  let mcpConfig: any
  try {
    mcpConfig = JSON.parse(importJson.value)
  } catch (err) {
    showAlert('JSON 格式错误', 'error')
    return
  }

  // 如果用户选择了分类，为所有插件添加分类
  if (importCategory.value && mcpConfig.mcpServers) {
    for (const pluginName in mcpConfig.mcpServers) {
      if (!mcpConfig.mcpServers[pluginName].category) {
        mcpConfig.mcpServers[pluginName].category = importCategory.value
      }
    }
  }

  saving.value = true
  try {
    importResult.value = await MCPAPI.importPluginsFromJson(mcpConfig)
    closePluginModal()
    importResultModalVisible.value = true

    // 刷新插件列表
    if (importResult.value.created.length > 0) {
      await fetchPlugins()
    }
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '导入失败', 'error')
  } finally {
    saving.value = false
  }
}

const deletePlugin = async (id: number) => {
  try {
    await MCPAPI.deletePlugin(id)
    plugins.value = plugins.value.filter((p) => p.id !== id)
    showAlert('插件已删除', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '删除失败', 'error')
  }
}

const togglePlugin = async (plugin: MCPPlugin) => {
  try {
    const newEnabled = plugin.user_enabled === null ? true : !plugin.user_enabled
    const result = await MCPAPI.togglePlugin(plugin.id, newEnabled)
    const index = plugins.value.findIndex((p) => p.id === plugin.id)
    if (index !== -1) {
      plugins.value[index].user_enabled = result.enabled
    }
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '切换失败', 'error')
  }
}

const testPlugin = async (id: number) => {
  if (testing.value) return

  testing.value = true
  testingPluginId.value = id
  testReport.value = null
  try {
    testReport.value = await MCPAPI.testPlugin(id)
    testModalVisible.value = true
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '测试失败', 'error')
  } finally {
    testing.value = false
    testingPluginId.value = null
  }
}

const columns: DataTableColumns<MCPPlugin> = [
  {
    title: '插件名称',
    key: 'display_name',
    width: 180,
    ellipsis: { tooltip: true },
    render(row) {
      return h('span', [
        row.display_name,
        row.is_default
          ? h(
              NTag,
              { size: 'small', type: 'info', style: { marginLeft: '8px' } },
              { default: () => '默认' }
            )
          : null
      ])
    }
  },
  {
    title: '标识符',
    key: 'plugin_name',
    width: 150,
    ellipsis: { tooltip: true }
  },
  {
    title: '服务器地址',
    key: 'server_url',
    ellipsis: { tooltip: true }
  },
  {
    title: '分类',
    key: 'category',
    width: 120,
    render(row) {
      return row.category
        ? h(
            NTag,
            { size: 'small', type: 'info' },
            { default: () => row.category }
          )
        : '—'
    }
  },
  {
    title: '全局状态',
    key: 'enabled',
    width: 100,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { size: 'small', type: row.enabled ? 'primary' : 'default' },
        { default: () => (row.enabled ? '启用' : '禁用') }
      )
    }
  },
  {
    title: '我的状态',
    key: 'user_enabled',
    width: 100,
    align: 'center',
    render(row) {
      if (row.user_enabled === null) {
        return h(
          NTag,
          { size: 'small', type: 'default' },
          { default: () => '未设置' }
        )
      }
      return h(
        NTag,
        { size: 'small', type: row.user_enabled ? 'primary' : 'default' },
        { default: () => (row.user_enabled ? '已启用' : '已禁用') }
      )
    }
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 360,
    render(row) {
      const actions = [
        h(
          NButton,
          {
            size: 'small',
            type: row.user_enabled ? 'warning' : 'success',
            tertiary: true,
            onClick: () => togglePlugin(row)
          },
          { default: () => (row.user_enabled ? '禁用' : '启用') }
        ),
        h(
          NButton,
          {
            size: 'small',
            tertiary: true,
            onClick: () => viewTools(row)
          },
          { default: () => '查看工具' }
        )
      ]

      if (isAdmin.value) {
        actions.push(
          h(
            NButton,
            {
              size: 'small',
              type: 'info',
              tertiary: true,
              onClick: () => testPlugin(row.id)
            },
            { default: () => '测试连接' }
          ),
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              tertiary: true,
              onClick: () => openEditPluginModal(row)
            },
            { default: () => '编辑' }
          ),
          h(
            NPopconfirm,
            {
              'positive-text': '删除',
              'negative-text': '取消',
              type: 'error',
              placement: 'left',
              onPositiveClick: () => deletePlugin(row.id)
            },
            {
              default: () => '确认删除该插件？',
              trigger: () =>
                h(
                  NButton,
                  { size: 'small', type: 'error', quaternary: true },
                  { default: () => '删除' }
                )
            }
          )
        )
      }

      return h(
        NSpace,
        { justify: 'center', size: 'small' },
        { default: () => actions }
      )
    }
  }
]

onMounted(() => {
  fetchPlugins()
})
</script>

<style scoped>
.plugin-management {
  width: 100%;
  display: flex;
  justify-content: center;
}

.outer-plugin-card {
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  border-radius: 16px; /* rounded-2xl */
  background: rgba(255, 255, 255, 0.7); /* bg-white/70 */
  box-shadow: 0 10px 15px rgba(15, 23, 42, 0.12), 0 4px 6px rgba(15, 23, 42, 0.06); /* shadow-lg */
  padding: 32px; /* p-8 */
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.card-title {
  font-size: 1.5rem; /* 接近 text-2xl 的页面标题 */
  font-weight: 700;   /* font-bold */
  color: #1f2937;     /* text-gray-800 */
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-refresh-button {
  min-height: 32px;
  padding: 0 10px;
  font-size: 0.875rem;
  font-weight: 500;
  color: #4b5563; /* text-gray-600 */
  background: transparent;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.card-refresh-button:disabled {
  opacity: 0.7;
  cursor: default;
}

.primary-gradient-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  line-height: 1.25;
  background: linear-gradient(to right, #4f46e5, #6366f1);
  color: #ffffff;
  border: none;
  border-radius: 16px;
  box-shadow: 0 10px 25px rgba(79, 70, 229, 0.28);
  cursor: pointer;
  transition: background-color 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease;
}

.primary-gradient-button:hover {
  background: linear-gradient(to right, #4338ca, #4f46e5);
  box-shadow: 0 14px 30px rgba(79, 70, 229, 0.32);
}

.primary-gradient-button :deep(.n-button__border),
.primary-gradient-button :deep(.n-button__state-border) {
  display: none;
}

.primary-gradient-button :deep(.n-button__content) {
  color: #ffffff;
}

.plugin-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plugin-card {
  border-radius: 16px; /* rounded-2xl，与大纲章节卡片一致的弧度层级 */
  background: rgba(255, 255, 255, 0.95); /* bg-white/95 */
  border: 1px solid #e5e7eb; /* border-slate-200 */
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05); /* shadow-sm，与章节卡片一致 */
}

.plugin-card-body {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 16px;
  padding: 12px 16px; /* 统一内边距，避免文字顶到卡片边缘 */
}

.plugin-main {
  flex: 1;
  min-width: 0;
}

.plugin-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}

.plugin-title-row :deep(.n-tag) {
  border-radius: 8px;
}

.plugin-name {
  font-weight: 600;
  font-size: 14px;
}

.plugin-subtitle-row {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

.plugin-url-row {
  font-size: 12px;
  color: #4b5563;
  word-break: break-all;
}

.plugin-info-alert {
  margin-top: 12px;
  margin-bottom: 16px;
  border-radius: 12px;
}

.plugin-content-area {
  margin-top: 24px;
}

.plugin-info-alert :deep(.n-alert-body)
  {
  background: #eff6ff;
  border-radius: 12px;
  color: #1d4ed8;
}

.plugin-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 8px;
  min-width: 200px;
}

.plugin-action-buttons {
  justify-content: flex-end;
}

.icon-button {
  padding: 6px;
  border-radius: 10px;
}

.icon-button svg {
  display: block;
}

.icon-button-danger {
  color: #dc2626;
}

.plugin-switch {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.plugin-switch-label {
  font-size: 12px;
  color: #6b7280;
}

/* MCP 原生弹窗外壳：与大纲管理/生成大纲弹窗对齐 */
.pm-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.pm-overlay-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.4); /* bg-slate-900/40 */
  backdrop-filter: blur(8px);
}

.pm-modal-card {
  position: relative;
  z-index: 51;
  background: #ffffff;
  border-radius: 16px; /* rounded-2xl */
  box-shadow: 0 25px 50px -12px rgba(15, 23, 42, 0.35); /* shadow-2xl */
  border: 1px solid #e5e7eb; /* border-slate-200 */
  padding: 24px 24px 20px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}

.pm-modal-lg {
  width: 100%;
  max-width: 880px;
}

.pm-modal-md {
  width: 100%;
  max-width: 720px;
}

.pm-modal-sm {
  width: 100%;
  max-width: 560px;
}

.pm-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.pm-modal-title {
  font-size: 18px; /* text-xl */
  font-weight: 600;
  color: #111827;
}

.pm-modal-close {
  border: none;
  background: transparent;
  padding: 4px;
  border-radius: 9999px;
  color: #9ca3af;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
}

.pm-modal-close:hover {
  background-color: #f3f4f6;
  color: #4b5563;
}

.pm-close-icon {
  width: 20px;
  height: 20px;
}

.pm-modal-body {
  padding-top: 8px;
  padding-bottom: 8px;
  overflow-y: auto;
}

.pm-modal-footer {
  margin-top: 16px;
}

.pm-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pm-info-block {
  padding: 10px 12px;
  border-radius: 10px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 13px;
}

.pm-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pm-field-inline {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.pm-field-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.pm-field-hint {
  font-size: 12px;
  color: #9ca3af;
}

.pm-input,
.pm-select,
.pm-textarea {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #d1d5db; /* border-gray-300 */
  padding: 8px 12px;
  font-size: 14px;
  color: #111827;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.pm-input:focus,
.pm-select:focus,
.pm-textarea:focus {
  border-color: #4f46e5; /* indigo-600 */
  box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.25); /* ring-indigo-200 */
}

.pm-input-disabled {
  background-color: #f9fafb;
  color: #6b7280;
}

.pm-textarea {
  min-height: 96px;
  resize: vertical;
}

.pm-switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pm-switch-input {
  width: 36px;
  height: 20px;
}

.pm-switch-label {
  font-size: 13px;
  color: #4b5563;
}

.pm-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.pm-btn-secondary {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #4b5563;
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}

.pm-btn-secondary:hover {
  background-color: #f9fafb;
}

.pm-btn-primary {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #ffffff;
  background: linear-gradient(to right, #4f46e5, #6366f1);
  border-radius: 8px;
  border: none;
  box-shadow: 0 10px 25px rgba(79, 70, 229, 0.28);
  cursor: pointer;
  transition: background-color 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease;
}

.pm-btn-primary:hover:enabled {
  background: linear-gradient(to right, #4338ca, #4f46e5);
  box-shadow: 0 14px 30px rgba(79, 70, 229, 0.32);
}

.pm-btn-primary:disabled {
  opacity: 0.7;
  cursor: default;
  box-shadow: none;
}

.tool-card {
  border-radius: 12px; /* 内层卡片略小弧度，参考大纲展开内容 */
  background: rgba(248, 250, 252, 0.96);
  padding: 10px 12px; /* 避免文字紧贴边框 */
}

.test-section-card {
  border-radius: 12px; /* 内层卡片略小弧度 */
  background: rgba(248, 250, 252, 0.96);
  padding: 8px 10px;
  overflow: hidden;
}

.test-modal-body {
  padding-top: 8px;
}

.test-modal-loading,
.tools-modal-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 0;
  gap: 12px;
}

.test-loading-spinner {
  width: 32px;
  height: 32px;
  border-radius: 9999px;
  border: 3px solid rgba(191, 219, 254, 0.8);
  border-top-color: #4f46e5;
  animation: icon-spin 0.9s linear infinite;
}

.test-loading-text {
  font-size: 13px;
  color: #6b7280;
}

.test-modal-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.test-status-block {
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 12px; /* 内层卡片略小弧度 */
  padding: 10px 12px;
  margin-bottom: 8px;
}

.test-status-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px; /* 小圆角矩形 */
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.test-status-svg {
  width: 24px;
  height: 24px;
  stroke: currentColor;
  stroke-width: 1.7;
  fill: none;
}

.test-status-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 2px;
}

.test-status-desc {
  font-size: 13px;
  color: #6b7280;
}

.test-status-block-success {
  background: #eff6ff;
  color: #1d4ed8;
}

.test-status-block-success .test-status-icon {
  background: rgba(191, 219, 254, 0.8);
  color: #1d4ed8;
}

.test-status-block-error {
  background: #fef2f2;
  color: #b91c1c;
}

.test-status-block-error .test-status-icon {
  background: rgba(254, 202, 202, 0.9);
  color: #b91c1c;
}

.test-status-text {
  text-align: left;
}

.test-modal-empty {
  padding: 20px 0;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
}

.tools-modal-body {
  padding-top: 8px;
}

.tools-empty-state {
  padding: 20px 0;
  text-align: center;
}

.tools-empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
}

.tools-empty-desc {
  font-size: 13px;
  color: #6b7280;
}

.tools-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.tool-name {
  font-size: 14px; /* 略大一号，作为卡片标题 */
  font-weight: 600;
  color: #111827;
}

.tool-type-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 8px;
  background: #eff6ff;
  color: #2563eb;
}

.import-result-body {
  padding-top: 8px;
}

.import-result-empty {
  padding: 20px 0;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
}

.import-result-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.import-status-block {
  border-radius: 12px; /* 内层卡片略小弧度 */
  padding: 12px 14px;
  background: #eff6ff;
  color: #1d4ed8;
}

.import-status-success {
  background: #eff6ff;
  color: #1d4ed8;
}

.import-status-error {
  background: #fef2f2;
  color: #b91c1c;
}

.import-status-title {
  font-size: 15px;
  font-weight: 600;
}

.import-section-card {
  border-radius: 12px; /* 内层卡片略小弧度 */
  background: rgba(248, 250, 252, 0.96);
  padding: 10px 12px;
}

.import-section-error-card {
  background: #fef2f2;
}

.import-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 6px;
}

.import-section-list {
  font-size: 13px;
  color: #374151;
  padding-left: 18px;
}

.import-section-list li {
  list-style: disc;
  margin-bottom: 2px;
}

.tool-field {
  margin-bottom: 8px;
}

.tool-field-label {
  font-size: 12px;
  font-weight: 600;
  color: #4b5563;
  margin-bottom: 2px;
}

.tool-field-value {
  font-size: 13px;
  color: #374151;
  line-height: 1.5;
}

.tool-params-json {
  max-height: 200px;
  overflow: auto;
  font-size: 12px;
  background: #f9fafb;
  border-radius: 8px;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  color: #111827;
}

:deep(.n-data-table .n-tag) {
  border-radius: 8px;
}

@keyframes icon-spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.icon-spin {
  animation: icon-spin 0.9s linear infinite;
}

@media (max-width: 767px) {
  .card-title {
    font-size: 1.125rem;
  }
}
</style>
