# 实施计划

## 当前状态

**已完成**: 
- ✅ 后端异步任务基础设施（任务1-7, 10, 12, 13, 14）
  - 数据库模型和迁移
  - TaskService和TaskWorker实现
  - API路由（任务创建和查询）
  - 后端API已迁移为异步模式
  - 属性测试和单元测试
  - 进度报告功能
  - 日志记录
  - 数据库故障处理和重试机制
  - 管理员监控端点和性能指标
- ✅ 前端基础组件（任务8-9）
  - useTaskPolling composable
  - TaskProgressModal组件
  - 任务API客户端
- ✅ 前端UI集成（任务11）
  - InspirationMode.vue已集成useTaskPolling
  - WritingDesk.vue已集成useTaskPolling
  - novel.ts API已更新为返回task_id
  - store已添加任务管理方法
- ✅ 文档（任务15）
  - API文档
  - 部署指南
  - 前端使用文档

**待完成**: 
- 前端属性测试（任务8.5）- 可选测试任务
- 最终检查点（任务16）

---

- [x] 1. 创建数据库模型和迁移
- [x] 1.1 创建AsyncTask模型类
  - 定义所有字段（id, user_id, task_type, status, progress等）
  - 添加关系映射（与User表的外键关系）
  - 添加索引定义
  - _需求: 1.3, 1.4_

- [x] 1.2 创建数据库迁移脚本
  - 使用Alembic创建迁移文件
  - 添加async_tasks表
  - 添加索引（user_id+status, status+created_at, expires_at）
  - _需求: 1.3_

- [x] 1.3 更新数据库base模块
  - 在__init__.py中导入AsyncTask模型
  - 确保模型被SQLAlchemy识别
  - _需求: 1.3_

- [x] 1.4 编写属性测试验证任务持久化
  - **Property 2: 任务持久化**
  - **验证: 需求 1.3**

- [x] 2. 实现TaskService服务层
- [x] 2.1 创建TaskService类基础结构
  - 实现create_task方法（创建任务并返回任务对象）
  - 实现get_task方法（根据ID和用户ID查询任务）
  - 实现update_task_status方法（更新任务状态和进度）
  - _需求: 1.1, 2.1_

- [x] 2.2 实现任务查询和管理方法
  - 实现get_pending_tasks方法（获取待处理任务列表）
  - 实现list_user_tasks方法（查询用户的任务列表）
  - 实现cleanup_expired_tasks方法（清理过期任务）
  - _需求: 2.1, 5.1, 5.4_

- [x] 2.3 添加权限验证逻辑
  - 在get_task中验证任务所有权
  - 不存在的任务抛出404异常
  - 无权访问的任务抛出403异常
  - _需求: 2.2, 2.3_

- [x] 2.4 编写属性测试验证任务查询权限控制
  - **Property 3: 任务查询权限控制**
  - **验证: 需求 2.1, 2.2, 2.3**

- [x] 2.5 编写属性测试验证任务清理机制
  - **Property 10: 任务清理机制**
  - **验证: 需求 5.4**

- [x] 3. 实现TaskWorker任务执行器
- [x] 3.1 创建TaskWorker类基础结构
  - 初始化ThreadPoolExecutor
  - 实现start方法（启动后台任务循环）
  - 实现stop方法（优雅关闭）
  - 实现任务获取循环逻辑
  - _需求: 3.1, 8.5_

- [x] 3.2 实现任务执行核心逻辑
  - 实现process_task方法（处理单个任务）
  - 实现状态转换逻辑（pending → processing → completed/failed）
  - 添加异常捕获和错误处理
  - 记录执行日志
  - _需求: 3.2, 3.3, 3.4, 3.5_

- [x] 3.3 实现任务类型处理器
  - 实现_execute_concept_converse方法
  - 实现_execute_blueprint_generate方法
  - 实现_execute_chapter_generate方法
  - 实现_execute_chapter_evaluate方法
  - 实现_execute_outline_generate方法
  - 每个处理器调用对应的现有服务方法
  - _需求: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 3.4 实现重试机制
  - 添加重试计数逻辑
  - 实现指数退避延迟
  - 达到最大重试次数后标记为failed
  - _需求: 8.1, 8.2_

