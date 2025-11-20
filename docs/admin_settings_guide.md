# 管理员设置指南

## 系统配置管理

管理员可以通过"系统配置"统一管理所有配置项，包括 API 设置和嵌入模型设置。

### 常用配置项

#### LLM API 配置
- `llm.api_key` - 默认 LLM API Key，用于后台调用大模型
- `llm.base_url` - 默认大模型 API Base URL
- `llm.model` - 默认 LLM 模型名称

#### 嵌入模型配置
- `embedding.provider` - 嵌入模型提供方（openai 或 ollama）
- `embedding.api_key` - 嵌入模型专用 API Key（留空则使用默认 LLM API Key）
- `embedding.base_url` - 嵌入模型 Base URL（留空则使用默认 LLM Base URL）
- `embedding.model` - OpenAI 嵌入模型名称（如 text-embedding-3-large）
- `embedding.model_vector_size` - 嵌入向量维度（留空则自动检测）

#### Ollama 嵌入配置
- `ollama.embedding_base_url` - Ollama 嵌入模型服务地址
- `ollama.embedding_model` - Ollama 嵌入模型名称（如 nomic-embed-text）

### 操作说明

1. **新增配置**：点击"新增配置"按钮，填写 Key、值和描述
2. **编辑配置**：点击配置项的"编辑"按钮，修改值或描述
3. **删除配置**：点击配置项的"删除"按钮，确认后删除

### 配置示例

```
Key: llm.api_key
值: sk-xxxxxxxxxxxxx
描述: 默认 LLM API Key，用于后台调用大模型

Key: llm.base_url
值: https://api.openai.com/v1
描述: 默认大模型 API Base URL

Key: embedding.provider
值: openai
描述: 嵌入模型提供方，支持 openai 或 ollama
```

## 每日请求额度

设置未配置 API Key 的用户每日可用请求次数，用于控制系统资源使用。
