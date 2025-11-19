"""任务管理服务，负责异步任务的创建、查询和状态更新。"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.async_task import AsyncTask


class TaskService:
    """任务管理服务"""

    def __init__(self, session: AsyncSession, retention_days: int = 7):
        self.session = session
        self.retention_days = retention_days

    async def create_task(
        self,
        user_id: int,
        task_type: str,
        input_data: dict,
        max_retries: int = 3,
    ) -> AsyncTask:
        """
        创建新的异步任务
        
        Args:
            user_id: 任务所属用户ID
            task_type: 任务类型
            input_data: 任务输入参数
            max_retries: 最大重试次数
            
        Returns:
            创建的任务对象
        """
        task = AsyncTask(
            id=str(uuid4()),
            user_id=user_id,
            task_type=task_type,
            status="pending",
            progress=0,
            input_data=input_data,
            max_retries=max_retries,
            retry_count=0,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=self.retention_days),
        )
        
        self.session.add(task)
        await self.session.flush()
        return task

    async def get_task(
        self,
        task_id: str,
        user_id: int,
    ) -> AsyncTask:
        """
        根据ID和用户ID查询任务
        
        Args:
            task_id: 任务ID
            user_id: 用户ID
            
        Returns:
            任务对象
            
        Raises:
            HTTPException: 任务不存在(404)或无权访问(403)
        """
        stmt = select(AsyncTask).where(AsyncTask.id == task_id)
        result = await self.session.execute(stmt)
        task = result.scalars().first()
        
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        if task.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此任务"
            )
        
        return task

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: Optional[int] = None,
        progress_message: Optional[str] = None,
        result_data: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        更新任务状态和进度
        
        Args:
            task_id: 任务ID
            status: 新状态
            progress: 进度百分比(0-100)
            progress_message: 进度描述
            result_data: 任务结果数据
            error_message: 错误信息
        """
        stmt = select(AsyncTask).where(AsyncTask.id == task_id)
        result = await self.session.execute(stmt)
        task = result.scalars().first()
        
        if task is None:
            return
        
        task.status = status
        
        if progress is not None:
            task.progress = progress
        
        if progress_message is not None:
            task.progress_message = progress_message
        
        if result_data is not None:
            task.result_data = result_data
        
        if error_message is not None:
            task.error_message = error_message
        
        # 更新时间戳
        if status == "processing" and task.started_at is None:
            task.started_at = datetime.utcnow()
        
        if status in ("completed", "failed"):
            task.completed_at = datetime.utcnow()
        
        await self.session.flush()

    async def get_pending_tasks(
        self,
        limit: int = 10,
    ) -> List[AsyncTask]:
        """
        获取待处理任务列表
        
        Args:
            limit: 返回的最大任务数
            
        Returns:
            待处理任务列表
        """
        stmt = (
            select(AsyncTask)
            .where(AsyncTask.status == "pending")
            .order_by(AsyncTask.created_at)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_user_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[AsyncTask]:
        """
        查询用户的任务列表
        
        Args:
            user_id: 用户ID
            status: 可选的状态过滤
            limit: 返回的最大任务数
            
        Returns:
            用户任务列表
        """
        stmt = select(AsyncTask).where(AsyncTask.user_id == user_id)
        
        if status is not None:
            stmt = stmt.where(AsyncTask.status == status)
        
        stmt = stmt.order_by(AsyncTask.created_at.desc()).limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cleanup_expired_tasks(self) -> int:
        """
        清理过期任务
        
        Returns:
            清理的任务数量
        """
        now = datetime.utcnow()
        
        stmt = delete(AsyncTask).where(AsyncTask.expires_at < now)
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount

    async def recover_processing_tasks(self) -> int:
        """
        恢复处于processing状态的任务，将它们重置为pending状态
        用于系统启动时的故障恢复
        
        Returns:
            恢复的任务数量
        """
        from sqlalchemy import update
        
        stmt = (
            update(AsyncTask)
            .where(AsyncTask.status == "processing")
            .values(
                status="pending",
                started_at=None,
                progress=0,
                progress_message="任务已恢复，等待重新处理"
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount

    async def check_timeout_tasks(self, max_execution_time: int) -> int:
        """
        检查并标记超时的任务
        
        Args:
            max_execution_time: 最大执行时间（秒）
            
        Returns:
            标记为超时的任务数量
        """
        from sqlalchemy import update
        
        timeout_threshold = datetime.utcnow() - timedelta(seconds=max_execution_time)
        
        stmt = (
            update(AsyncTask)
            .where(
                AsyncTask.status == "processing",
                AsyncTask.started_at < timeout_threshold
            )
            .values(
                status="failed",
                completed_at=datetime.utcnow(),
                error_message=f"任务执行超时（超过{max_execution_time}秒）"
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount

    async def count_tasks_by_status(self, status: str) -> int:
        """
        统计指定状态的任务数量
        
        Args:
            status: 任务状态
            
        Returns:
            任务数量
        """
        from sqlalchemy import func
        
        stmt = select(func.count(AsyncTask.id)).where(AsyncTask.status == status)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_all_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AsyncTask]:
        """
        查询所有任务列表（管理员用）
        
        Args:
            status: 可选的状态过滤
            task_type: 可选的任务类型过滤
            limit: 返回的最大任务数
            offset: 偏移量
            
        Returns:
            任务列表
        """
        stmt = select(AsyncTask)
        
        if status is not None:
            stmt = stmt.where(AsyncTask.status == status)
        
        if task_type is not None:
            stmt = stmt.where(AsyncTask.task_type == task_type)
        
        stmt = stmt.order_by(AsyncTask.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_task_statistics(self) -> dict:
        """
        获取任务统计信息（管理员用）
        
        Returns:
            包含各种统计数据的字典
        """
        from sqlalchemy import func
        
        # 统计各状态的任务数
        total_stmt = select(func.count(AsyncTask.id))
        total_result = await self.session.execute(total_stmt)
        total_tasks = total_result.scalar() or 0
        
        pending_count = await self.count_tasks_by_status("pending")
        processing_count = await self.count_tasks_by_status("processing")
        completed_count = await self.count_tasks_by_status("completed")
        failed_count = await self.count_tasks_by_status("failed")
        
        # 统计各类型的任务数
        type_stmt = select(
            AsyncTask.task_type,
            func.count(AsyncTask.id)
        ).group_by(AsyncTask.task_type)
        type_result = await self.session.execute(type_stmt)
        tasks_by_type = {row[0]: row[1] for row in type_result.all()}
        
        return {
            "total_tasks": total_tasks,
            "pending_tasks": pending_count,
            "processing_tasks": processing_count,
            "completed_tasks": completed_count,
            "failed_tasks": failed_count,
            "tasks_by_type": tasks_by_type,
        }
