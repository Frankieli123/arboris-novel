# Design Document

## Overview

本设计文档描述了 MCP 插件系统的完整实现，包括两个核心部分：

1. **MCP 调用功能**：在 LLM 服务中集成 MCP 工具，实现 AI 与外部工具的交互
2. **默认插件管理**：在管理员设置中添加默认插件配置，实现全局插件管理

设计遵循以下原则：
- 复用现有的 MCP 基础设施（MCPToolService、MCPPluginRegistry 等）
- 保持向后兼容，不破坏现有功能
- 优雅降级，MCP 失败时不影响核心功能
- 清晰的职责分离，管理功能与调用功能解耦

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend Layer                        │
├─────────────────────────────────────────────────────────────┤
│  SettingsManagement.vue  │  PluginManagement.vue  │  Novel  │
│  (Admin MCP Settings)    │  (User MCP Settings)   │  Views  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                            │
├─────────────────────────────────────────────────────────────┤
│  admin.py          │  mcp_plugins.py    │  novels.py        │
│  (Admin Settings)  │  (MCP Management)  │  (Novel Gen)      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       Service Layer                          │
├─────────────────────────────────────────────────────────────┤
│  LLMService            │  MCPPluginService  │  MCPToolService│
│  + generate_with_mcp() │  (Plugin CRUD)     │  (Tool Exec)  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Repository Layer                        │
├─────────────────────────────────────────────────────────────┤
│  MCPPluginRepository   │  UserPluginPreferenceRepository    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                            │
├─────────────────────────────────────────────────────────────┤
│  mcp_plugins (Table)   │  user_plugin_preferences (Table)   │
└─────────────────────────────────────────────────────────────┘
```



## Components and Interfaces

### 1. 数据模型层

#### 1.1 MCPPlugin 模型（已存在，需调整）

```python
class MCPPlugin(Base):
    """MCP插件配置表"""
    __tablename__ = "mcp_plugins"
    
    id = Column(Integer, primary_key=True)
    
    # 关键字段：区分默认插件和用户插件
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # user_id = NULL 表示默认插件（对所有用户生效）
    # user_id = 具体ID 表示用户自定义插件
    
    plugin_name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    plugin_type = Column(String(50), default="http")
    
    # 连接配置
    server_url = Column(String(500))
    command = Column(String(500))
    args = Column(JSON)
    env = Column(JSON)
    headers = Column(JSON)
    
    # 插件配置
    config = Column(JSON)
    
    # 状态管理
    enabled = Column(Boolean, default=True)
    status = Column(String(50), default="inactive")
    
    # 分类和排序
    category = Column(String(100), default="general")
    sort_order = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        # 默认插件：plugin_name 唯一
        # 用户插件：user_id + plugin_name 唯一
        Index('idx_user_plugin', 'user_id', 'plugin_name', unique=True),
    )
```

**关键设计决策**：
- 使用 `user_id = NULL` 标识默认插件
- 使用 `user_id = 具体ID` 标识用户插件
- 通过唯一索引确保：
  - 默认插件的 plugin_name 全局唯一
  - 用户插件的 (user_id, plugin_name) 组合唯一

#### 1.2 UserPluginPreference 模型（已存在）

```python
class UserPluginPreference(Base):
    """用户插件偏好表"""
    __tablename__ = "user_plugin_preferences"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plugin_id = Column(Integer, ForeignKey("mcp_plugins.id"), nullable=False)
    enabled = Column(Boolean, default=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_user_plugin_pref', 'user_id', 'plugin_id', unique=True),
    )