- [x] 3.5 实现并发控制
  - 使用信号量限制并发任务数
  - 从配置读取最大并发数（默认3）
  - _需求: 5.5_

- [x] 3.6 编写属性测试验证任务状态转换
  - **Property 4: 任务状态转换正确性**
  - **验证: 需求 3.1, 3.2, 3.3, 3.4**

- [x] 3.7 编写属性测试验证异常处理
  - **Property 5: 异常处理完整性**
  - **验证: 需求 3.5**

- [x] 3.8 编写属性测试验证重试机制
  - **Property 15: 任务重试机制**
  - **验证: 需求 8.1, 8.2**

- [x] 3.9 编写属性测试验证并发控制
  - **Property 11: 并发控制**
  - **验证: 需求 5.5**

- [x] 4. 实现故障恢复和监控功能
- [x] 4.1 实现系统启动时的任务恢复
  - 在应用启动时查询所有processing状态的任务
  - 将它们重置为pending状态
  - 记录恢复日志
  - _需求: 5.3, 8.3_

- [x] 4.2 实现任务超时检测
  - 创建定时任务检查长时间运行的任务
  - 超时任务标记为failed
  - 记录超时日志
  - _需求: 5.2_

- [x] 4.3 实现定期清理过期任务
  - 创建定时任务清理过期任务
  - 从配置读取保留期限（默认7天）
  - 记录清理日志
  - _需求: 5.4_

- [x] 4.4 编写属性测试验证故障恢复
  - **Property 9: 故障恢复机制**
  - **验证: 需求 5.3, 8.3**

- [x] 4.5 编写属性测试验证超时处理
  - **Property 8: 任务超时处理**
  - **验证: 需求 5.2**

- [x] 4.6 编写属性测试验证优雅关闭
  - **Property 17: 优雅关闭**
  - **验证: 需求 8.5**

- [x] 5. 创建任务管理API路由
- [x] 5.1 创建tasks路由模块
  - 创建backend/app/api/routers/tasks.py文件
  - 定义APIRouter
  - 添加到主应用路由
  - _需求: 1.1_

- [x] 5.2 实现任务创建端点
  - POST /api/tasks/concept-converse（创建概念对话任务）
  - POST /api/tasks/blueprint-generate（创建蓝图生成任务）
  - POST /api/tasks/chapter-generate（创建章节生成任务）
  - POST /api/tasks/chapter-evaluate（创建章节评估任务）
  - POST /api/tasks/outline-generate（创建大纲生成任务）
  - 每个端点验证输入、创建任务、立即返回任务ID
  - _需求: 1.1, 1.2, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 5.3 实现任务查询端点
  - GET /api/tasks/{task_id}（查询任务状态）
  - 返回任务状态、进度、结果（如果完成）
  - 实现权限验证
  - _需求: 2.1, 2.2, 2.3_

- [x] 5.4 实现任务列表端点
  - GET /api/tasks（查询用户任务列表）
  - 支持按状态过滤
  - 支持分页
  - _需求: 5.1_

- [x] 5.5 编写属性测试验证任务创建响应时间
  - **Property 1: 任务创建立即响应**
  - **验证: 需求 1.1, 1.2, 1.4, 1.5**

- [x] 5.6 编写属性测试验证API异步迁移
  - **Property 14: API异步迁移一致性**
  - **验证: 需求 7.1, 7.2, 7.3, 7.4, 7.5**

- [x] 6. 创建Pydantic schemas
- [x] 6.1 创建任务相关的schema类
  - 创建TaskResponse schema（任务创建响应）
  - 创建TaskStatusResponse schema（任务状态查询响应）
  - 创建TaskSummary schema（任务摘要）
  - 创建各个任务类型的输入schema
  - _需求: 1.5, 2.1_

