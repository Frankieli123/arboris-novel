# 需求文档

## 简介

本系统是一个小说创作平台，当前通过同步API调用LLM服务来生成内容（如概念对话、蓝图生成、章节生成等）。由于这些操作耗时较长（可能超过100秒），在使用CDN时会触发524超时错误。本功能旨在引入后端异步任务处理机制和前端轮询机制，使长时间运行的操作能够在后台执行，前端通过轮询获取任务状态和结果。

## 术语表

- **AsyncTask（异步任务）**: 在后台执行的长时间运行操作，具有唯一标识符、状态和结果
- **TaskQueue（任务队列）**: 管理待执行和正在执行的异步任务的队列系统
- **TaskWorker（任务工作器）**: 从任务队列中获取任务并执行的后台进程
- **PollingClient（轮询客户端）**: 前端定期向服务器查询任务状态的机制
- **TaskStatus（任务状态）**: 任务的当前状态，包括 pending（待处理）、processing（处理中）、completed（已完成）、failed（失败）
- **LLMService（LLM服务）**: 调用大语言模型API的服务
- **CDN（内容分发网络）**: 用于加速内容传输的网络，可能对请求时长有限制

## 需求

### 需求 1

**用户故事:** 作为用户，我希望在发起长时间操作时能立即收到响应，这样我就不会因为超时错误而失败

#### 验收标准

1. WHEN 用户发起需要长时间处理的请求（如生成蓝图、生成章节）THEN 系统 SHALL 立即返回任务ID和初始状态，而不等待操作完成
2. WHEN 系统接收到长时间操作请求 THEN 系统 SHALL 在3秒内返回HTTP响应
3. WHEN 任务被创建 THEN 系统 SHALL 将任务信息持久化到数据库
4. WHEN 任务被创建 THEN 系统 SHALL 将任务状态设置为 pending
5. WHEN 任务被创建 THEN 系统 SHALL 返回包含任务ID、状态和创建时间的响应

### 需求 2

**用户故事:** 作为用户，我希望能够查询我提交的任务的当前状态，这样我就能知道操作是否完成

#### 验收标准

1. WHEN 用户使用有效的任务ID查询任务状态 THEN 系统 SHALL 返回任务的当前状态、进度信息和结果（如果已完成）
2. WHEN 用户查询不存在的任务ID THEN 系统 SHALL 返回404错误
3. WHEN 用户查询不属于自己的任务 THEN 系统 SHALL 返回403错误
4. WHEN 任务正在处理中 THEN 系统 SHALL 返回 processing 状态
5. WHEN 任务已完成 THEN 系统 SHALL 返回 completed 状态和完整结果数据

### 需求 3

**用户故事:** 作为系统，我需要在后台处理异步任务，这样长时间操作就不会阻塞API响应

#### 验收标准

1. WHEN 任务被创建并进入队列 THEN TaskWorker SHALL 从队列中获取待处理任务
2. WHEN TaskWorker 开始处理任务 THEN 系统 SHALL 将任务状态更新为 processing
3. WHEN 任务处理成功完成 THEN 系统 SHALL 将任务状态更新为 completed 并保存结果
4. WHEN 任务处理失败 THEN 系统 SHALL 将任务状态更新为 failed 并记录错误信息
5. WHEN 任务处理过程中发生异常 THEN 系统 SHALL 捕获异常并将错误信息保存到任务记录中

### 需求 4

**用户故事:** 作为前端开发者，我需要一个轮询机制来自动检查任务状态，这样用户就能看到实时进度

#### 验收标准

1. WHEN 前端收到任务ID THEN PollingClient SHALL 开始定期查询任务状态
2. WHEN 任务状态为 pending 或 processing THEN PollingClient SHALL 每隔2-5秒查询一次状态
3. WHEN 任务状态变为 completed 或 failed THEN PollingClient SHALL 停止轮询
4. WHEN 轮询超过最大重试次数 THEN PollingClient SHALL 停止轮询并显示超时错误
5. WHEN 轮询过程中发生网络错误 THEN PollingClient SHALL 使用指数退避策略重试

### 需求 5

**用户故事:** 作为系统管理员，我需要能够监控和管理异步任务，这样我就能确保系统正常运行

#### 验收标准

1. WHEN 管理员查询任务列表 THEN 系统 SHALL 返回所有任务的摘要信息（ID、状态、创建时间、用户）
2. WHEN 任务超过最大执行时间仍未完成 THEN 系统 SHALL 将任务标记为超时并记录日志
3. WHEN 系统重启 THEN 系统 SHALL 将所有 processing 状态的任务重置为 pending 状态
4. WHEN 任务完成超过保留期限 THEN 系统 SHALL 自动清理过期的任务记录
5. WHEN 系统资源不足 THEN TaskWorker SHALL 限制并发执行的任务数量

### 需求 6

**用户故事:** 作为用户，我希望在任务执行过程中能看到进度反馈，这样我就知道系统正在工作

#### 验收标准

1. WHEN 任务正在处理 THEN 系统 SHALL 提供进度百分比或阶段描述
2. WHEN 任务进度更新 THEN 系统 SHALL 将进度信息保存到任务记录
3. WHEN 前端轮询任务状态 THEN 系统 SHALL 返回最新的进度信息
4. WHEN 任务包含多个步骤 THEN 系统 SHALL 为每个步骤提供独立的进度信息
5. WHEN 任务失败 THEN 系统 SHALL 提供用户友好的错误消息

### 需求 7

**用户故事:** 作为开发者，我需要将现有的同步API迁移到异步模式，这样所有长时间操作都能受益于异步处理

#### 验收标准

1. WHEN 概念对话API被调用 THEN 系统 SHALL 创建异步任务并立即返回任务ID
2. WHEN 蓝图生成API被调用 THEN 系统 SHALL 创建异步任务并立即返回任务ID
3. WHEN 章节生成API被调用 THEN 系统 SHALL 创建异步任务并立即返回任务ID
4. WHEN 章节评估API被调用 THEN 系统 SHALL 创建异步任务并立即返回任务ID
5. WHEN 大纲生成API被调用 THEN 系统 SHALL 创建异步任务并立即返回任务ID

### 需求 8

**用户故事:** 作为系统，我需要确保任务执行的可靠性，这样即使出现故障也能恢复

#### 验收标准

1. WHEN 任务执行失败且配置了重试策略 THEN 系统 SHALL 自动重试任务
2. WHEN 任务重试次数达到上限 THEN 系统 SHALL 将任务标记为 failed
3. WHEN TaskWorker 崩溃 THEN 系统 SHALL 能够在重启后继续处理未完成的任务
4. WHEN 数据库连接失败 THEN 系统 SHALL 记录错误并在连接恢复后继续处理
5. WHEN 任务执行过程中系统关闭 THEN 系统 SHALL 优雅地停止任务处理并保存当前状态