```

**用途**：
- 记录用户对默认插件的启用/禁用偏好
- 不影响默认插件本身的配置



### 2. Repository 层

#### 2.1 MCPPluginRepository（需扩展）

```python
class MCPPluginRepository:
    """MCP 插件仓库"""
    
    async def get_default_plugins(self) -> List[MCPPlugin]:
        """获取所有默认插件（user_id = NULL）"""
        query = select(MCPPlugin).where(MCPPlugin.user_id.is_(None))
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_user_plugins(self, user_id: int) -> List[MCPPlugin]:
        """获取用户自定义插件"""
        query = select(MCPPlugin).where(MCPPlugin.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_all_available_plugins(self, user_id: int) -> List[MCPPlugin]:
        """获取用户可用的所有插件（默认插件 + 用户插件）"""
        query = select(MCPPlugin).where(
            or_(
                MCPPlugin.user_id.is_(None),  # 默认插件
                MCPPlugin.user_id == user_id   # 用户插件
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def create_default_plugin(self, plugin_data: MCPPluginCreate) -> MCPPlugin:
        """创建默认插件（user_id = NULL）"""
        plugin = MCPPlugin(
            user_id=None,  # 关键：设置为 NULL
            **plugin_data.dict()
        )
        self.session.add(plugin)
        await self.session.commit()
        await self.session.refresh(plugin)
        return plugin
    
    async def create_user_plugin(
        self, user_id: int, plugin_data: MCPPluginCreate
    ) -> MCPPlugin:
        """创建用户插件"""
        plugin = MCPPlugin(
            user_id=user_id,  # 关键：设置为用户ID
            **plugin_data.dict()
        )
        self.session.add(plugin)
        await self.session.commit()
        await self.session.refresh(plugin)
        return plugin
```

#### 2.2 UserPluginPreferenceRepository（已存在，需扩展）

```python
class UserPluginPreferenceRepository:
    """用户插件偏好仓库"""
    
    async def get_enabled_plugins(self, user_id: int) -> List[MCPPlugin]:
        """获取用户启用的所有插件（考虑偏好设置）"""
        # 1. 获取所有可用插件（默认 + 用户）
        all_plugins = await self.plugin_repo.get_all_available_plugins(user_id)
        
        # 2. 获取用户偏好
        prefs_query = select(UserPluginPreference).where(
            UserPluginPreference.user_id == user_id
        )
        prefs_result = await self.session.execute(prefs_query)
        prefs = {p.plugin_id: p.enabled for p in prefs_result.scalars().all()}
        
        # 3. 过滤启用的插件
        enabled_plugins = []
        for plugin in all_plugins:
            # 如果有用户偏好，使用偏好设置
            if plugin.id in prefs:
                if prefs[plugin.id]:
                    enabled_plugins.append(plugin)
            # 否则使用插件的默认 enabled 状态
            elif plugin.enabled:
                enabled_plugins.append(plugin)
        
        return enabled_plugins
    
    async def set_user_preference(
        self, user_id: int, plugin_id: int, enabled: bool
    ) -> UserPluginPreference:
        """设置用户对插件的偏好"""
        # 查找现有偏好
        query = select(UserPluginPreference).where(
            UserPluginPreference.user_id == user_id,
            UserPluginPreference.plugin_id == plugin_id
        )
        result = await self.session.execute(query)
        pref = result.scalar_one_or_none()
        
        if pref:
            # 更新现有偏好
            pref.enabled = enabled
        else:
            # 创建新偏好
            pref = UserPluginPreference(
                user_id=user_id,
                plugin_id=plugin_id,
                enabled=enabled
            )
            self.session.add(pref)
        
        await self.session.commit()
        await self.session.refresh(pref)
        return pref
```



### 3. Service 层

#### 3.1 LLMService（需添加 MCP 集成）

```python
class LLMService:
    """LLM 服务，负责与 AI 模型交互"""
    
    def __init__(self, session, mcp_tool_service: Optional[MCPToolService] = None):
        self.session = session
        self.mcp_tool_service = mcp_tool_service
        # ... 其他初始化
    
    async def generate_with_mcp(
        self,
        prompt: str,
        user_id: int,
        *,
        enable_mcp: bool = True,
        max_tool_rounds: int = 3,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        """
        使用 MCP 工具增强的文本生成
        
        Args:
            prompt: 生成提示词
            user_id: 用户 ID
            enable_mcp: 是否启用 MCP 工具
            max_tool_rounds: 最大工具调用轮次
            tool_choice: 工具选择策略（auto/required/none）
            temperature: 温度参数
            timeout: 超时时间
            
        Returns:
            {
                "content": "生成的文本",
                "tool_calls_made": 2,
                "tools_used": ["plugin.tool1", "plugin.tool2"],
                "finish_reason": "stop",
                "mcp_enhanced": True
            }
        """
        # 初始化结果
        result = {
            "content": "",
            "tool_calls_made": 0,
            "tools_used": [],
            "finish_reason": "",
            "mcp_enhanced": False
        }
        
        # 1. 获取 MCP 工具（如果启用）
        tools = None
        if enable_mcp and self.mcp_tool_service:
            try:
                tools = await self.mcp_tool_service.get_user_enabled_tools(user_id)
                if tools:
                    logger.info(f"MCP 增强: 加载了 {len(tools)} 个工具")
                    result["mcp_enhanced"] = True
            except Exception as e:
                logger.error(f"获取 MCP 工具失败，降级为普通生成: {e}")
                tools = None
        
        # 2. 如果没有工具，直接使用普通生成
        if not tools:
            content = await self._stream_and_collect(
                [{"role": "user", "content": prompt}],
                temperature=temperature,
                user_id=user_id,
                timeout=timeout
            )
            result["content"] = content
            result["finish_reason"] = "stop"
            return result
        
        # 3. 工具调用循环
        conversation_history = [{"role": "user", "content": prompt}]
        
        for round_num in range(max_tool_rounds):
            logger.info(f"MCP 工具调用轮次: {round_num + 1}/{max_tool_rounds}")
            
            # 调用 AI（第一轮传递工具列表）
            ai_response = await self._call_llm_with_tools(
                conversation_history,
                tools=tools if round_num == 0 else None,
                tool_choice=tool_choice if round_num == 0 else None,
                temperature=temperature,
                user_id=user_id,
                timeout=timeout
            )
            
            # 检查是否有工具调用
            tool_calls = ai_response.get("tool_calls", [])
            
            if not tool_calls:
                # AI 返回最终内容
                result["content"] = ai_response.get("content", "")
                result["finish_reason"] = ai_response.get("finish_reason", "stop")
                break
            
            # 4. 执行工具调用
            logger.info(f"AI 请求调用 {len(tool_calls)} 个工具")
            
            try:
                tool_results = await self.mcp_tool_service.execute_tool_calls(
                    user_id, tool_calls
                )
                
                # 记录使用的工具
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    if tool_name not in result["tools_used"]:
                        result["tools_used"].append(tool_name)
                
                result["tool_calls_made"] += len(tool_calls)
                
                # 5. 更新对话历史
                conversation_history.append({
                    "role": "assistant",
                    "content": ai_response.get("content", ""),
                    "tool_calls": tool_calls
                })
                
                # 添加工具结果
                for tool_result in tool_results:
                    conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "name": tool_result["name"],
                        "content": tool_result["content"]
                    })
                
            except Exception as e:
                logger.error(f"工具调用失败: {e}")
                # 降级为普通生成
                content = await self._stream_and_collect(
                    [{"role": "user", "content": prompt}],
                    temperature=temperature,
                    user_id=user_id,
                    timeout=timeout
                )
                result["content"] = content
                result["finish_reason"] = "stop"
                break
        
        return result
    
    async def _call_llm_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        *,
        tool_choice: Optional[str],
        temperature: float,
        user_id: Optional[int],
        timeout: float,
    ) -> Dict[str, Any]:
        """
        调用 LLM 并提供工具列表
        
        Returns:
            {
                "content": "AI 响应内容",
                "tool_calls": [...],  # 可选
                "finish_reason": "stop"
            }
        """
        config = await self._resolve_llm_config(user_id)
        
        # 使用 OpenAI 客户端进行非流式调用
        client = AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url")
        )
        
        response = await client.chat.completions.create(
            model=config.get("model") or "gpt-3.5-turbo",
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            timeout=timeout
        )
        
        choice = response.choices[0]
        message = choice.message
        
        result = {
            "content": message.content or "",
            "finish_reason": choice.finish_reason
        }
        
        # 如果有工具调用，添加到结果中
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        
        return result
