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
    :style="{ width: '640px', maxWidth: '92vw' }"
  >
    <n-form label-placement="top" :model="pluginForm" ref="formRef">
      <n-form-item label="插件名称" required>
        <n-input
          v-model:value="pluginForm.plugin_name"
          :disabled="!isCreateMode"
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
      <n-form-item label="插件类型">
        <n-input
          v-model:value="pluginForm.plugin_type"
          placeholder="默认为 http"
        />
      </n-form-item>
      <n-form-item label="分类">
        <n-input
          v-model:value="pluginForm.category"
          placeholder="如 search, filesystem, database"
        />
      </n-form-item>
      <n-form-item label="认证请求头 (JSON)">
        <n-input
          v-model:value="headersJson"
          type="textarea"
          :rows="3"
          placeholder='{"Authorization": "Bearer YOUR_TOKEN"}'
        />
      </n-form-item>
      <n-form-item label="额外配置 (JSON)">
        <n-input
          v-model:value="configJson"
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
        <n-button type="primary" :loading="saving" @click="submitPlugin">
          保存
        </n-button>
      </n-space>
    </template>
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
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NUl,
  type DataTableColumns
} from 'naive-ui'

import { MCPAPI, type MCPPlugin, type MCPPluginCreate, type PluginTestReport } from '@/api/mcp'
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
const isCreateMode = ref(true)
const testReport = ref<PluginTestReport | null>(null)

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

const modalTitle = computed(() => (isCreateMode.value ? '添加插件' : '编辑插件'))

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
  pluginForm.plugin_name = ''
  pluginForm.display_name = ''
  pluginForm.plugin_type = 'http'
  pluginForm.server_url = ''
  pluginForm.enabled = true
  pluginForm.category = null
  headersJson.value = ''
  configJson.value = ''
  pluginModalVisible.value = true
}

const openEditModal = (plugin: MCPPlugin) => {
  isCreateMode.value = false
  pluginForm.id = plugin.id
  pluginForm.plugin_name = plugin.plugin_name
  pluginForm.display_name = plugin.display_name
  pluginForm.plugin_type = plugin.plugin_type
  pluginForm.server_url = plugin.server_url
  pluginForm.enabled = plugin.enabled
  pluginForm.category = plugin.category || null
  headersJson.value = plugin.headers ? JSON.stringify(plugin.headers, null, 2) : ''
  configJson.value = plugin.config ? JSON.stringify(plugin.config, null, 2) : ''
  pluginModalVisible.value = true
}

const closePluginModal = () => {
  pluginModalVisible.value = false
  saving.value = false
}

const submitPlugin = async () => {
  if (!pluginForm.plugin_name.trim() || !pluginForm.display_name.trim() || !pluginForm.server_url.trim()) {
    showAlert('插件名称、显示名称和服务器地址为必填项', 'error')
    return
  }

  // Parse JSON fields
  let headers = null
  let config = null
  
  if (headersJson.value.trim()) {
    try {
      headers = JSON.parse(headersJson.value)
    } catch (err) {
      showAlert('认证请求头 JSON 格式错误', 'error')
      return
    }
  }
  
  if (configJson.value.trim()) {
    try {
      config = JSON.parse(configJson.value)
    } catch (err) {
      showAlert('额外配置 JSON 格式错误', 'error')
      return
    }
  }

  saving.value = true
  try {
    const payload = {
      plugin_name: pluginForm.plugin_name.trim(),
      display_name: pluginForm.display_name.trim(),
      plugin_type: pluginForm.plugin_type || 'http',
      server_url: pluginForm.server_url.trim(),
      headers,
      enabled: pluginForm.enabled,
      category: pluginForm.category?.trim() || null,
      config
    }

    if (isCreateMode.value) {
      const created = await MCPAPI.createPlugin(payload)
      plugins.value.unshift(created)
      showAlert('插件已创建', 'success')
    } else {
      const updated = await MCPAPI.updatePlugin(pluginForm.id!, {
        display_name: payload.display_name,
        server_url: payload.server_url,
        headers: payload.headers,
        enabled: payload.enabled,
        category: payload.category,
        config: payload.config
      })
      const index = plugins.value.findIndex((p) => p.id === updated.id)
      if (index !== -1) {
        plugins.value.splice(index, 1, updated)
      }
      showAlert('插件已更新', 'success')
    }
    closePluginModal()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
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
