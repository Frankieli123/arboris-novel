"""任务执行器，负责从队列中获取任务并在后台执行。"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Callable, TypeVar, Any
from functools import wraps

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, DatabaseError

from ..db.session import AsyncSessionLocal
from ..models.async_task import AsyncTask
from .task_service import TaskService

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def retry_on_db_error(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 5,
    base_delay: float = 1.0,
    **kwargs: Any
) -> T:
    """
    数据库操作重试装饰器
    
    当遇到数据库连接错误时，使用指数退避策略重试
    
    Args:
        func: 要执行的异步函数
        *args: 函数参数
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        **kwargs: 函数关键字参数
        
    Returns:
        函数执行结果
        
    Raises:
        最后一次重试失败时的异常
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except (OperationalError, DatabaseError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"Database error in {func.__name__}, attempt {attempt + 1}/{max_retries}: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"Database error in {func.__name__} after {max_retries} attempts: {e}",
                    exc_info=True
                )
    
    raise last_exception


class TaskWorker:
    """任务工作器，负责从数据库队列中获取待处理任务并执行"""

    def __init__(self, max_workers: int = 3, max_execution_time: int = 900, retention_days: int = 7):
        """
        初始化任务工作器
        
        Args:
            max_workers: 最大并发任务数
            max_execution_time: 任务最大执行时间（秒）
            retention_days: 任务保留天数
        """
        self.max_workers = max_workers
        self.max_execution_time = max_execution_time
        self.retention_days = retention_days
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self._task_loop: Optional[asyncio.Task] = None
        self._timeout_check_loop: Optional[asyncio.Task] = None
        self._cleanup_loop: Optional[asyncio.Task] = None
        self._db_health_check_loop: Optional[asyncio.Task] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._db_healthy = True  # 数据库健康状态标志
        logger.info(f"TaskWorker initialized with max_workers={max_workers}, max_execution_time={max_execution_time}s, retention_days={retention_days}")

    async def start(self) -> None:
        """启动任务工作器，开始后台任务循环"""
        if self.running:
            logger.warning("TaskWorker is already running")
            return
        
        self.running = True
        self._db_healthy = True
        self._semaphore = asyncio.Semaphore(self.max_workers)
        self._task_loop = asyncio.create_task(self._run_task_loop())
        self._timeout_check_loop = asyncio.create_task(self._run_timeout_check_loop())
        self._cleanup_loop = asyncio.create_task(self._run_cleanup_loop())
        self._db_health_check_loop = asyncio.create_task(self._run_db_health_check_loop())
        logger.info("TaskWorker started")

    async def stop(self) -> None:
        """优雅关闭任务工作器"""
        if not self.running:
            logger.warning("TaskWorker is not running")
            return
        
        logger.info("Stopping TaskWorker...")
        self.running = False
        
        # 等待任务循环结束
        if self._task_loop:
            try:
                await asyncio.wait_for(self._task_loop, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("Task loop did not stop gracefully, cancelling...")
                self._task_loop.cancel()
        
        # 等待超时检查循环结束
        if self._timeout_check_loop:
            try:
                await asyncio.wait_for(self._timeout_check_loop, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout check loop did not stop gracefully, cancelling...")
                self._timeout_check_loop.cancel()
        
        # 等待清理循环结束
        if self._cleanup_loop:
            try:
                await asyncio.wait_for(self._cleanup_loop, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Cleanup loop did not stop gracefully, cancelling...")
                self._cleanup_loop.cancel()
        
        # 等待数据库健康检查循环结束
        if self._db_health_check_loop:
            try:
                await asyncio.wait_for(self._db_health_check_loop, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("DB health check loop did not stop gracefully, cancelling...")
                self._db_health_check_loop.cancel()
        
        # 关闭线程池
        self.executor.shutdown(wait=True, cancel_futures=False)
        logger.info("TaskWorker stopped")

    def is_running(self) -> bool:
        """
        检查任务工作器是否正在运行
        
        Returns:
            是否正在运行
        """
        return self.running

    def get_max_workers(self) -> int:
        """
        获取最大并发任务数
        
        Returns:
            最大并发任务数
        """
        return self.max_workers

    async def _run_task_loop(self) -> None:
        """任务获取循环，持续从队列中获取待处理任务"""
        logger.info("Task loop started")
        
        while self.running:
            try:
                # 检查数据库健康状态
                if not self._db_healthy:
                    logger.warning("Database is unhealthy, pausing task processing...")
                    await asyncio.sleep(5.0)
                    continue
                
                # 使用重试逻辑获取待处理任务
                async def fetch_tasks():
                    async with AsyncSessionLocal() as session:
                        task_service = TaskService(session, retention_days=self.retention_days)
                        return await task_service.get_pending_tasks(limit=self.max_workers)
                
                pending_tasks = await retry_on_db_error(fetch_tasks, max_retries=5, base_delay=1.0)
                
                if not pending_tasks:
                    # 没有待处理任务，等待后再检查
                    await asyncio.sleep(2.0)
                    continue
                
                # 处理每个任务
                for task in pending_tasks:
                    if not self.running:
                        break
                    
                    # 使用信号量控制并发
                    await self._semaphore.acquire()
                    
                    # 在后台处理任务
                    asyncio.create_task(self._process_task_with_semaphore(task))
                
                # 短暂休眠，避免过于频繁查询
                await asyncio.sleep(1.0)
                
            except (OperationalError, DatabaseError) as e:
                logger.error(f"Database error in task loop after retries: {e}", exc_info=True)
                self._db_healthy = False
                await asyncio.sleep(10.0)  # 数据库错误后等待更长时间
            except Exception as e:
                logger.error(f"Error in task loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)  # 出错后等待更长时间
        
        logger.info("Task loop stopped")

    async def _run_timeout_check_loop(self) -> None:
        """定期检查超时任务的循环"""
        logger.info("Timeout check loop started")
        
        while self.running:
            try:
                # 检查数据库健康状态
                if not self._db_healthy:
                    await asyncio.sleep(60.0)
                    continue
                
                # 使用重试逻辑检查超时任务
                async def check_timeouts():
                    async with AsyncSessionLocal() as session:
                        task_service = TaskService(session, retention_days=self.retention_days)
                        timeout_count = await task_service.check_timeout_tasks(self.max_execution_time)
                        await session.commit()
                        return timeout_count
                
                timeout_count = await retry_on_db_error(check_timeouts, max_retries=3, base_delay=2.0)
                
                if timeout_count > 0:
                    logger.warning(f"Marked {timeout_count} tasks as timed out")
                
                # 每60秒检查一次超时任务
                await asyncio.sleep(60.0)
                
            except (OperationalError, DatabaseError) as e:
                logger.error(f"Database error in timeout check loop: {e}", exc_info=True)
                await asyncio.sleep(60.0)
            except Exception as e:
                logger.error(f"Error in timeout check loop: {e}", exc_info=True)
                await asyncio.sleep(60.0)
        
        logger.info("Timeout check loop stopped")

    async def _run_cleanup_loop(self) -> None:
        """定期清理过期任务的循环"""
        logger.info("Cleanup loop started")
        
        while self.running:
            try:
                # 检查数据库健康状态
                if not self._db_healthy:
                    await asyncio.sleep(3600.0)
                    continue
                
                # 使用重试逻辑清理过期任务
                async def cleanup_tasks():
                    async with AsyncSessionLocal() as session:
                        task_service = TaskService(session, retention_days=self.retention_days)
                        cleanup_count = await task_service.cleanup_expired_tasks()
                        await session.commit()
                        return cleanup_count
                
                cleanup_count = await retry_on_db_error(cleanup_tasks, max_retries=3, base_delay=2.0)
                
                if cleanup_count > 0:
                    logger.info(f"Cleaned up {cleanup_count} expired tasks")
                
                # 每小时清理一次过期任务
                await asyncio.sleep(3600.0)
                
            except (OperationalError, DatabaseError) as e:
                logger.error(f"Database error in cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(3600.0)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                await asyncio.sleep(3600.0)
        
        logger.info("Cleanup loop stopped")

    async def _run_db_health_check_loop(self) -> None:
        """定期检查数据库连接健康状态的循环"""
        logger.info("Database health check loop started")
        
        while self.running:
            try:
                # 尝试执行简单的数据库查询来检查连接
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import text
                    await session.execute(text("SELECT 1"))
                
                # 如果查询成功，标记数据库为健康
                if not self._db_healthy:
                    logger.info("Database connection recovered")
                    self._db_healthy = True
                
                # 每30秒检查一次数据库健康状态
                await asyncio.sleep(30.0)
                
            except (OperationalError, DatabaseError) as e:
                if self._db_healthy:
                    logger.error(f"Database connection failed: {e}", exc_info=True)
                    self._db_healthy = False
                else:
                    logger.warning(f"Database still unhealthy: {e}")
                
                # 数据库不健康时，更频繁地检查（每10秒）
                await asyncio.sleep(10.0)
                
            except Exception as e:
                logger.error(f"Error in database health check loop: {e}", exc_info=True)
                await asyncio.sleep(30.0)
        
        logger.info("Database health check loop stopped")

    async def _process_task_with_semaphore(self, task: AsyncTask) -> None:
        """处理任务并释放信号量"""
        try:
            await self.process_task(task)
        finally:
            self._semaphore.release()

    async def process_task(self, task: AsyncTask) -> None:
        """
        处理单个任务
        
        Args:
            task: 要处理的任务对象
        """
        task_id = task.id
        task_type = task.task_type
        
        logger.info(f"Processing task: id={task_id} type={task_type}")
        
        # 创建新的数据库会话用于任务处理
        try:
            async with AsyncSessionLocal() as session:
                task_service = TaskService(session, retention_days=self.retention_days)
                
                try:
                    # 使用重试逻辑更新任务状态为 processing
                    async def update_to_processing():
                        await task_service.update_task_status(
                            task_id=task_id,
                            status="processing",
                            progress=0,
                            progress_message="开始处理任务..."
                        )
                        await session.commit()
                    
                    await retry_on_db_error(update_to_processing, max_retries=5, base_delay=1.0)
                    
                    # 执行任务
                    result = await self._execute_task(task, session)
                    
                    # 使用重试逻辑更新任务状态为 completed
                    async def update_to_completed():
                        await task_service.update_task_status(
                            task_id=task_id,
                            status="completed",
                            progress=100,
                            progress_message="任务完成",
                            result_data=result
                        )
                        await session.commit()
                    
                    await retry_on_db_error(update_to_completed, max_retries=5, base_delay=1.0)
                    
                    logger.info(f"Task completed successfully: id={task_id} type={task_type}")
                    
                except Exception as e:
                    logger.error(f"Task failed: id={task_id} type={task_type} error={e}", exc_info=True)
                    
                    # 检查是否需要重试
                    if task.retry_count < task.max_retries:
                        # 增加重试计数
                        retry_count = task.retry_count + 1
                        
                        # 计算指数退避延迟（秒）
                        delay = 2 ** retry_count
                        
                        logger.info(f"Task will be retried: id={task_id} retry={retry_count}/{task.max_retries} delay={delay}s")
                        
                        # 使用重试逻辑更新任务状态为 pending
                        async def update_to_pending():
                            await task_service.update_task_status(
                                task_id=task_id,
                                status="pending",
                                progress=0,
                                progress_message=f"任务失败，将在 {delay} 秒后重试（第 {retry_count} 次重试）",
                                error_message=str(e)
                            )
                        
                        await retry_on_db_error(update_to_pending, max_retries=5, base_delay=1.0)
                        
                        # 更新重试计数
                        async def update_retry_count():
                            async with AsyncSessionLocal() as retry_session:
                                from sqlalchemy import select, update
                                stmt = (
                                    update(AsyncTask)
                                    .where(AsyncTask.id == task_id)
                                    .values(retry_count=retry_count)
                                )
                                await retry_session.execute(stmt)
                                await retry_session.commit()
                        
                        await retry_on_db_error(update_retry_count, max_retries=5, base_delay=1.0)
                        
                        # 等待指数退避延迟
                        await asyncio.sleep(delay)
                    else:
                        # 达到最大重试次数，标记为失败
                        error_message = f"任务执行失败: {str(e)}"
                        
                        async def update_to_failed():
                            await task_service.update_task_status(
                                task_id=task_id,
                                status="failed",
                                progress=0,
                                progress_message="任务失败",
                                error_message=error_message
                            )
                            await session.commit()
                        
                        await retry_on_db_error(update_to_failed, max_retries=5, base_delay=1.0)
                        
                        logger.error(f"Task failed permanently: id={task_id} type={task_type}")
        
        except (OperationalError, DatabaseError) as e:
            logger.error(
                f"Database error while processing task {task_id} after all retries: {e}",
                exc_info=True
            )
            # 标记数据库为不健康
            self._db_healthy = False

    async def _execute_task(self, task: AsyncTask, session: AsyncSession) -> dict:
        """
        根据任务类型执行相应的处理逻辑
        
        Args:
            task: 任务对象
            session: 数据库会话
            
        Returns:
            任务执行结果
        """
        task_type = task.task_type
        
        if task_type == "concept_converse":
            return await self._execute_concept_converse(task, session)
        elif task_type == "blueprint_generate":
            return await self._execute_blueprint_generate(task, session)
        elif task_type == "chapter_generate":
            return await self._execute_chapter_generate(task, session)
        elif task_type == "chapter_evaluate":
            return await self._execute_chapter_evaluate(task, session)
        elif task_type == "outline_generate":
            return await self._execute_outline_generate(task, session)
        else:
            raise ValueError(f"Unknown task type: {task_type}")

    async def _execute_concept_converse(self, task: AsyncTask, session: AsyncSession) -> dict:
        """
        执行概念对话任务
        
        Args:
            task: 任务对象
            session: 数据库会话
            
        Returns:
            对话结果
        """
        import json
        from ..services.novel_service import NovelService
        from ..services.prompt_service import PromptService
        from ..services.llm_service import LLMService
        from ..utils.json_utils import remove_think_tags, sanitize_json_like_text, unwrap_markdown_json
        
        input_data = task.input_data
        project_id = input_data.get("project_id")
        user_input = input_data.get("user_input")
        user_id = task.user_id
        
        if not project_id or not user_input:
            raise ValueError("Missing required input data: project_id or user_input")
        
        # 更新进度
        task_service = TaskService(session)
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=10,
            progress_message="正在加载项目信息..."
        )
        await session.commit()
        
        novel_service = NovelService(session)
        prompt_service = PromptService(session)
        llm_service = LLMService(session)
        
        project = await novel_service.ensure_project_owner(project_id, user_id)
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=20,
            progress_message="正在准备对话历史..."
        )
        await session.commit()
        
        history_records = await novel_service.list_conversations(project_id)
        conversation_history = [
            {"role": record.role, "content": record.content}
            for record in history_records
        ]
        user_content = json.dumps(user_input, ensure_ascii=False)
        conversation_history.append({"role": "user", "content": user_content})
        
        system_prompt = await prompt_service.get_prompt("concept")
        if not system_prompt:
            raise ValueError("未配置名为 'concept' 的提示词")
        
        JSON_RESPONSE_INSTRUCTION = """
IMPORTANT: 你的回复必须是合法的 JSON 对象，并严格包含以下字段：
{
  "ai_message": "string",
  "ui_control": {
    "type": "single_choice | text_input | info_display",
    "options": [
      {"id": "option_1", "label": "string"}
    ],
    "placeholder": "string"
  },
  "conversation_state": {},
  "is_complete": false
}
不要输出额外的文本或解释。
"""
        system_prompt = f"{system_prompt}\n{JSON_RESPONSE_INSTRUCTION}"
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=40,
            progress_message="正在与AI对话..."
        )
        await session.commit()
        
        llm_response = await llm_service.get_llm_response(
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            temperature=0.8,
            user_id=user_id,
            timeout=240.0,
        )
        llm_response = remove_think_tags(llm_response)
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=80,
            progress_message="正在解析AI响应..."
        )
        await session.commit()
        
        normalized = unwrap_markdown_json(llm_response)
        sanitized = sanitize_json_like_text(normalized)
        parsed = json.loads(sanitized)
        
        # 保存对话记录
        await novel_service.append_conversation(project_id, "user", user_content)
        await novel_service.append_conversation(project_id, "assistant", normalized)
        
        if parsed.get("is_complete"):
            parsed["ready_for_blueprint"] = True
        
        parsed.setdefault("conversation_state", parsed.get("conversation_state", {}))
        
        return parsed

    async def _execute_blueprint_generate(self, task: AsyncTask, session: AsyncSession) -> dict:
        """
        执行蓝图生成任务
        
        Args:
            task: 任务对象
            session: 数据库会话
            
        Returns:
            蓝图生成结果
        """
        import json
        from typing import Dict, List
        from ..services.novel_service import NovelService
        from ..services.prompt_service import PromptService
        from ..services.llm_service import LLMService
        from ..utils.json_utils import remove_think_tags, sanitize_json_like_text, unwrap_markdown_json
        from ..schemas.novel import Blueprint
        
        input_data = task.input_data
        project_id = input_data.get("project_id")
        user_id = task.user_id
        
        if not project_id:
            raise ValueError("Missing required input data: project_id")
        
        # 更新进度
        task_service = TaskService(session)
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=10,
            progress_message="正在加载项目信息..."
        )
        await session.commit()
        
        novel_service = NovelService(session)
        prompt_service = PromptService(session)
        llm_service = LLMService(session)
        
        project = await novel_service.ensure_project_owner(project_id, user_id)
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=20,
            progress_message="正在准备对话历史..."
        )
        await session.commit()
        
        history_records = await novel_service.list_conversations(project_id)
        if not history_records:
            raise ValueError("缺少对话历史，请先完成概念对话后再生成蓝图")
        
        formatted_history: List[Dict[str, str]] = []
        for record in history_records:
            role = record.role
            content = record.content
            if not role or not content:
                continue
            try:
                normalized = unwrap_markdown_json(content)
                data = json.loads(normalized)
                if role == "user":
                    user_value = data.get("value", data)
                    if isinstance(user_value, str):
                        formatted_history.append({"role": "user", "content": user_value})
                elif role == "assistant":
                    ai_message = data.get("ai_message") if isinstance(data, dict) else None
                    if ai_message:
                        formatted_history.append({"role": "assistant", "content": ai_message})
            except (json.JSONDecodeError, AttributeError):
                continue
        
        if not formatted_history:
            raise ValueError("无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话")
        
        system_prompt = await prompt_service.get_prompt("screenwriting")
        if not system_prompt:
            raise ValueError("未配置名为 'screenwriting' 的提示词")
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=40,
            progress_message="正在生成蓝图..."
        )
        await session.commit()
        
        blueprint_raw = await llm_service.get_llm_response(
            system_prompt=system_prompt,
            conversation_history=formatted_history,
            temperature=0.3,
            user_id=user_id,
            timeout=1200.0,
        )
        blueprint_raw = remove_think_tags(blueprint_raw)
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=80,
            progress_message="正在解析蓝图..."
        )
        await session.commit()
        
        blueprint_normalized = unwrap_markdown_json(blueprint_raw)
        blueprint_sanitized = sanitize_json_like_text(blueprint_normalized)
        blueprint_data = json.loads(blueprint_sanitized)
        
        blueprint = Blueprint(**blueprint_data)
        await novel_service.replace_blueprint(project_id, blueprint)
        
        if blueprint.title:
            project.title = blueprint.title
            project.status = "blueprint_ready"
            await session.commit()
        
        ai_message = (
            "太棒了！我已经根据我们的对话整理出完整的小说蓝图。请确认是否进入写作阶段，或提出修改意见。"
        )
        
        return {
            "blueprint": blueprint_data,
            "ai_message": ai_message
        }

    async def _execute_chapter_generate(self, task: AsyncTask, session: AsyncSession) -> dict:
        """
        执行章节生成任务
        
        Args:
            task: 任务对象
            session: 数据库会话
            
        Returns:
            章节生成结果
        """
        import json
        import os
        from typing import Dict, List, Optional
        from ..services.novel_service import NovelService
        from ..services.prompt_service import PromptService
        from ..services.llm_service import LLMService
        from ..services.chapter_context_service import ChapterContextService
        from ..services.vector_store_service import VectorStoreService
        from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
        from ..core.config import settings
        from ..repositories.system_config_repository import SystemConfigRepository
        
        input_data = task.input_data
        project_id = input_data.get("project_id")
        chapter_number = input_data.get("chapter_number")
        writing_notes = input_data.get("writing_notes")
        user_id = task.user_id
        
        if not project_id or chapter_number is None:
            raise ValueError("Missing required input data: project_id or chapter_number")
        
        # 更新进度
        task_service = TaskService(session)
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=5,
            progress_message="正在加载项目信息..."
        )
        await session.commit()
        
        novel_service = NovelService(session)
        prompt_service = PromptService(session)
        llm_service = LLMService(session)
        
        project = await novel_service.ensure_project_owner(project_id, user_id)
        outline = await novel_service.get_outline(project_id, chapter_number)
        if not outline:
            raise ValueError("蓝图中未找到对应章节纲要")
        
        chapter = await novel_service.get_or_create_chapter(project_id, chapter_number)
        chapter.real_summary = None
        chapter.selected_version_id = None
        chapter.status = "generating"
        await session.commit()
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=10,
            progress_message="正在准备章节上下文..."
        )
        await session.commit()
        
        # 准备上下文
        outlines_map = {item.chapter_number: item for item in project.outlines}
        completed_chapters = []
        latest_prev_number = -1
        previous_summary_text = ""
        previous_tail_excerpt = ""
        
        for existing in project.chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                summary = await llm_service.get_summary(
                    existing.selected_version.content,
                    temperature=0.15,
                    user_id=user_id,
                    timeout=180.0,
                )
                existing.real_summary = remove_think_tags(summary)
                await session.commit()
            completed_chapters.append(
                {
                    "chapter_number": existing.chapter_number,
                    "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
                    "summary": existing.real_summary,
                }
            )
            if existing.chapter_number > latest_prev_number:
                latest_prev_number = existing.chapter_number
                previous_summary_text = existing.real_summary or ""
                content = existing.selected_version.content or ""
                stripped = content.strip()
                previous_tail_excerpt = stripped[-500:] if len(stripped) > 500 else stripped
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=20,
            progress_message="正在检索相关剧情..."
        )
        await session.commit()
        
        project_schema = await novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump()
        
        if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
            for relation in blueprint_dict["relationships"]:
                if "character_from" in relation:
                    relation["from"] = relation.pop("character_from")
                if "character_to" in relation:
                    relation["to"] = relation.pop("character_to")
        
        banned_blueprint_keys = {
            "chapter_outline",
            "chapter_summaries",
            "chapter_details",
            "chapter_dialogues",
            "chapter_events",
            "conversation_history",
            "character_timelines",
        }
        for key in banned_blueprint_keys:
            if key in blueprint_dict:
                blueprint_dict.pop(key, None)
        
        writer_prompt = await prompt_service.get_prompt("writing")
        if not writer_prompt:
            raise ValueError("缺少写作提示词，请联系管理员配置 'writing' 提示词")
        
        # 初始化向量检索
        vector_store: Optional[VectorStoreService]
        if not settings.vector_store_enabled:
            vector_store = None
        else:
            try:
                vector_store = VectorStoreService()
            except RuntimeError:
                vector_store = None
        
        context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)
        
        outline_title = outline.title or f"第{outline.chapter_number}章"
        outline_summary = outline.summary or "暂无摘要"
        query_parts = [outline_title, outline_summary]
        if writing_notes:
            query_parts.append(writing_notes)
        rag_query = "\n".join(part for part in query_parts if part)
        rag_context = await context_service.retrieve_for_generation(
            project_id=project_id,
            query_text=rag_query or outline.title or outline.summary or "",
            user_id=user_id,
        )
        
        # 准备提示词
        blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
        previous_summary_text = previous_summary_text or "暂无可用摘要"
        previous_tail_excerpt = previous_tail_excerpt or "暂无上一章结尾内容"
        rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context and rag_context.chunks else "未检索到章节片段"
        rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context and rag_context.summaries else "未检索到章节摘要"
        writing_notes_text = writing_notes or "无额外写作指令"
        
        prompt_sections = [
            ("[世界蓝图](JSON)", blueprint_text),
            ("[上一章摘要]", previous_summary_text),
            ("[上一章结尾]", previous_tail_excerpt),
            ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
            ("[检索到的章节摘要]", rag_summaries_text),
            (
                "[当前章节目标]",
                f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes_text}",
            ),
        ]
        prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
        
        # 获取版本数量
        repo = SystemConfigRepository(session)
        record = await repo.get_by_key("writer.chapter_versions")
        version_count = 3
        if record:
            try:
                value = int(record.value)
                if value > 0:
                    version_count = value
            except (TypeError, ValueError):
                pass
        if version_count <= 0:
            env_value = os.getenv("WRITER_CHAPTER_VERSION_COUNT")
            if env_value:
                try:
                    value = int(env_value)
                    if value > 0:
                        version_count = value
                except ValueError:
                    pass
        
        # 生成多个版本
        raw_versions = []
        for idx in range(version_count):
            progress = 30 + int((idx / version_count) * 50)
            await task_service.update_task_status(
                task_id=task.id,
                status="processing",
                progress=progress,
                progress_message=f"正在生成第 {idx + 1}/{version_count} 个版本..."
            )
            await session.commit()
            
            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": prompt_input}],
                temperature=0.9,
                user_id=user_id,
                timeout=1200.0,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            try:
                raw_versions.append(json.loads(normalized))
            except json.JSONDecodeError:
                raw_versions.append({"content": normalized})
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=85,
            progress_message="正在保存章节版本..."
        )
        await session.commit()
        
        contents: List[str] = []
        metadata: List[Dict] = []
        for variant in raw_versions:
            if isinstance(variant, dict):
                if "content" in variant and isinstance(variant["content"], str):
                    contents.append(variant["content"])
                elif "chapter_content" in variant:
                    contents.append(str(variant["chapter_content"]))
                else:
                    contents.append(json.dumps(variant, ensure_ascii=False))
                metadata.append(variant)
            else:
                contents.append(str(variant))
                metadata.append({"raw": variant})
        
        await novel_service.replace_chapter_versions(chapter, contents, metadata)
        
        return {
            "chapter_number": chapter_number,
            "versions_count": len(contents),
            "status": "success"
        }

    async def _execute_chapter_evaluate(self, task: AsyncTask, session: AsyncSession) -> dict:
        """
        执行章节评估任务
        
        Args:
            task: 任务对象
            session: 数据库会话
            
        Returns:
            章节评估结果
        """
        import json
        from ..services.novel_service import NovelService
        from ..services.prompt_service import PromptService
        from ..services.llm_service import LLMService
        from ..utils.json_utils import remove_think_tags
        
        input_data = task.input_data
        project_id = input_data.get("project_id")
        chapter_number = input_data.get("chapter_number")
        user_id = task.user_id
        
        if not project_id or chapter_number is None:
            raise ValueError("Missing required input data: project_id or chapter_number")
        
        # 更新进度
        task_service = TaskService(session)
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=10,
            progress_message="正在加载章节信息..."
        )
        await session.commit()
        
        novel_service = NovelService(session)
        prompt_service = PromptService(session)
        llm_service = LLMService(session)
        
        project = await novel_service.ensure_project_owner(project_id, user_id)
        chapter = next((ch for ch in project.chapters if ch.chapter_number == chapter_number), None)
        if not chapter:
            raise ValueError("章节不存在")
        if not chapter.versions:
            raise ValueError("无可评估的章节版本")
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=20,
            progress_message="正在准备评估数据..."
        )
        await session.commit()
        
        evaluator_prompt = await prompt_service.get_prompt("evaluation")
        if not evaluator_prompt:
            raise ValueError("缺少评估提示词，请联系管理员配置 'evaluation' 提示词")
        
        project_schema = await novel_service._serialize_project(project)
        blueprint_dict = project_schema.blueprint.model_dump()
        
        versions_to_evaluate = [
            {"version_id": idx + 1, "content": version.content}
            for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
        ]
        
        evaluator_payload = {
            "novel_blueprint": blueprint_dict,
            "content_to_evaluate": {
                "chapter_number": chapter.chapter_number,
                "versions": versions_to_evaluate,
            },
        }
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=40,
            progress_message="正在评估章节..."
        )
        await session.commit()
        
        evaluation_raw = await llm_service.get_llm_response(
            system_prompt=evaluator_prompt,
            conversation_history=[{"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)}],
            temperature=0.3,
            user_id=user_id,
            timeout=360.0,
        )
        evaluation_clean = remove_think_tags(evaluation_raw)
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=80,
            progress_message="正在保存评估结果..."
        )
        await session.commit()
        
        await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)
        
        return {
            "chapter_number": chapter_number,
            "evaluation": evaluation_clean,
            "status": "success"
        }

    async def _execute_outline_generate(self, task: AsyncTask, session: AsyncSession) -> dict:
        """
        执行大纲生成任务
        
        Args:
            task: 任务对象
            session: 数据库会话
            
        Returns:
            大纲生成结果
        """
        import json
        from sqlalchemy import select
        from ..models.novel import ChapterOutline
        from ..services.novel_service import NovelService
        from ..services.prompt_service import PromptService
        from ..services.llm_service import LLMService
        from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
        
        input_data = task.input_data
        project_id = input_data.get("project_id")
        start_chapter = input_data.get("start_chapter", 1)
        num_chapters = input_data.get("num_chapters", 10)
        user_id = task.user_id
        
        if not project_id:
            raise ValueError("Missing required input data: project_id")
        
        # 更新进度
        task_service = TaskService(session)
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=10,
            progress_message="正在加载项目信息..."
        )
        await session.commit()
        
        novel_service = NovelService(session)
        prompt_service = PromptService(session)
        llm_service = LLMService(session)
        
        await novel_service.ensure_project_owner(project_id, user_id)
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=20,
            progress_message="正在准备蓝图数据..."
        )
        await session.commit()
        
        outline_prompt = await prompt_service.get_prompt("outline")
        if not outline_prompt:
            raise ValueError("缺少大纲提示词，请联系管理员配置 'outline' 提示词")
        
        project_schema = await novel_service.get_project_schema(project_id, user_id)
        blueprint_dict = project_schema.blueprint.model_dump()
        
        payload = {
            "novel_blueprint": blueprint_dict,
            "wait_to_generate": {
                "start_chapter": start_chapter,
                "num_chapters": num_chapters,
            },
        }
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=40,
            progress_message="正在生成章节大纲..."
        )
        await session.commit()
        
        response = await llm_service.get_llm_response(
            system_prompt=outline_prompt,
            conversation_history=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            temperature=0.7,
            user_id=user_id,
            timeout=360.0,
        )
        normalized = unwrap_markdown_json(remove_think_tags(response))
        data = json.loads(normalized)
        
        # 更新进度
        await task_service.update_task_status(
            task_id=task.id,
            status="processing",
            progress=80,
            progress_message="正在保存大纲..."
        )
        await session.commit()
        
        new_outlines = data.get("chapters", [])
        for item in new_outlines:
            stmt = (
                select(ChapterOutline)
                .where(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == item.get("chapter_number"),
                )
            )
            result = await session.execute(stmt)
            record = result.scalars().first()
            if record:
                record.title = item.get("title", record.title)
                record.summary = item.get("summary", record.summary)
            else:
                session.add(
                    ChapterOutline(
                        project_id=project_id,
                        chapter_number=item.get("chapter_number"),
                        title=item.get("title", ""),
                        summary=item.get("summary"),
                    )
                )
        await session.commit()
        
        return {
            "start_chapter": start_chapter,
            "num_chapters": num_chapters,
            "generated_count": len(new_outlines),
            "status": "success"
        }