```



#### 3.2 MCPPluginService（需扩展）

```python
class MCPPluginService:
    """MCP 插件服务"""
    
    async def list_default_plugins(self) -> List[MCPPluginResponse]:
        """列出所有默认插件"""
        plugins = await self.plugin_repo.get_default_plugins()
        return [MCPPluginResponse.from_orm(p) for p in plugins]
    
    async def list_plugins_with_user_status(
        self, user_id: int
    ) -> List[MCPPluginResponse]:
        """列出所有可用插件，并标注用户状态"""
        # 获取所有可用插件
        plugins = await self.plugin_repo.get_all_available_plugins(user_id)
        
        # 获取用户偏好
        prefs = await self.user_pref_repo.get_user_preferences(user_id)
        pref_map = {p.plugin_id: p.enabled for p in prefs}
        
        # 构建响应
        responses = []
        for plugin in plugins:
            response = MCPPluginResponse.from_orm(plugin)
            
            # 标注是否为默认插件
            response.is_default = plugin.user_id is None
            
            # 标注用户状态
            if plugin.id in pref_map:
                response.user_enabled = pref_map[plugin.id]
            else:
                response.user_enabled = plugin.enabled  # 使用默认值
            
            responses.append(response)
        
        return responses
    
    async def create_default_plugin(
        self, plugin_data: MCPPluginCreate
    ) -> MCPPlugin:
        """创建默认插件（仅管理员）"""
        return await self.plugin_repo.create_default_plugin(plugin_data)
    
    async def toggle_user_plugin(
        self, user_id: int, plugin_id: int, enabled: bool
    ) -> bool:
        """切换用户的插件启用状态"""
        await self.user_pref_repo.set_user_preference(user_id, plugin_id, enabled)
        return enabled
