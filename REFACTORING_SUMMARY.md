# 管理员设置重构总结

## 完成的工作

✅ 删除了"API 设置"独立卡片
✅ 删除了"嵌入模型设置"独立卡片  
✅ 统一使用"系统配置"表格管理所有配置项
✅ 简化了前端代码，删除了约 150 行重复代码
✅ 保持后端 API 完全兼容，无需修改

## 修改的文件

### 前端
- `frontend/src/components/admin/SettingsManagement.vue` - 重构主文件

### 文档
- `docs/admin_settings_guide.md` - 使用指南
- `docs/admin_settings_refactoring.md` - 重构说明

## 使用方式

管理员现在可以通过"系统配置"统一管理所有配置项：

1. 点击"新增配置"添加新的配置项
2. 点击"编辑"修改现有配置
3. 点击"删除"移除不需要的配置

常用配置项 Key：
- `llm.api_key`, `llm.base_url`, `llm.model`
- `embedding.provider`, `embedding.api_key`, `embedding.base_url`, `embedding.model`
- `ollama.embedding_base_url`, `ollama.embedding_model`

## 优势

- 界面更简洁，减少视觉混乱
- 配置管理更统一，易于维护
- 代码更精简，减少重复逻辑
- 扩展更灵活，新增配置无需修改代码
