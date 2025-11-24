<template>
  <n-tabs type="segment" class="admin-settings">
    <n-tab-pane name="general" tab="常规设置">
      <n-space vertical size="large">
        <n-card :bordered="false">
          <template #header>
            <div class="card-header">
              <span class="card-title">每日请求额度</span>
              <n-button quaternary size="small" @click="fetchDailyLimit" :loading="dailyLimitLoading">
                刷新
              </n-button>
            </div>
          </template>
          <n-spin :show="dailyLimitLoading">
            <n-alert v-if="dailyLimitError" type="error" closable @close="dailyLimitError = null">
              {{ dailyLimitError }}
            </n-alert>
            <n-form label-placement="top" class="limit-form">
              <n-form-item label="未配置 API Key 的用户每日可用请求次数">
                <n-input-number
                  v-model:value="dailyLimit"
                  :min="0"
                  :step="10"
                  placeholder="请输入每日请求上限"
                />
              </n-form-item>
              <n-space justify="end">
                <n-button type="primary" :loading="dailyLimitSaving" @click="saveDailyLimit">
                  保存设置
                </n-button>
              </n-space>
            </n-form>
          </n-spin>
        </n-card>

        <n-card :bordered="false">
          <template #header>
            <div class="card-header">
              <span class="card-title">一般设置</span>
            </div>
          </template>
          <n-form label-placement="top" class="limit-form">
            <n-form-item label="生成蓝图后是否自动拆分章节">
              <n-space align="center">
                <n-switch v-model:value="autoExpandEnabled" />
                <span>
                  {{
                    autoExpandEnabled
                      ? '开启后，生成蓝图会自动根据章节大纲拆分章节'
                      : '关闭后，只生成蓝图，不自动拆分章节'
                  }}
                </span>
              </n-space>
            </n-form-item>
            <n-form-item label="自动拆分每条大纲的章节数">
              <n-input-number
                v-model:value="autoExpandTarget"
                :min="1"
                :max="10"
                :step="1"
                placeholder="例如 3 表示每条大纲拆分为 3 章"
              />
            </n-form-item>
            <n-space justify="end" class="mb-4">
              <n-button type="primary" :loading="autoExpandSaving" @click="saveAutoExpandTarget">
                保存自动拆分设置
              </n-button>
            </n-space>
            <n-form-item label="每次生成章节的候选版本数量">
              <n-input-number
                v-model:value="chapterVersionCount"
                :min="1"
                :max="5"
                :step="1"
                placeholder="例如 1 表示只生成一个版本"
              />
            </n-form-item>
            <n-space justify="end">
              <n-button type="primary" :loading="chapterVersionSaving" @click="saveChapterVersionCount">
                保存设置
              </n-button>
            </n-space>
          </n-form>
        </n-card>

        <n-card :bordered="false">
          <template #header>
            <div class="card-header">
              <span class="card-title">系统配置</span>
              <n-button type="primary" size="small" @click="openCreateModal">
                新增配置
              </n-button>
            </div>
          </template>

          <n-spin :show="configLoading">
            <n-alert v-if="configError" type="error" closable @close="configError = null">
              {{ configError }}
            </n-alert>

            <n-data-table
              :columns="columns"
              :data="configs"
              :loading="configLoading"
              :bordered="false"
              :row-key="rowKey"
              class="config-table"
            />
          </n-spin>
        </n-card>
      </n-space>
    </n-tab-pane>

    <!-- MCP 插件管理标签 -->
    <n-tab-pane name="mcp" tab="MCP 插件">
      <n-card :bordered="false">
        <template #header>
          <div class="card-header">
            <span class="card-title">默认 MCP 插件管理</span>
            <n-button type="primary" size="small" @click="openCreatePluginModal">
              添加默认插件
            </n-button>
          </div>
        </template>

        <n-spin :show="mcpLoading">
          <n-alert v-if="mcpError" type="error" closable @close="mcpError = null">
            {{ mcpError }}
          </n-alert>

          <div v-if="defaultPlugins.length" class="plugin-list">
            <n-card
              v-for="plugin in defaultPlugins"
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
                      :type="plugin.enabled ? 'success' : 'default'"
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
                  </div>
                  <div class="plugin-subtitle-row">
                    {{ plugin.plugin_name }}
                  </div>
                  <div class="plugin-url-row">
                    {{ plugin.server_url }}
                  </div>
                </div>

                <div class="plugin-actions">
                  <div class="plugin-switch">
                    <span class="plugin-switch-label">
                      {{ plugin.enabled ? '全局状态：启用' : '全局状态：已停用' }}
                    </span>
                    <n-switch
                      :value="plugin.enabled"
                      size="small"
                      @update:value="() => toggleDefaultPlugin(plugin)"
                    />
                  </div>

                  <n-space size="small">
                    <n-button
                      size="small"
                      tertiary
                      @click="() => viewTools(plugin)"
                    >
                      查看工具
                    </n-button>
                    <n-button
                      size="small"
                      tertiary
                      type="info"
                      @click="() => testPlugin(plugin.id)"
                    >
                      测试连接
                    </n-button>
                    <n-button
                      size="small"
                      tertiary
                      type="primary"
                      @click="() => openEditPluginModal(plugin)"
                    >
                      编辑
                    </n-button>
                    <n-popconfirm
                      :positive-text="'删除'"
                      :negative-text="'取消'"
                      type="error"
                      placement="left"
                      @positive-click="() => deletePlugin(plugin.id)"
                    >
                      <template #trigger>
                        <n-button size="small" quaternary type="error">
                          删除
                        </n-button>
                      </template>
                      确认删除该默认插件？
                    </n-popconfirm>
                  </n-space>
                </div>
              </div>
            </n-card>
          </div>

          <n-result
            v-else
            status="info"
            title="暂无默认插件"
            description="点击右上角“添加默认插件”导入 MCP 插件"
          />
        </n-spin>
      </n-card>
    </n-tab-pane>
  </n-tabs>

  <n-modal
    v-model:show="configModalVisible"
    preset="card"
    :title="modalTitle"
    class="config-modal"
    :style="{ width: '520px', maxWidth: '92vw' }"
  >
    <n-form label-placement="top" :model="configForm">
      <n-form-item label="Key">
        <n-input
          v-model:value="configForm.key"
          :disabled="!isCreateMode"
          placeholder="请输入唯一 Key"
        />
      </n-form-item>
      <n-form-item label="值">
        <n-input v-model:value="configForm.value" placeholder="配置的具体值" />
      </n-form-item>
      <n-form-item label="描述">
        <n-input v-model:value="configForm.description" placeholder="配置项的用途说明，可选" />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closeConfigModal">取消</n-button>
        <n-button type="primary" :loading="configSaving" @click="submitConfig">
          保存
        </n-button>
      </n-space>
    </template>
  </n-modal>

  <!-- 插件创建模态框 -->
  <n-modal
    v-model:show="pluginModalVisible"
    preset="card"
    title="添加默认插件"
    class="plugin-modal"
    :style="{ width: '720px', maxWidth: '92vw' }"
  >
    <n-space vertical size="large">
      <n-alert type="info">
        粘贴标准 MCP 配置 JSON，系统自动提取插件名称。支持 HTTP 和 Stdio 类型
      </n-alert>
      
      <n-form-item label="* MCP配置JSON">
        <n-input
          v-model:value="pluginImportJson"
          type="textarea"
          :rows="16"
          placeholder='{
  "mcpServers": {
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?exaApiKey=YOUR_API_KEY",
      "headers": {}
    }
  }
}'
        />
      </n-form-item>

      <n-form-item label="插件分类">
        <n-select
          v-model:value="pluginImportCategory"
          :options="categoryOptions"
          placeholder="选择插件的功能类别，用于AI智能匹配使用场景"
        />
      </n-form-item>
    </n-space>
    
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closePluginModal">取消</n-button>
        <n-button type="primary" :loading="pluginSaving" @click="submitPlugin">
          保存
        </n-button>
      </n-space>
    </template>
  </n-modal>

  <!-- 导入结果模态框 -->
  <n-modal
    v-model:show="pluginResultModalVisible"
    preset="card"
    title="导入结果"
    class="import-result-modal"
    :style="{ width: '560px', maxWidth: '92vw' }"
  >
    <n-result
      v-if="pluginImportResult"
      :status="pluginImportResult.errors.length === 0 ? 'success' : 'warning'"
      :title="pluginImportResult.summary"
    >
      <template #footer>
        <n-space vertical>
          <n-card v-if="pluginImportResult.created.length > 0" title="成功导入" size="small" type="success">
            <n-ul>
              <n-li v-for="name in pluginImportResult.created" :key="name">{{ name }}</n-li>
            </n-ul>
          </n-card>
          <n-card v-if="pluginImportResult.skipped.length > 0" title="已跳过（已存在）" size="small" type="warning">
            <n-ul>
              <n-li v-for="name in pluginImportResult.skipped" :key="name">{{ name }}</n-li>
            </n-ul>
          </n-card>
          <n-card v-if="pluginImportResult.errors.length > 0" title="导入失败" size="small" type="error">
            <n-ul>
              <n-li v-for="error in pluginImportResult.errors" :key="error">{{ error }}</n-li>
            </n-ul>
          </n-card>
        </n-space>
      </template>
    </n-result>
  </n-modal>

  <n-modal
    v-model:show="testModalVisible"
    preset="card"
    title="默认插件测试结果"
    class="test-modal"
    :style="{ width: '560px', maxWidth: '92vw' }"
  >
    <n-spin :show="testing">
      <n-result
        v-if="testReport"
        :status="testReport.success ? 'success' : 'error'"
        :title="testReport.success ? '测试成功' : '测试失败'"
        :description="testReport.message"
      >
        <template #footer>
          <n-space vertical>
            <n-descriptions :column="1" bordered size="small">
              <n-descriptions-item label="工具数量">
                {{ testReport.tools_count }}
              </n-descriptions-item>
              <n-descriptions-item v-if="testReport.error" label="错误信息">
                {{ testReport.error }}
              </n-descriptions-item>
            </n-descriptions>
            <n-card v-if="testReport.suggestions.length > 0" title="建议" size="small">
              <n-ul>
                <n-li v-for="(suggestion, index) in testReport.suggestions" :key="index">
                  {{ suggestion }}
                </n-li>
              </n-ul>
            </n-card>
          </n-space>
        </template>
      </n-result>
    </n-spin>
  </n-modal>

  <n-modal
    v-model:show="toolsModalVisible"
    preset="card"
    :title="currentToolsPlugin ? `工具列表 - ${currentToolsPlugin.display_name}` : '工具列表'"
    class="tools-modal"
    :style="{ width: '720px', maxWidth: '92vw' }"
  >
    <n-spin :show="toolsLoading">
      <n-result
        v-if="!toolsLoading && tools.length === 0"
        status="info"
        title="暂无工具"
        description="该插件未提供任何工具定义"
      />
      <n-space v-else vertical size="small">
        <n-card
          v-for="tool in tools"
          :key="tool.function.name"
          size="small"
        >
          <template #header>
            <n-space justify="space-between">
              <span>{{ tool.function.name }}</span>
              <n-tag size="small" type="info">
                {{ tool.type }}
              </n-tag>
            </n-space>
          </template>
          <div v-if="tool.function.description" style="margin-bottom: 8px">
            {{ tool.function.description }}
          </div>
          <pre
            v-if="tool.function.parameters"
            style="max-height: 200px; overflow: auto; font-size: 12px"
          >{{ formatParameters(tool.function.parameters) }}</pre>
        </n-card>
      </n-space>
    </n-spin>
  </n-modal>

  <n-modal
    v-model:show="pluginEditModalVisible"
    preset="card"
    title="编辑默认插件"
    class="plugin-modal"
    :style="{ width: '720px', maxWidth: '92vw' }"
  >
    <n-form label-placement="top">
      <n-form-item label="插件标识符 (plugin_name)">
        <n-input v-model:value="pluginForm.plugin_name" disabled />
      </n-form-item>
      <n-form-item label="显示名称">
        <n-input v-model:value="pluginForm.display_name" />
      </n-form-item>
      <n-form-item label="服务器地址">
        <n-input v-model:value="pluginForm.server_url" />
      </n-form-item>
      <n-form-item label="分类">
        <n-select
          v-model:value="pluginForm.category"
          :options="categoryOptions"
          placeholder="选择插件分类"
        />
      </n-form-item>
      <n-form-item label="启用状态">
        <n-switch v-model:value="pluginForm.enabled" />
      </n-form-item>
      <n-form-item label="Headers JSON">
        <n-input
          v-model:value="headersJson"
          type="textarea"
          :rows="4"
          placeholder="可选，JSON 对象，例如 { &quot;Authorization&quot;: &quot;Bearer ...&quot; }"
        />
      </n-form-item>
      <n-form-item label="Config JSON">
        <n-input
          v-model:value="configJson"
          type="textarea"
          :rows="6"
          placeholder="可选，插件自定义配置 JSON"
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closeEditPluginModal">取消</n-button>
        <n-button type="primary" :loading="editSaving" @click="submitEditPlugin">
          保存
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NLi,
  NModal,
  NPopconfirm,
  NResult,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  NUl,
  type DataTableColumns
} from 'naive-ui'