```



### 4. API 层

#### 4.1 Admin API（需添加 MCP 管理端点）

```python
# backend/app/api/routers/admin.py

@router.get("/mcp/plugins", response_model=List[MCPPluginResponse])
async def list_default_mcp_plugins(
    current_user: UserInDB = Depends(get_current_admin),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> List[MCPPluginResponse]:
    """列出所有默认 MCP 插件（仅管理员）"""
    return await plugin_service.list_default_plugins()


@router.post("/mcp/plugins", response_model=MCPPluginResponse)
async def create_default_mcp_plugin(
    plugin_data: MCPPluginCreate,
    current_user: UserInDB = Depends(get_current_admin),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> MCPPluginResponse:
    """创建默认 MCP 插件（仅管理员）"""
    plugin = await plugin_service.create_default_plugin(plugin_data)
    return MCPPluginResponse.from_orm(plugin)


@router.put("/mcp/plugins/{plugin_id}", response_model=MCPPluginResponse)
async def update_default_mcp_plugin(
    plugin_id: int,
    plugin_data: MCPPluginUpdate,
    current_user: UserInDB = Depends(get_current_admin),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> MCPPluginResponse:
    """更新默认 MCP 插件（仅管理员）"""
    plugin = await plugin_service.update_plugin(plugin_id, plugin_data)
    return MCPPluginResponse.from_orm(plugin)


@router.delete("/mcp/plugins/{plugin_id}")
async def delete_default_mcp_plugin(
    plugin_id: int,
    current_user: UserInDB = Depends(get_current_admin),
    plugin_service: MCPPluginService = Depends(get_mcp_plugin_service),
) -> Dict[str, str]:
    """删除默认 MCP 插件（仅管理员）"""
    await plugin_service.delete_plugin(plugin_id)
    return {"status": "success", "message": "默认插件已删除"}
```

#### 4.2 Novel API（需添加 MCP 支持）

```python
# backend/app/api/routers/novels.py

class NovelGenerateRequest(BaseModel):
    """小说生成请求"""
    prompt: str
    enable_mcp: bool = True  # 新增：是否启用 MCP
    temperature: float = 0.7
    max_length: int = 2000


@router.post("/novels/generate")
async def generate_novel_content(
    request: NovelGenerateRequest,
    current_user: UserInDB = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
) -> Dict[str, Any]:
    """生成小说内容（支持 MCP 增强）"""
    
    # 使用 MCP 增强的生成
    result = await llm_service.generate_with_mcp(
        prompt=request.prompt,
        user_id=current_user.id,
        enable_mcp=request.enable_mcp,
        temperature=request.temperature,
        max_tool_rounds=3,
        tool_choice="auto"
    )
    
    return {
        "content": result["content"],
        "mcp_enhanced": result["mcp_enhanced"],
        "tools_used": result["tools_used"],
        "tool_calls_made": result["tool_calls_made"]
    }
```



### 5. Frontend 层

#### 5.1 管理员设置组件（需添加 MCP 管理）

```vue
<!-- frontend/src/components/admin/SettingsManagement.vue -->

<template>
  <n-tabs type="segment">
    <n-tab-pane name="general" tab="常规设置">
      <!-- 现有的常规设置 -->
    </n-tab-pane>
    
    <!-- 新增：MCP 插件管理标签 -->
    <n-tab-pane name="mcp" tab="MCP 插件">
      <n-card title="默认 MCP 插件管理">
        <template #header-extra>
          <n-button type="primary" @click="openCreatePluginModal">
            添加默认插件
          </n-button>
        </template>
        
        <n-data-table
          :columns="pluginColumns"
          :data="defaultPlugins"
          :loading="loading"
        />
      </n-card>
      
      <!-- 插件创建/编辑模态框 -->
      <n-modal v-model:show="pluginModalVisible" preset="card" title="配置默认插件">
        <n-form :model="pluginForm">
          <n-form-item label="插件名称" required>
            <n-input v-model:value="pluginForm.plugin_name" />
          </n-form-item>
          
          <n-form-item label="显示名称" required>
            <n-input v-model:value="pluginForm.display_name" />
          </n-form-item>
          
          <n-form-item label="服务器地址" required>
            <n-input v-model:value="pluginForm.server_url" />
          </n-form-item>
          
          <n-form-item label="分类">
            <n-select
              v-model:value="pluginForm.category"
              :options="categoryOptions"
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
              placeholder='{"timeout": 30}'
            />
          </n-form-item>
          
          <n-form-item label="全局启用">
            <n-switch v-model:value="pluginForm.enabled" />
          </n-form-item>
        </n-form>
        
        <template #footer>
          <n-space justify="end">
            <n-button @click="pluginModalVisible = false">取消</n-button>
            <n-button type="primary" @click="savePlugin">保存</n-button>
          </n-space>
        </template>
      </n-modal>
    </n-tab-pane>
  </n-tabs>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminAPI } from '@/api/admin'

const defaultPlugins = ref([])
const loading = ref(false)
const pluginModalVisible = ref(false)

const pluginForm = ref({
  plugin_name: '',
  display_name: '',
  server_url: '',
  category: 'general',
  headers: null,
  config: null,
  enabled: true
})

const categoryOptions = [
  { label: '通用', value: 'general' },
  { label: '搜索', value: 'search' },
  { label: '文件系统', value: 'filesystem' },
  { label: '数据库', value: 'database' },
  { label: '分析', value: 'analysis' }
]

const fetchDefaultPlugins = async () => {
  loading.value = true
  try {
    defaultPlugins.value = await adminAPI.listDefaultMCPPlugins()
  } finally {
    loading.value = false
  }
}

const savePlugin = async () => {
  // 解析 JSON 字段
  const headers = headersJson.value ? JSON.parse(headersJson.value) : null
  const config = configJson.value ? JSON.parse(configJson.value) : null
  
  const payload = {
    ...pluginForm.value,
    headers,
    config
  }
  
  await adminAPI.createDefaultMCPPlugin(payload)
  await fetchDefaultPlugins()
  pluginModalVisible.value = false
}

onMounted(() => {
  fetchDefaultPlugins()
})
</script>
```

#### 5.2 用户插件管理组件（已存在，需调整）

```vue
<!-- frontend/src/views/PluginManagement.vue -->

<template>
  <n-card title="MCP 插件管理">
    <n-alert type="info" style="margin-bottom: 16px">
      默认插件由管理员配置，你可以启用/禁用它们，或添加自己的插件
    </n-alert>
    
    <n-data-table
      :columns="columns"
      :data="plugins"
      :loading="loading"
    />
  </n-card>
</template>

<script setup lang="ts">
// 列定义中添加"是否默认"标识
const columns = [
  {
    title: '插件名称',
    key: 'display_name',
    render(row) {
      return h('span', [
        row.display_name,
        row.is_default ? h(NTag, { size: 'small', type: 'info' }, { default: () => '默认' }) : null
      ])
    }
  },
  // ... 其他列
]
</script>
```



## Data Models

### 数据库 Schema

#### mcp_plugins 表

```sql
CREATE TABLE mcp_plugins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NULL,  -- NULL 表示默认插件
    plugin_name VARCHAR(100) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    plugin_type VARCHAR(50) DEFAULT 'http',
    
    -- 连接配置
    server_url VARCHAR(500),
    command VARCHAR(500),
    args JSON,
    env JSON,
    headers JSON,
    
    -- 插件配置
    config JSON,
    
    -- 状态管理
    enabled BOOLEAN DEFAULT TRUE,
    status VARCHAR(50) DEFAULT 'inactive',
    
    -- 分类和排序
    category VARCHAR(100) DEFAULT 'general',
    sort_order INTEGER DEFAULT 0,
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, plugin_name)
);

