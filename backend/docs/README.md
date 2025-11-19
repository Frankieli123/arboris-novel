# Arboris Novel 后端文档

欢迎查阅 Arboris Novel 后端系统文档。

## 文档索引

### 异步任务系统

异步任务系统用于处理长时间运行的 LLM 操作，避免 CDN 超时问题。

- **[异步任务 API 文档](./async_task_api.md)** - 完整的 API 端点说明和使用示例
  - 任务创建端点
  - 任务查询端点
  - 错误处理
  - 使用流程

- **[部署指南](./deployment_guide.md)** - 部署和配置异步任务系统
  - 数据库迁移步骤
  - 环境变量配置
  - 监控和日志
  - 故障排查
  - 性能优化

- **[前端使用文档](./frontend_task_usage.md)** - 前端集成指南
  - useTaskPolling composable 使用
  - TaskProgressModal 组件使用
  - 完整集成示例
  - 最佳实践

- **[管理员监控端点](./admin_task_endpoints.md)** - 管理员功能
  - 任务统计端点
  - 任务列表查询
  - 监控和调试

## 快速开始

### 对于 API 使用者

如果你想了解如何使用异步任务 API，请阅读：
1. [异步任务 API 文档](./async_task_api.md) - 了解所有可用的端点
2. 查看 API 使用示例

### 对于部署人员

如果你需要部署或配置系统，请阅读：
1. [部署指南](./deployment_guide.md) - 完整的部署步骤
2. 配置环境变量
3. 执行数据库迁移

### 对于前端开发者

如果你需要在前端集成异步任务，请阅读：
1. [前端使用文档](./frontend_task_usage.md) - 完整的集成指南
2. 查看代码示例
3. 了解最佳实践

### 对于管理员

如果你需要监控和管理任务，请阅读：
1. [管理员监控端点](./admin_task_endpoints.md) - 监控功能说明
2. 了解如何查看任务统计
3. 学习故障排查方法

## 系统架构

异步任务系统采用以下架构：

```
前端 (Vue.js)
    ↓ 创建任务
后端 API (FastAPI)
    ↓ 保存到数据库
数据库 (MySQL/SQLite)
    ↑ 获取待处理任务
TaskWorker (后台线程)
    ↓ 执行任务
LLM API (OpenAI 等)
```

### 核心组件

1. **AsyncTask 模型** - 数据库表，存储任务信息
2. **TaskService** - 任务管理服务层
3. **TaskWorker** - 后台任务执行器
4. **API 路由** - 任务创建和查询端点
5. **前端轮询** - useTaskPolling composable

## 工作流程

1. 用户在前端发起操作（如生成章节）
2. 前端调用 API 创建任务
3. API 立即返回任务 ID
4. TaskWorker 从数据库获取待处理任务
5. TaskWorker 执行任务并更新状态
6. 前端通过轮询获取任务状态和结果

## 支持的任务类型

- `concept_converse` - 概念对话
- `blueprint_generate` - 蓝图生成
- `chapter_generate` - 章节生成
- `chapter_evaluate` - 章节评估
- `outline_generate` - 大纲生成

## 常见问题

### 任务一直处于 pending 状态？

检查 TaskWorker 是否正常运行。参见 [部署指南 - 故障排查](./deployment_guide.md#故障排查)。

### 如何调整并发数？

修改 `TASK_WORKER_MAX_WORKERS` 环境变量。参见 [部署指南 - 配置项](./deployment_guide.md#配置项)。

### 前端如何集成？

使用 `useTaskPolling` composable。参见 [前端使用文档](./frontend_task_usage.md)。

### 如何监控任务状态？

使用管理员监控端点。参见 [管理员监控端点](./admin_task_endpoints.md)。

## 贡献

如果你发现文档有误或需要改进，欢迎：
- 提交 Issue
- 提交 Pull Request
- 在社区讨论

## 相关链接

- [项目主页](https://github.com/t59688/arboris-novel)
- [在线演示](https://arboris.aozhiai.com)
- [问题反馈](https://github.com/t59688/arboris-novel/issues)