import {
  AdminAPI,
  type DailyRequestLimit,
  type AutoExpandConfig,
  type SystemConfig,
  type SystemConfigUpdatePayload,
  type SystemConfigUpsertPayload,
  type MCPPlugin,
  type MCPPluginCreate
} from '@/api/admin'
import { useAlert } from '@/composables/useAlert'
import { MCPAPI, type PluginTestReport, type ToolDefinition } from '@/api/mcp'

const { showAlert } = useAlert()

// Daily limit state
const dailyLimit = ref<number | null>(null)
const dailyLimitLoading = ref(false)
const dailyLimitSaving = ref(false)
const dailyLimitError = ref<string | null>(null)

// Chapter version settings
const chapterVersionCount = ref<number | null>(null)
const chapterVersionSaving = ref(false)

// Auto expand settings
const autoExpandEnabled = ref<boolean>(false)
const autoExpandTarget = ref<number | null>(null)
const autoExpandSaving = ref(false)

// System config state
const configs = ref<SystemConfig[]>([])
const configLoading = ref(false)
const configSaving = ref(false)
const configError = ref<string | null>(null)

const configModalVisible = ref(false)
const isCreateMode = ref(true)
const configForm = reactive<SystemConfig>({
  key: '',
  value: '',
  description: ''
})