CREATE INDEX idx_mcp_plugins_user ON mcp_plugins(user_id);
CREATE INDEX idx_mcp_plugins_enabled ON mcp_plugins(enabled);
CREATE INDEX idx_mcp_plugins_category ON mcp_plugins(category);
```

#### user_plugin_preferences 表

```sql
CREATE TABLE user_plugin_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plugin_id INTEGER NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (plugin_id) REFERENCES mcp_plugins(id) ON DELETE CASCADE,
    UNIQUE (user_id, plugin_id)
);

CREATE INDEX idx_user_plugin_pref_user ON user_plugin_preferences(user_id);
CREATE INDEX idx_user_plugin_pref_plugin ON user_plugin_preferences(plugin_id);
```

### Pydantic Schemas

#### MCPPluginResponse（需扩展）

```python
class MCPPluginResponse(BaseModel):
    """插件响应"""
    id: int
    plugin_name: str
    display_name: str
    description: Optional[str] = None
    plugin_type: str
    category: str
    
    # 连接配置
    server_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    
    # 配置
    config: Optional[Dict[str, Any]] = None
    
    # 状态
    enabled: bool
    status: str
    
    # 新增字段
    is_default: bool = False  # 是否为默认插件
    user_enabled: Optional[bool] = None  # 用户的启用状态
    
    created_at: datetime
    
    class Config:
        from_attributes = True
```

#### NovelGenerateRequest（需扩展）

```python
class NovelGenerateRequest(BaseModel):
    """小说生成请求"""
    prompt: str
    enable_mcp: bool = True  # 新增：是否启用 MCP
    temperature: float = 0.7
    max_length: int = 2000
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: 默认插件全局唯一性