- [x] 6.2 添加schema验证逻辑
  - 验证task_type枚举值
  - 验证status枚举值
  - 验证progress范围（0-100）
  - _需求: 1.5_

- [x] 7. 集成TaskWorker到应用生命周期
- [x] 7.1 在main.py中初始化TaskWorker
  - 创建TaskWorker实例
  - 在startup事件中启动worker
  - 在shutdown事件中停止worker
  - 在启动时恢复processing状态的任务
  - _需求: 3.1, 5.3_

- [x] 7.2 添加配置项
  - 在Settings中添加task_worker_max_workers配置
  - 在Settings中添加task_max_execution_time配置
  - 在Settings中添加task_retention_days配置
  - _需求: 5.2, 5.4, 5.5_

- [x] 7.3 实现健康检查端点
  - GET /api/health/tasks（返回worker状态）
  - 返回当前处理中的任务数
  - 返回待处理任务数
  - _需求: 5.1_

- [x] 8. 实现前端轮询机制
- [x] 8.1 创建useTaskPolling composable
  - 创建frontend/src/composables/useTaskPolling.ts
  - 实现startPolling方法
  - 实现stopPolling方法
  - 实现状态管理（status, progress, result, error）
  - _需求: 4.1, 4.2, 4.3_

- [x] 8.2 实现轮询逻辑
  - 使用setInterval定期查询任务状态
  - 根据任务状态调整轮询间隔（pending/processing: 3秒）
  - 任务完成或失败时停止轮询
  - 达到最大轮询次数时停止并显示超时
  - _需求: 4.2, 4.3, 4.4_

- [x] 8.3 实现网络错误处理
  - 捕获网络错误
  - 使用指数退避策略重试
  - 记录错误日志
  - _需求: 4.5_

- [x] 8.4 编写属性测试验证轮询行为





  - **Property 6: 轮询行为正确性**
  - **验证: 需求 4.1, 4.2, 4.3, 4.4**

- [ ] 8.5 编写属性测试验证网络错误重试






  - **Property 7: 网络错误重试策略**
  - **验证: 需求 4.5**

- [x] 9. 创建前端任务进度组件
- [x] 9.1 创建TaskProgressModal组件
  - 创建frontend/src/components/TaskProgressModal.vue
  - 显示进度条
  - 显示进度消息
  - 显示任务状态
  - 支持取消操作（可选）
  - _需求: 6.1, 6.3_

- [x] 9.2 创建任务API客户端
  - 在frontend/src/api/中创建tasks.ts
  - 实现createTask方法
  - 实现getTaskStatus方法
  - 实现listTasks方法
  - _需求: 1.1, 2.1_

- [x] 9.3 添加错误提示组件
  - 显示用户友好的错误消息
  - 支持重试操作
  - _需求: 6.5_

- [x] 10. 迁移现有API到异步模式






- [x] 10.1 更新概念对话API






  - 修改POST /api/novels/{project_id}/concept/converse
  - 改为创建异步任务并返回任务ID
  - 保留原有的输入验证逻辑
  - _需求: 7.1_

- [x] 10.2 更新蓝图生成API










  - 修改POST /api/novels/{project_id}/blueprint/generate
  - 改为创建异步任务并返回任务ID
  - _需求: 7.2_

- [x] 10.3 更新章节生成API






  - 修改POST /api/writer/novels/{project_id}/chapters/generate
  - 改为创建异步任务并返回任务ID
  - _需求: 7.3_

- [x] 10.4 更新章节评估API





  - 修改POST /api/writer/novels/{project_id}/chapters/evaluate
  - 改为创建异步任务并返回任务ID
  - _需求: 7.4_

- [x] 10.5 更新大纲生成API




  - 修改POST /api/writer/novels/{project_id}/chapters/outline
  - 改为创建异步任务并返回任务ID
  - _需求: 7.5_

- [x] 11. 更新前端调用逻辑