// MCP plugin state
const defaultPlugins = ref<MCPPlugin[]>([])
const mcpLoading = ref(false)
const pluginSaving = ref(false)
const mcpError = ref<string | null>(null)

const pluginModalVisible = ref(false)
const isPluginCreateMode = ref(true)
const pluginForm = reactive<MCPPluginCreate & { id?: number }>({
  plugin_name: '',
  display_name: '',
  plugin_type: 'http',
  server_url: '',
  headers: null,
  enabled: true,
  category: null,
  config: null
})

const pluginImportJson = ref('')
const pluginImportCategory = ref<string | null>(null)
const pluginResultModalVisible = ref(false)
const pluginImportResult = ref<any>(null)

const testModalVisible = ref(false)
const testing = ref(false)
const testReport = ref<PluginTestReport | null>(null)

const toolsModalVisible = ref(false)
const toolsLoading = ref(false)
const tools = ref<ToolDefinition[]>([])
const currentToolsPlugin = ref<MCPPlugin | null>(null)

const pluginEditModalVisible = ref(false)
const editSaving = ref(false)

const headersJson = ref('')
const configJson = ref('')

const formatParameters = (params: Record<string, any>) => JSON.stringify(params, null, 2)

const categoryOptions = [
  { label: '搜索类 (Search) - 网络搜索、信息查询', value: 'search' },
  { label: '文件系统 (Filesystem) - 文件读写、目录操作', value: 'filesystem' },
  { label: '数据库 (Database) - 数据查询、数据管理', value: 'database' },
  { label: '分析类 (Analysis) - 数据分析 / 文本处理', value: 'analysis' },
  { label: 'API集成 (API) - 第三方服务调用', value: 'api' },
  { label: '工具类 (Tools) - 实用工具、辅助功能', value: 'tools' },
  { label: '其他 (Other)', value: 'other' }
]