*For any* 默认插件（user_id = NULL），plugin_name 应该在所有默认插件中唯一

**Validates: Requirements 1.3, 7.1**

### Property 2: 用户插件用户内唯一性

*For any* 用户插件（user_id != NULL），(user_id, plugin_name) 组合应该在所有用户插件中唯一

**Validates: Requirements 5.3, 7.2**

### Property 3: 用户可用插件合并正确性

*For any* 用户 ID，查询用户可用插件应该返回所有默认插件和该用户的自定义插件的合并列表，且不包含其他用户的插件

**Validates: Requirements 7.3**

### Property 4: 用户偏好不影响默认插件

*For any* 用户对默认插件的启用/禁用操作，默认插件本身的 enabled 字段应该保持不变

**Validates: Requirements 5.4, 7.4**

### Property 5: 工具调用降级一致性

*For any* MCP 工具调用失败的情况，系统应该降级为普通生成模式，且生成结果应该与不启用 MCP 时的结果一致

**Validates: Requirements 9.5**

### Property 6: 工具列表格式正确性

*For any* 用户启用的 MCP 工具列表，每个工具定义应该符合 OpenAI Function Calling 格式规范

**Validates: Requirements 9.2**

### Property 7: 多轮工具调用终止性

*For any* MCP 增强的生成请求，工具调用轮次应该不超过 max_tool_rounds 参数指定的值

**Validates: Requirements 9.3, 9.4**

### Property 8: JSON 配置验证正确性

*For any* 插件的 headers 或 config 字段，如果值不为 NULL，则应该是有效的 JSON 格式

**Validates: Requirements 3.2, 3.3, 4.2**

### Property 9: 插件分类一致性

*For any* 插件，如果未指定 category，则应该自动设置为 "general"

**Validates: Requirements 2.5**

### Property 10: 用户偏好查询正确性

*For any* 用户和插件，如果用户设置了偏好，则查询结果应该使用偏好设置；否则应该使用插件的默认 enabled 状态

**Validates: Requirements 5.4**



## Error Handling

### 1. MCP 工具调用失败

**场景**：MCP 工具调用超时或返回错误

**处理策略**：
- 记录错误日志
- 降级为普通生成模式
- 返回结果中标注 `mcp_enhanced=False`
- 不中断用户的生成流程

```python
try:
    tools = await mcp_tool_service.get_user_enabled_tools(user_id)
except Exception as e:
    logger.error(f"获取 MCP 工具失败: {e}")
    tools = None  # 降级为普通生成
```

### 2. JSON 配置格式错误

**场景**：管理员输入的 headers 或 config 不是有效的 JSON

**处理策略**：
- 前端验证 JSON 格式
- 后端再次验证
- 返回 400 错误和具体的错误信息
- 阻止保存无效配置

```python
try:
    headers = json.loads(headers_str)
except json.JSONDecodeError as e:
    raise HTTPException(
        status_code=400,
        detail=f"认证请求头 JSON 格式错误: {str(e)}"
    )
```

### 3. 默认插件名称冲突

**场景**：管理员尝试创建与现有默认插件同名的插件

**处理策略**：
- 数据库唯一约束捕获冲突
- 返回 409 Conflict 错误
- 提示管理员使用不同的插件名称

```python
try:
    plugin = await plugin_repo.create_default_plugin(plugin_data)
except IntegrityError:
    raise HTTPException(
        status_code=409,
        detail=f"默认插件 '{plugin_data.plugin_name}' 已存在"
    )
```

### 4. 用户未启用任何工具

**场景**：用户请求 MCP 增强生成，但没有启用任何工具

**处理策略**：
- 自动降级为普通生成
- 记录信息日志
- 返回结果中标注 `mcp_enhanced=False`

```python
tools = await mcp_tool_service.get_user_enabled_tools(user_id)
if not tools:
    logger.info(f"用户 {user_id} 未启用任何 MCP 工具，使用普通生成")
    return await self._stream_and_collect(...)
```

### 5. 工具调用超时

**场景**：MCP 工具调用超过配置的超时时间

**处理策略**：
- 捕获 asyncio.TimeoutError
- 记录超时日志
- 返回工具调用失败结果
- 继续执行后续逻辑（可能降级）

```python
try:
    result = await asyncio.wait_for(
        mcp_registry.call_tool(...),
        timeout=timeout
    )
except asyncio.TimeoutError:
    logger.error(f"工具调用超时: {plugin_name}.{tool_name}")
    return {
        "tool_call_id": tool_call_id,
        "role": "tool",
        "content": "工具调用超时",
        "success": False
    }
```



