# 管理员设置重构说明

## 变更概述

将原本独立的"API 设置"和"嵌入模型设置"两个卡片整合到"系统配置"统一管理。

## 重构原因

1. **简化界面**：减少重复的表单和保存按钮，提升用户体验
2. **统一管理**：所有配置项在同一个表格中管理，更加直观
3. **易于扩展**：新增配置项只需在表格中添加，无需修改界面代码
4. **减少代码**：删除了大量重复的状态管理和保存逻辑

## 变更内容

### 前端变更

#### 删除的功能
- 删除了"API 设置"独立卡片
- 删除了"嵌入模型设置"独立卡片
- 删除了相关的响应式状态（`apiSettings`, `embeddingSettings`）
- 删除了相关的保存函数（`saveApiSettings`, `saveEmbeddingSettings`）
- 删除了配置同步函数（`hydrateSettingsFromConfigs`）

#### 保留的功能
- "每日请求额度"设置（独立卡片）
- "系统配置"表格（统一管理所有配置）
- 配置的增删改查功能

### 后端变更

无需变更，后端 API 保持不变。

## 使用方式

### 配置 LLM API

在"系统配置"中添加或编辑以下配置项：

```
llm.api_key - 默认 LLM API Key
llm.base_url - 默认大模型 API Base URL
llm.model - 默认 LLM 模型名称
```

### 配置嵌入模型

在"系统配置"中添加或编辑以下配置项：

```
embedding.provider - 嵌入模型提供方（openai/ollama）
embedding.api_key - 嵌入模型 API Key
embedding.base_url - 嵌入模型 Base URL
embedding.model - 嵌入模型名称
embedding.model_vector_size - 向量维度
ollama.embedding_base_url - Ollama 服务地址
ollama.embedding_model - Ollama 模型名称
```

## 优势

1. **更少的代码**：删除了约 150 行重复代码
2. **更好的维护性**：配置项集中管理，修改更方便
3. **更清晰的界面**：减少了视觉混乱，用户更容易找到配置
4. **更灵活的扩展**：新增配置无需修改前端代码

## 兼容性

- 后端 API 完全兼容，无需修改
- 数据库配置项保持不变
- 现有配置数据无需迁移