const rowKey = (row: SystemConfig) => row.key
const pluginRowKey = (row: MCPPlugin) => row.id

const modalTitle = computed(() => (isCreateMode.value ? '新增配置项' : '编辑配置项'))


const fetchDailyLimit = async () => {
  dailyLimitLoading.value = true
  dailyLimitError.value = null
  try {
    const result = await AdminAPI.getDailyRequestLimit()
    dailyLimit.value = result.limit
  } catch (err) {
    dailyLimitError.value = err instanceof Error ? err.message : '加载每日限制失败'
  } finally {
    dailyLimitLoading.value = false
  }
}

const fetchAutoExpandConfig = async () => {
  try {
    const result = await AdminAPI.getAutoExpandConfig()
    autoExpandEnabled.value = result.enabled
    autoExpandTarget.value = result.target_chapter_count
  } catch (err) {
    console.error('加载自动拆分配置失败', err)
  }
}

const saveAutoExpandTarget = async () => {
  if (autoExpandTarget.value === null || autoExpandTarget.value <= 0) {
    showAlert('请设置有效的自动拆分章节数', 'error')
    return
  }
  autoExpandSaving.value = true
  try {
    await AdminAPI.setAutoExpandConfig({
      enabled: autoExpandEnabled.value,
      target_chapter_count: autoExpandTarget.value as number
    })
    showAlert('自动拆分设置已更新', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    autoExpandSaving.value = false
  }
}

const saveDailyLimit = async () => {
  if (dailyLimit.value === null || dailyLimit.value < 0) {
    showAlert('请设置有效的每日额度', 'error')
    return
  }
  dailyLimitSaving.value = true
  try {
    await AdminAPI.setDailyRequestLimit(dailyLimit.value)
    showAlert('每日额度已更新', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    dailyLimitSaving.value = false
  }
}

const initChapterVersionFromConfigs = () => {
  const target = configs.value.find((item) => item.key === 'writer.chapter_versions')
  if (target) {
    const parsed = parseInt(target.value, 10)
    if (!isNaN(parsed) && parsed > 0) {
      chapterVersionCount.value = parsed
      return
    }
  }
  if (chapterVersionCount.value === null) {
    chapterVersionCount.value = 2
  }
}

const fetchConfigs = async () => {
  configLoading.value = true
  configError.value = null
  try {
    configs.value = await AdminAPI.listSystemConfigs()
    initChapterVersionFromConfigs()
  } catch (err) {
    configError.value = err instanceof Error ? err.message : '加载配置失败'
  } finally {
    configLoading.value = false
  }
}

const saveChapterVersionCount = async () => {
  if (chapterVersionCount.value === null || chapterVersionCount.value <= 0) {
    showAlert('请设置有效的章节版本数量', 'error')
    return
  }
  chapterVersionSaving.value = true
  try {
    const value = String(chapterVersionCount.value)
    const existing = configs.value.find((item) => item.key === 'writer.chapter_versions')
    let updated: SystemConfig
    if (existing) {
      updated = await AdminAPI.patchSystemConfig('writer.chapter_versions', {
        value,
        description: existing.description || undefined
      } as SystemConfigUpdatePayload)
      const index = configs.value.findIndex((item) => item.key === updated.key)
      if (index !== -1) {
        configs.value.splice(index, 1, updated)
      }
    } else {
      updated = await AdminAPI.upsertSystemConfig('writer.chapter_versions', {
        value,
        description: '每次生成章节的候选版本数量。'
      })
      configs.value.unshift(updated)
    }
    showAlert('章节生成版本数量已更新', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    chapterVersionSaving.value = false
  }
}

const openCreateModal = () => {
  isCreateMode.value = true
  configForm.key = ''
  configForm.value = ''
  configForm.description = ''
  configModalVisible.value = true
}

const openEditModal = (config: SystemConfig) => {
  isCreateMode.value = false
  configForm.key = config.key
  configForm.value = config.value
  configForm.description = config.description || ''
  configModalVisible.value = true
}

const closeConfigModal = () => {
  configModalVisible.value = false
  configSaving.value = false
}

const submitConfig = async () => {
  if (!configForm.key.trim() || !configForm.value.trim()) {
    showAlert('Key 与 Value 均为必填项', 'error')
    return
  }
  configSaving.value = true
  try {
    let updated: SystemConfig
    if (isCreateMode.value) {
      updated = await AdminAPI.upsertSystemConfig(configForm.key.trim(), {
        value: configForm.value,
        description: configForm.description || undefined
      })
      configs.value.unshift(updated)
    } else {
      updated = await AdminAPI.patchSystemConfig(configForm.key, {
        value: configForm.value,
        description: configForm.description || undefined
      } as SystemConfigUpdatePayload)
      const index = configs.value.findIndex((item) => item.key === updated.key)
      if (index !== -1) {
        configs.value.splice(index, 1, updated)
      }
    }
    showAlert('配置已保存', 'success')
    closeConfigModal()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    configSaving.value = false
  }
}

const deleteConfig = async (key: string) => {
  try {
    await AdminAPI.deleteSystemConfig(key)
    configs.value = configs.value.filter((item) => item.key !== key)
    showAlert('配置已删除', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '删除失败', 'error')
  }
}

// MCP Plugin Management Functions
const fetchDefaultPlugins = async () => {
  mcpLoading.value = true
  mcpError.value = null
  try {
    defaultPlugins.value = await AdminAPI.listDefaultMCPPlugins()
  } catch (err) {
    mcpError.value = err instanceof Error ? err.message : '加载默认插件失败'
  } finally {
    mcpLoading.value = false
  }
}

const openCreatePluginModal = () => {
  pluginImportJson.value = ''
  pluginImportCategory.value = null
  pluginModalVisible.value = true
}

const closePluginModal = () => {
  pluginModalVisible.value = false
  pluginSaving.value = false
}

const submitPlugin = async () => {
  if (!pluginImportJson.value.trim()) {
    showAlert('请输入 MCP 配置 JSON', 'error')
    return
  }

  let mcpConfig: any
  try {
    mcpConfig = JSON.parse(pluginImportJson.value)
  } catch (err) {
    showAlert('JSON 格式错误', 'error')
    return
  }

  // 如果用户选择了分类，为所有插件添加分类
  if (pluginImportCategory.value && mcpConfig.mcpServers) {
    for (const pluginName in mcpConfig.mcpServers) {
      if (!mcpConfig.mcpServers[pluginName].category) {
        mcpConfig.mcpServers[pluginName].category = pluginImportCategory.value
      }
    }
  }

  pluginSaving.value = true
  try {
    pluginImportResult.value = await AdminAPI.importMCPPluginsFromJson(mcpConfig)
    closePluginModal()
    pluginResultModalVisible.value = true
    
    // 刷新插件列表
    if (pluginImportResult.value.created.length > 0) {
      await fetchDefaultPlugins()
    }
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '导入失败', 'error')
  } finally {
    pluginSaving.value = false
  }
}

const deletePlugin = async (id: number) => {
  try {
    await AdminAPI.deleteDefaultMCPPlugin(id)
    defaultPlugins.value = defaultPlugins.value.filter((p) => p.id !== id)
    showAlert('默认插件已删除', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '删除失败', 'error')
  }
}

const toggleDefaultPlugin = async (plugin: MCPPlugin) => {
  try {
    const newEnabled = !plugin.enabled
    const updated = await AdminAPI.updateDefaultMCPPlugin(plugin.id, { enabled: newEnabled })
    const index = defaultPlugins.value.findIndex((p) => p.id === plugin.id)
    if (index !== -1) {
      defaultPlugins.value[index].enabled = updated.enabled
    }
    showAlert(newEnabled ? '默认插件已启用' : '默认插件已禁用', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '切换失败', 'error')
  }
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
    const updated = await AdminAPI.updateDefaultMCPPlugin(pluginForm.id, {
      display_name: pluginForm.display_name,
      server_url: pluginForm.server_url,
      headers: pluginForm.headers || null,
      enabled: pluginForm.enabled,
      category: pluginForm.category || null,
      config: pluginForm.config || null
    })
    const index = defaultPlugins.value.findIndex((p) => p.id === updated.id)
    if (index !== -1) {
      defaultPlugins.value.splice(index, 1, updated)
    }
    showAlert('默认插件已更新', 'success')
    closeEditPluginModal()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '更新失败', 'error')
  } finally {
    editSaving.value = false
  }
}