## Testing Strategy

### 单元测试

#### 1. Repository 层测试

**测试目标**：验证数据库操作的正确性

```python
# test_mcp_plugin_repository.py

async def test_get_default_plugins():
    """测试获取默认插件"""
    # 创建默认插件和用户插件
    default_plugin = await repo.create_default_plugin(...)
    user_plugin = await repo.create_user_plugin(user_id=1, ...)
    
    # 获取默认插件
    defaults = await repo.get_default_plugins()
    
    # 验证只返回默认插件
    assert len(defaults) == 1
    assert defaults[0].id == default_plugin.id
    assert defaults[0].user_id is None


async def test_get_all_available_plugins():
    """测试获取用户可用插件"""
    # 创建默认插件和多个用户的插件
    default_plugin = await repo.create_default_plugin(...)
    user1_plugin = await repo.create_user_plugin(user_id=1, ...)
    user2_plugin = await repo.create_user_plugin(user_id=2, ...)
    
    # 获取用户1的可用插件
    plugins = await repo.get_all_available_plugins(user_id=1)
    
    # 验证返回默认插件和用户1的插件，不包含用户2的插件
    assert len(plugins) == 2
    plugin_ids = [p.id for p in plugins]
    assert default_plugin.id in plugin_ids
    assert user1_plugin.id in plugin_ids
    assert user2_plugin.id not in plugin_ids
```

#### 2. Service 层测试

**测试目标**：验证业务逻辑的正确性

```python
# test_llm_service.py

async def test_generate_with_mcp_no_tools():
    """测试没有工具时降级为普通生成"""
    # Mock mcp_tool_service 返回空工具列表
    mcp_tool_service.get_user_enabled_tools = AsyncMock(return_value=[])
    
    result = await llm_service.generate_with_mcp(
        prompt="测试",
        user_id=1,
        enable_mcp=True
    )
    
    # 验证降级为普通生成
    assert result["mcp_enhanced"] is False
    assert result["tool_calls_made"] == 0
    assert len(result["tools_used"]) == 0


async def test_generate_with_mcp_tool_failure():
    """测试工具调用失败时降级"""
    # Mock 工具调用失败
    mcp_tool_service.execute_tool_calls = AsyncMock(
        side_effect=Exception("Tool call failed")
    )
    
    result = await llm_service.generate_with_mcp(
        prompt="测试",
        user_id=1,
        enable_mcp=True
    )
    
    # 验证降级为普通生成
    assert result["content"] != ""
    assert result["finish_reason"] == "stop"
```

#### 3. API 层测试

**测试目标**：验证 API 端点的正确性

```python
# test_admin_api.py

async def test_create_default_plugin_admin_only():
    """测试只有管理员可以创建默认插件"""
    # 非管理员用户
    response = await client.post(
        "/api/admin/mcp/plugins",
        json=plugin_data,
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    
    # 管理员用户
    response = await client.post(
        "/api/admin/mcp/plugins",
        json=plugin_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 201
    assert response.json()["plugin_name"] == plugin_data["plugin_name"]


async def test_list_default_plugins():
    """测试列出默认插件"""
    # 创建默认插件和用户插件
    await create_default_plugin(...)
    await create_user_plugin(user_id=1, ...)
    
    # 列出默认插件
    response = await client.get(
        "/api/admin/mcp/plugins",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    # 验证只返回默认插件
    plugins = response.json()
    assert len(plugins) == 1
    assert plugins[0]["is_default"] is True
```

### 属性测试（Property-Based Testing）

使用 Hypothesis 库进行属性测试，验证系统在各种输入下的正确性。

#### Property 1: 默认插件全局唯一性

```python
from hypothesis import given, strategies as st

@given(
    plugin_name=st.text(min_size=1, max_size=100),
    display_name=st.text(min_size=1, max_size=200)
)
async def test_default_plugin_uniqueness(plugin_name, display_name):
    """
    **Feature: admin-mcp-defaults, Property 1: 默认插件全局唯一性**
    
    For any 默认插件，plugin_name 应该在所有默认插件中唯一
    """
    # 创建第一个默认插件
    plugin1 = await repo.create_default_plugin(
        MCPPluginCreate(
            plugin_name=plugin_name,
            display_name=display_name,
            server_url="http://test.com"
        )
    )
    
    # 尝试创建同名默认插件
    with pytest.raises(IntegrityError):
        await repo.create_default_plugin(
            MCPPluginCreate(
                plugin_name=plugin_name,
                display_name=display_name + "_2",
                server_url="http://test2.com"
            )
        )
```

#### Property 3: 用户可用插件合并正确性

