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

          <n-data-table
            :columns="pluginColumns"
            :data="defaultPlugins"
            :loading="mcpLoading"
            :bordered="false"
            :row-key="pluginRowKey"
            class="plugin-table"
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

  <!-- 插件创建/编辑模态框 -->
  <n-modal
    v-model:show="pluginModalVisible"
    preset="card"
    :title="pluginModalTitle"
    class="plugin-modal"
    :style="{ width: '640px', maxWidth: '92vw' }"
  >
    <n-form label-placement="top" :model="pluginForm">
      <n-form-item label="插件名称" required>
        <n-input
          v-model:value="pluginForm.plugin_name"
          :disabled="!isPluginCreateMode"
          placeholder="唯一标识符，如 exa-search"
        />
      </n-form-item>
      <n-form-item label="显示名称" required>
        <n-input
          v-model:value="pluginForm.display_name"
          placeholder="用户可见的名称，如 Exa 搜索"
        />
      </n-form-item>
      <n-form-item label="服务器地址" required>
        <n-input
          v-model:value="pluginForm.server_url"
          placeholder="MCP 服务器 URL，如 http://localhost:3000"
        />
      </n-form-item>
      <n-form-item label="分类">
        <n-select
          v-model:value="pluginForm.category"
          :options="categoryOptions"
          placeholder="选择插件分类"
        />
      </n-form-item>
      <n-form-item label="认证请求头 (JSON)">
        <n-input
          v-model:value="pluginHeadersJson"
          type="textarea"
          :rows="3"
          placeholder='{"Authorization": "Bearer YOUR_TOKEN"}'
        />
      </n-form-item>
      <n-form-item label="额外配置 (JSON)">
        <n-input
          v-model:value="pluginConfigJson"
          type="textarea"
          :rows="3"
          placeholder='{"timeout": 30, "max_retries": 3}'
        />
      </n-form-item>
      <n-form-item label="全局启用">
        <n-switch v-model:value="pluginForm.enabled" />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closePluginModal">取消</n-button>
        <n-button type="primary" :loading="pluginSaving" @click="submitPlugin">
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
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  type DataTableColumns
} from 'naive-ui'

import {
  AdminAPI,
  type DailyRequestLimit,
  type SystemConfig,
  type SystemConfigUpdatePayload,
  type SystemConfigUpsertPayload,
  type MCPPlugin,
  type MCPPluginCreate
} from '@/api/admin'
import { useAlert } from '@/composables/useAlert'

const { showAlert } = useAlert()

// Daily limit state
const dailyLimit = ref<number | null>(null)
const dailyLimitLoading = ref(false)
const dailyLimitSaving = ref(false)
const dailyLimitError = ref<string | null>(null)

// Chapter version settings
const chapterVersionCount = ref<number | null>(null)
const chapterVersionSaving = ref(false)

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

const pluginHeadersJson = ref('')
const pluginConfigJson = ref('')

const categoryOptions = [
  { label: '通用', value: 'general' },
  { label: '搜索', value: 'search' },
  { label: '文件系统', value: 'filesystem' },
  { label: '数据库', value: 'database' },
  { label: '分析', value: 'analysis' }
]

const rowKey = (row: SystemConfig) => row.key
const pluginRowKey = (row: MCPPlugin) => row.id

const modalTitle = computed(() => (isCreateMode.value ? '新增配置项' : '编辑配置项'))
const pluginModalTitle = computed(() => (isPluginCreateMode.value ? '添加默认插件' : '编辑默认插件'))

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
  isPluginCreateMode.value = true
  pluginForm.plugin_name = ''
  pluginForm.display_name = ''
  pluginForm.plugin_type = 'http'
  pluginForm.server_url = ''
  pluginForm.enabled = true
  pluginForm.category = null
  pluginHeadersJson.value = ''
  pluginConfigJson.value = ''
  pluginModalVisible.value = true
}

const openEditPluginModal = (plugin: MCPPlugin) => {
  isPluginCreateMode.value = false
  pluginForm.id = plugin.id
  pluginForm.plugin_name = plugin.plugin_name
  pluginForm.display_name = plugin.display_name
  pluginForm.plugin_type = plugin.plugin_type
  pluginForm.server_url = plugin.server_url
  pluginForm.enabled = plugin.enabled
  pluginForm.category = plugin.category || null
  pluginHeadersJson.value = plugin.headers ? JSON.stringify(plugin.headers, null, 2) : ''
  pluginConfigJson.value = plugin.config ? JSON.stringify(plugin.config, null, 2) : ''
  pluginModalVisible.value = true
}

const closePluginModal = () => {
  pluginModalVisible.value = false
  pluginSaving.value = false
}

const submitPlugin = async () => {
  if (!pluginForm.plugin_name.trim() || !pluginForm.display_name.trim() || !pluginForm.server_url.trim()) {
    showAlert('插件名称、显示名称和服务器地址为必填项', 'error')
    return
  }

  // Parse JSON fields
  let headers = null
  let config = null
  
  if (pluginHeadersJson.value.trim()) {
    try {
      headers = JSON.parse(pluginHeadersJson.value)
    } catch (err) {
      showAlert('认证请求头 JSON 格式错误', 'error')
      return
    }
  }
  
  if (pluginConfigJson.value.trim()) {
    try {
      config = JSON.parse(pluginConfigJson.value)
    } catch (err) {
      showAlert('额外配置 JSON 格式错误', 'error')
      return
    }
  }

  pluginSaving.value = true
  try {
    const payload: MCPPluginCreate = {
      plugin_name: pluginForm.plugin_name.trim(),
      display_name: pluginForm.display_name.trim(),
      plugin_type: pluginForm.plugin_type || 'http',
      server_url: pluginForm.server_url.trim(),
      headers,
      enabled: pluginForm.enabled,
      category: pluginForm.category?.trim() || null,
      config
    }

    if (isPluginCreateMode.value) {
      const created = await AdminAPI.createDefaultMCPPlugin(payload)
      defaultPlugins.value.unshift(created)
      showAlert('默认插件已创建', 'success')
    } else {
      const updated = await AdminAPI.updateDefaultMCPPlugin(pluginForm.id!, {
        display_name: payload.display_name,
        server_url: payload.server_url,
        headers: payload.headers,
        enabled: payload.enabled,
        category: payload.category,
        config: payload.config
      })
      const index = defaultPlugins.value.findIndex((p) => p.id === updated.id)
      if (index !== -1) {
        defaultPlugins.value.splice(index, 1, updated)
      }
      showAlert('默认插件已更新', 'success')
    }
    closePluginModal()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
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

const pluginColumns: DataTableColumns<MCPPlugin> = [
  {
    title: '插件名称',
    key: 'display_name',
    width: 180,
    ellipsis: { tooltip: true }
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
      return row.category ? h(NTag, { size: 'small', type: 'info' }, { default: () => row.category }) : '—'
    }
  },
  {
    title: '状态',
    key: 'enabled',
    width: 100,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { size: 'small', type: row.enabled ? 'success' : 'default' },
        { default: () => (row.enabled ? '启用' : '禁用') }
      )
    }
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 180,
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
                default: () => '确认删除该默认插件？',
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
  fetchConfigs()
  fetchDefaultPlugins()
})
</script>

<style scoped>
.admin-settings {
  width: 100%;
}

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

@media (max-width: 767px) {
  .card-title {
    font-size: 1.125rem;
  }
}
</style>