const viewTools = async (plugin: MCPPlugin) => {
  toolsModalVisible.value = true
  toolsLoading.value = true
  currentToolsPlugin.value = plugin
  tools.value = []
  try {
    tools.value = await MCPAPI.getPluginTools(plugin.id)
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '获取工具列表失败', 'error')
    toolsModalVisible.value = false
  } finally {
    toolsLoading.value = false
  }
}

const testPlugin = async (id: number) => {
  testing.value = true
  testReport.value = null
  testModalVisible.value = true
  try {
    testReport.value = await MCPAPI.testPlugin(id)
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '测试失败', 'error')
    testModalVisible.value = false
  } finally {
    testing.value = false
  }
}

const columns: DataTableColumns<SystemConfig> = [
  {
    title: 'Key',
    key: 'key',
    width: 220,
    ellipsis: { tooltip: true }
  },
  {
    title: '值',
    key: 'value',
    ellipsis: { tooltip: true }
  },
  {
    title: '描述',
    key: 'description',
    ellipsis: { tooltip: true },
    render(row) {
      return row.description || '—'
    }
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 160,
    render(row) {
      return h(
        NSpace,
        { justify: 'center', size: 'small' },
        {
          default: () => [
            h(
              NButton,
              {
                size: 'small',
                type: 'primary',
                tertiary: true,
                onClick: () => openEditModal(row)
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
                onPositiveClick: () => deleteConfig(row.key)
              },
              {
                default: () => '确认删除该配置项？',
                trigger: () =>
                  h(
                    NButton,
                    { size: 'small', type: 'error', quaternary: true },
                    { default: () => '删除' }
                  )
              }
            )
          ]
        }
      )
    }
  }
]

onMounted(() => {
  fetchDailyLimit()
  fetchAutoExpandConfig()
  fetchConfigs()
  fetchDefaultPlugins()
})

</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
}

.limit-form {
  max-width: 360px;
}

.config-modal {
  max-width: min(640px, 92vw);
}

.plugin-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plugin-card {
  border-radius: 10px;
}

.plugin-card-body {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 16px;
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

.plugin-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 8px;
  min-width: 180px;
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

@media (max-width: 767px) {
  .card-title {
    font-size: 1.125rem;
  }
}
</style>
