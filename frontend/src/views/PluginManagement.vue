<template>
  <n-space vertical size="large" class="plugin-management">
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">MCP 插件管理</span>
          <n-space>
            <n-button quaternary size="small" @click="fetchPlugins" :loading="loading">
              刷新
            </n-button>
            <n-button
              v-if="isAdmin"
              type="primary"
              size="small"
              @click="openCreateModal"
            >
              添加插件
            </n-button>
          </n-space>
        </div>
      </template>

      <n-spin :show="loading">
        <n-alert type="info" style="margin-bottom: 16px">
          默认插件由管理员配置，你可以启用/禁用它们，或添加自己的插件
        </n-alert>

        <n-alert v-if="error" type="error" closable @close="error = null">
          {{ error }}
        </n-alert>

        <n-data-table
          :columns="columns"
          :data="plugins"
          :loading="loading"
          :bordered="false"
          :row-key="rowKey"
          class="plugin-table"
        />
      </n-spin>
    </n-card>
  </n-space>

  <!-- 创建/编辑插件模态框 -->
  <n-modal
    v-model:show="pluginModalVisible"
    preset="card"
    :title="modalTitle"
    class="plugin-modal"
    :style="{ width: '720px', maxWidth: '92vw' }"
  >
    <n-space vertical size="large">
      <n-alert type="info">
        粘贴标准 MCP 配置 JSON，系统自动提取插件名称。支持 HTTP 和 Stdio 类型
      </n-alert>
      
      <n-form-item label="* MCP配置JSON">
        <n-input
          v-model:value="importJson"
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
          v-model:value="importCategory"
          :options="categoryOptions"
          placeholder="选择插件的功能类别，用于AI智能匹配使用场景"
        />
      </n-form-item>
    </n-space>
    
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closePluginModal">取消</n-button>
        <n-button type="primary" :loading="saving" @click="submitPlugin">
          保存
        </n-button>
      </n-space>
    </template>
  </n-modal>

  <!-- 导入结果模态框 -->
  <n-modal
    v-model:show="importResultModalVisible"
    preset="card"
    title="导入结果"
    class="import-result-modal"
    :style="{ width: '560px', maxWidth: '92vw' }"
  >
    <n-result
      v-if="importResult"
      :status="importResult.errors.length === 0 ? 'success' : 'warning'"
      :title="importResult.summary"
    >
      <template #footer>
        <n-space vertical>
          <n-card v-if="importResult.created.length > 0" title="成功导入" size="small" type="success">
            <n-ul>
              <n-li v-for="name in importResult.created" :key="name">{{ name }}</n-li>
            </n-ul>
          </n-card>
          <n-card v-if="importResult.skipped.length > 0" title="已跳过（已存在）" size="small" type="warning">
            <n-ul>
              <n-li v-for="name in importResult.skipped" :key="name">{{ name }}</n-li>
            </n-ul>
          </n-card>
          <n-card v-if="importResult.errors.length > 0" title="导入失败" size="small" type="error">
            <n-ul>
              <n-li v-for="error in importResult.errors" :key="error">{{ error }}</n-li>
            </n-ul>
          </n-card>
        </n-space>
      </template>
    </n-result>
  </n-modal>

  <!-- 测试结果模态框 -->
  <n-modal
    v-model:show="testModalVisible"
    preset="card"
    title="插件测试结果"
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
  NLi,
  NModal,
  NPopconfirm,
  NResult,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NUl,
  type DataTableColumns
} from 'naive-ui'

import { MCPAPI, type MCPPlugin, type MCPPluginCreate, type PluginTestReport, type ImportPluginsResponse } from '@/api/mcp'
import { useAlert } from '@/composables/useAlert'
import { useAuthStore } from '@/stores/auth'

const { showAlert } = useAlert()
const authStore = useAuthStore()

const isAdmin = computed(() => authStore.user?.is_admin || false)

const plugins = ref<MCPPlugin[]>([])
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const error = ref<string | null>(null)

const pluginModalVisible = ref(false)
const testModalVisible = ref(false)
const importResultModalVisible = ref(false)
const isCreateMode = ref(true)
const testReport = ref<PluginTestReport | null>(null)
const importResult = ref<ImportPluginsResponse | null>(null)

const importJson = ref('')
const importCategory = ref<string | null>(null)

const categoryOptions = [
  { label: '搜索类 (Search) - 网络搜索、信息查询', value: 'search' },
  { label: '文件系统 (Filesystem) - 文件读写、目录操作', value: 'filesystem' },
  { label: '数据库 (Database) - 数据查询、数据管理', value: 'database' },
  { label: 'API集成 (API) - 第三方服务调用', value: 'api' },
  { label: '工具类 (Tools) - 实用工具、辅助功能', value: 'tools' },
  { label: '其他 (Other)', value: 'other' }
]

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

const headersJson = ref('')
const configJson = ref('')

const rowKey = (row: MCPPlugin) => row.id

const modalTitle = computed(() => '添加插件')

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

const openCreateModal = () => {
  isCreateMode.value = true
  importJson.value = ''
  importCategory.value = null
  pluginModalVisible.value = true
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
    showAlert(result.enabled ? '插件已启用' : '插件已禁用', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '切换失败', 'error')
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



const columns: DataTableColumns<MCPPlugin> = [
  {
    title: '插件名称',
    key: 'display_name',
    width: 180,
    ellipsis: { tooltip: true },
    render(row) {
      return h('span', [
        row.display_name,
        row.is_default ? h(NTag, { size: 'small', type: 'info', style: { marginLeft: '8px' } }, { default: () => '默认' }) : null
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
      return row.category ? h(NTag, { size: 'small', type: 'info' }, { default: () => row.category }) : '—'
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
        { size: 'small', type: row.enabled ? 'success' : 'default' },
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
        return h(NTag, { size: 'small', type: 'default' }, { default: () => '未设置' })
      }
      return h(
        NTag,
        { size: 'small', type: row.user_enabled ? 'success' : 'warning' },
        { default: () => (row.user_enabled ? '已启用' : '已禁用') }
      )
    }
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 280,
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
            { default: () => '测试' }
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

      return h(NSpace, { justify: 'center', size: 'small' }, { default: () => actions })
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

.plugin-modal,
.test-modal {
  max-width: min(640px, 92vw);
}

@media (max-width: 767px) {
  .card-title {
    font-size: 1.125rem;
  }
}
</style>