- [x] 11.1 更新InspirationMode.vue
  - 修改sendConversation调用后使用useTaskPolling轮询任务状态
  - 修改generateBlueprint调用后使用useTaskPolling轮询任务状态
  - 集成TaskProgressModal组件展示进度
  - 处理任务完成后更新对话状态和蓝图数据
  - 处理任务失败和错误状态
  - _需求: 4.1, 6.1, 7.1, 7.2_

- [x] 11.2 更新WritingDesk相关组件
  - 修改generateChapter调用后使用useTaskPolling轮询任务状态
  - 修改evaluateChapter调用后使用useTaskPolling轮询任务状态
  - 修改generateChapterOutline调用后使用useTaskPolling轮询任务状态
  - 集成TaskProgressModal展示生成进度
  - 处理任务完成后更新章节数据
  - _需求: 4.1, 6.1, 7.3, 7.4, 7.5_

- [x] 11.3 更新novel store和API客户端
  - 修改NovelAPI.converseConcept返回任务ID而非直接结果
  - 修改NovelAPI.generateBlueprint返回任务ID而非直接结果
  - 修改NovelAPI.generateChapter返回任务ID而非直接结果
  - 修改NovelAPI.evaluateChapter返回任务ID而非直接结果
  - 修改NovelAPI.generateChapterOutline返回任务ID而非直接结果
  - 在store中添加任务状态管理逻辑
  - 添加任务结果处理逻辑
  - _需求: 4.1, 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 12. 添加进度报告功能
- [x] 12.1 在任务处理器中添加进度更新
  - 在_execute_concept_converse中更新进度
  - 在_execute_blueprint_generate中更新进度
  - 在_execute_chapter_generate中更新进度
  - 每个阶段更新progress和progress_message
  - _需求: 6.1, 6.2, 6.4_

- [x] 12.2 优化进度消息
  - 使用用户友好的描述（如"正在分析对话内容..."）
  - 避免技术术语
  - 提供预估时间（可选）
  - _需求: 6.5_

- [x] 12.3 编写属性测试验证进度信息
  - **Property 12: 进度信息完整性**
  - **验证: 需求 6.1, 6.2, 6.3**

- [x] 12.4 编写属性测试验证错误消息
  - **Property 13: 错误消息用户友好性**
  - **验证: 需求 6.5**

- [x] 13. 添加数据库故障处理

- [x] 13.1 实现数据库连接重试逻辑
  - 在TaskWorker中捕获数据库连接错误
  - 实现重试机制
  - 记录错误日志
  - _需求: 8.4_

- [x] 13.2 添加数据库健康检查
  - 定期检查数据库连接
  - 连接失败时暂停任务处理
  - 连接恢复后继续处理
  - _需求: 8.4_

- [x] 13.3 编写属性测试验证数据库故障恢复
  - **Property 16: 数据库故障恢复**
  - **验证: 需求 8.4**

- [x] 14. 添加日志和监控

- [x] 14.1 添加结构化日志
  - 记录任务创建事件
  - 记录任务状态变更
  - 记录错误和异常
  - 包含任务ID、用户ID、时间戳等上下文
  - _需求: 5.2, 8.4_

- [x] 14.2 添加性能指标
  - 记录任务执行时间
  - 记录任务成功率
  - 记录平均等待时间
  - _需求: 5.1_

- [x] 14.3 添加管理员监控端点
  - GET /api/admin/tasks/stats（任务统计）
  - GET /api/admin/tasks（所有任务列表）
  - 需要管理员权限
  - _需求: 5.1_

- [x] 15. 编写文档和部署指南

- [x] 15.1 更新API文档
  - 记录新的异步API端点
  - 记录任务状态查询端点
  - 提供使用示例
  - _需求: 1.1, 2.1_

- [x] 15.2 编写部署指南
  - 说明数据库迁移步骤
  - 说明配置项
  - 说明监控和日志
  - _需求: 5.3_

- [x] 15.3 更新前端使用文档
  - 说明如何使用useTaskPolling
  - 说明如何处理任务错误
  - 提供代码示例
  - _需求: 4.1_

- [x] 16. 最终检查点 - 确保所有测试通过



  - 确保所有测试通过，如有问题请询问用户