```python
@given(
    user_id=st.integers(min_value=1, max_value=1000),
    num_default_plugins=st.integers(min_value=0, max_value=5),
    num_user_plugins=st.integers(min_value=0, max_value=5),
    num_other_user_plugins=st.integers(min_value=0, max_value=5)
)
async def test_user_available_plugins_merge(
    user_id, num_default_plugins, num_user_plugins, num_other_user_plugins
):
    """
    **Feature: admin-mcp-defaults, Property 3: 用户可用插件合并正确性**
    
    For any 用户 ID，查询用户可用插件应该返回所有默认插件和该用户的自定义插件的合并列表
    """
    # 创建默认插件
    default_plugins = []
    for i in range(num_default_plugins):
        plugin = await repo.create_default_plugin(
            MCPPluginCreate(
                plugin_name=f"default_{i}",
                display_name=f"Default {i}",
                server_url="http://test.com"
            )
        )
        default_plugins.append(plugin)
    
    # 创建用户插件
    user_plugins = []
    for i in range(num_user_plugins):
        plugin = await repo.create_user_plugin(
            user_id=user_id,
            plugin_data=MCPPluginCreate(
                plugin_name=f"user_{user_id}_{i}",
                display_name=f"User {user_id} Plugin {i}",
                server_url="http://test.com"
            )
        )
        user_plugins.append(plugin)
    
    # 创建其他用户的插件
    other_user_id = user_id + 1000
    for i in range(num_other_user_plugins):
        await repo.create_user_plugin(
            user_id=other_user_id,
            plugin_data=MCPPluginCreate(
                plugin_name=f"user_{other_user_id}_{i}",
                display_name=f"User {other_user_id} Plugin {i}",
                server_url="http://test.com"
            )
        )
    
    # 获取用户可用插件
    available_plugins = await repo.get_all_available_plugins(user_id)
    
    # 验证数量正确
    expected_count = num_default_plugins + num_user_plugins
    assert len(available_plugins) == expected_count
    
    # 验证包含所有默认插件
    available_ids = [p.id for p in available_plugins]
    for default_plugin in default_plugins:
        assert default_plugin.id in available_ids
    
    # 验证包含所有用户插件
    for user_plugin in user_plugins:
        assert user_plugin.id in available_ids
```

#### Property 5: 工具调用降级一致性

```python
@given(
    prompt=st.text(min_size=1, max_size=1000),
    temperature=st.floats(min_value=0.0, max_value=2.0)
)
async def test_mcp_fallback_consistency(prompt, temperature):
    """
    **Feature: admin-mcp-defaults, Property 5: 工具调用降级一致性**
    
    For any MCP 工具调用失败的情况，系统应该降级为普通生成模式
    """
    # Mock 工具调用失败
    mcp_tool_service.get_user_enabled_tools = AsyncMock(
        side_effect=Exception("Tool service failed")
    )
    
    # 使用 MCP 生成（会降级）
    result_with_mcp = await llm_service.generate_with_mcp(
        prompt=prompt,
        user_id=1,
        enable_mcp=True,
        temperature=temperature
    )
    
    # 验证降级标志
    assert result_with_mcp["mcp_enhanced"] is False
    assert result_with_mcp["tool_calls_made"] == 0
    
    # 验证有内容返回
    assert result_with_mcp["content"] != ""
    assert result_with_mcp["finish_reason"] in ["stop", "length"]
```

### 集成测试

**测试目标**：验证完整的业务流程

```python
# test_mcp_integration.py

async def test_end_to_end_mcp_generation():
    """端到端测试：从配置插件到使用 MCP 生成"""
    # 1. 管理员创建默认插件
    plugin_response = await admin_client.post(
        "/api/admin/mcp/plugins",
        json={
            "plugin_name": "test_search",
            "display_name": "Test Search",
            "server_url": "http://test-mcp-server.com",
            "category": "search",
            "enabled": True
        }
    )
    assert plugin_response.status_code == 201
    
    # 2. 用户查看可用插件
    plugins_response = await user_client.get("/api/mcp/plugins")
    plugins = plugins_response.json()
    assert len(plugins) >= 1
    assert any(p["plugin_name"] == "test_search" for p in plugins)
    
    # 3. 用户使用 MCP 生成内容
    generate_response = await user_client.post(
        "/api/novels/generate",
        json={
            "prompt": "写一篇科幻小说",
            "enable_mcp": True
        }
    )
    result = generate_response.json()
    
    # 4. 验证生成结果
    assert result["content"] != ""
    # 如果 MCP 服务可用，应该使用了 MCP
    # 如果不可用，应该降级为普通生成
    assert "mcp_enhanced" in result
```

