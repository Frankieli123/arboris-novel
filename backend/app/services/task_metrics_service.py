"""任务性能指标服务，负责记录和查询任务执行的性能数据。"""

from datetime import datetime, timedelta
from typing import Dict, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.async_task import AsyncTask


class TaskMetricsService:
    """任务性能指标服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_task_execution_metrics(
        self,
        task_type: Optional[str] = None,
        time_window_hours: int = 24
    ) -> Dict:
        """
        获取任务执行时间指标
        
        Args:
            task_type: 可选的任务类型过滤
            time_window_hours: 时间窗口（小时）
            
        Returns:
            包含执行时间统计的字典
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # 构建查询：只统计已完成或失败的任务
        stmt = select(
            func.count(AsyncTask.id).label('total_count'),
            func.avg(
                func.timestampdiff(
                    'SECOND',
                    AsyncTask.started_at,
                    AsyncTask.completed_at
                )
            ).label('avg_execution_time'),
            func.min(
                func.timestampdiff(
                    'SECOND',
                    AsyncTask.started_at,
                    AsyncTask.completed_at
                )
            ).label('min_execution_time'),
            func.max(
                func.timestampdiff(
                    'SECOND',
                    AsyncTask.started_at,
                    AsyncTask.completed_at
                )
            ).label('max_execution_time')
        ).where(
            AsyncTask.completed_at.isnot(None),
            AsyncTask.started_at.isnot(None),
            AsyncTask.created_at >= cutoff_time,
            AsyncTask.status.in_(['completed', 'failed'])
        )
        
        if task_type:
            stmt = stmt.where(AsyncTask.task_type == task_type)
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if not row or row.total_count == 0:
            return {
                'total_count': 0,
                'avg_execution_time_seconds': 0,
                'min_execution_time_seconds': 0,
                'max_execution_time_seconds': 0,
                'time_window_hours': time_window_hours,
                'task_type': task_type
            }
        
        return {
            'total_count': row.total_count,
            'avg_execution_time_seconds': float(row.avg_execution_time) if row.avg_execution_time else 0,
            'min_execution_time_seconds': float(row.min_execution_time) if row.min_execution_time else 0,
            'max_execution_time_seconds': float(row.max_execution_time) if row.max_execution_time else 0,
            'time_window_hours': time_window_hours,
            'task_type': task_type
        }

    async def get_task_success_rate(
        self,
        task_type: Optional[str] = None,
        time_window_hours: int = 24
    ) -> Dict:
        """
        获取任务成功率指标
        
        Args:
            task_type: 可选的任务类型过滤
            time_window_hours: 时间窗口（小时）
            
        Returns:
            包含成功率统计的字典
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # 统计总任务数
        total_stmt = select(func.count(AsyncTask.id)).where(
            AsyncTask.created_at >= cutoff_time,
            AsyncTask.status.in_(['completed', 'failed'])
        )
        
        if task_type:
            total_stmt = total_stmt.where(AsyncTask.task_type == task_type)
        
        total_result = await self.session.execute(total_stmt)
        total_count = total_result.scalar() or 0
        
        # 统计成功任务数
        success_stmt = select(func.count(AsyncTask.id)).where(
            AsyncTask.created_at >= cutoff_time,
            AsyncTask.status == 'completed'
        )
        
        if task_type:
            success_stmt = success_stmt.where(AsyncTask.task_type == task_type)
        
        success_result = await self.session.execute(success_stmt)
        success_count = success_result.scalar() or 0
        
        # 统计失败任务数
        failed_count = total_count - success_count
        
        # 计算成功率
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        return {
            'total_count': total_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate_percent': round(success_rate, 2),
            'time_window_hours': time_window_hours,
            'task_type': task_type
        }

    async def get_task_waiting_time_metrics(
        self,
        task_type: Optional[str] = None,
        time_window_hours: int = 24
    ) -> Dict:
        """
        获取任务等待时间指标（从创建到开始执行的时间）
        
        Args:
            task_type: 可选的任务类型过滤
            time_window_hours: 时间窗口（小时）
            
        Returns:
            包含等待时间统计的字典
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # 构建查询：只统计已开始执行的任务
        stmt = select(
            func.count(AsyncTask.id).label('total_count'),
            func.avg(
                func.timestampdiff(
                    'SECOND',
                    AsyncTask.created_at,
                    AsyncTask.started_at
                )
            ).label('avg_waiting_time'),
            func.min(
                func.timestampdiff(
                    'SECOND',
                    AsyncTask.created_at,
                    AsyncTask.started_at
                )
            ).label('min_waiting_time'),
            func.max(
                func.timestampdiff(
                    'SECOND',
                    AsyncTask.created_at,
                    AsyncTask.started_at
                )
            ).label('max_waiting_time')
        ).where(
            AsyncTask.started_at.isnot(None),
            AsyncTask.created_at >= cutoff_time
        )
        
        if task_type:
            stmt = stmt.where(AsyncTask.task_type == task_type)
        
        result = await self.session.execute(stmt)
        row = result.first()
        
        if not row or row.total_count == 0:
            return {
                'total_count': 0,
                'avg_waiting_time_seconds': 0,
                'min_waiting_time_seconds': 0,
                'max_waiting_time_seconds': 0,
                'time_window_hours': time_window_hours,
                'task_type': task_type
            }
        
        return {
            'total_count': row.total_count,
            'avg_waiting_time_seconds': float(row.avg_waiting_time) if row.avg_waiting_time else 0,
            'min_waiting_time_seconds': float(row.min_waiting_time) if row.min_waiting_time else 0,
            'max_waiting_time_seconds': float(row.max_waiting_time) if row.max_waiting_time else 0,
            'time_window_hours': time_window_hours,
            'task_type': task_type
        }

    async def get_comprehensive_metrics(
        self,
        task_type: Optional[str] = None,
        time_window_hours: int = 24
    ) -> Dict:
        """
        获取综合性能指标
        
        Args:
            task_type: 可选的任务类型过滤
            time_window_hours: 时间窗口（小时）
            
        Returns:
            包含所有性能指标的字典
        """
        execution_metrics = await self.get_task_execution_metrics(task_type, time_window_hours)
        success_metrics = await self.get_task_success_rate(task_type, time_window_hours)
        waiting_metrics = await self.get_task_waiting_time_metrics(task_type, time_window_hours)
        
        return {
            'execution_time': execution_metrics,
            'success_rate': success_metrics,
            'waiting_time': waiting_metrics,
            'time_window_hours': time_window_hours,
            'task_type': task_type
        }

    async def get_metrics_by_task_type(
        self,
        time_window_hours: int = 24
    ) -> Dict:
        """
        获取按任务类型分组的性能指标
        
        Args:
            time_window_hours: 时间窗口（小时）
            
        Returns:
            按任务类型分组的性能指标字典
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # 获取所有任务类型
        stmt = select(AsyncTask.task_type).where(
            AsyncTask.created_at >= cutoff_time
        ).distinct()
        
        result = await self.session.execute(stmt)
        task_types = [row[0] for row in result.all()]
        
        # 为每个任务类型获取指标
        metrics_by_type = {}
        for task_type in task_types:
            metrics_by_type[task_type] = await self.get_comprehensive_metrics(
                task_type=task_type,
                time_window_hours=time_window_hours
            )
        
        return {
            'metrics_by_type': metrics_by_type,
            'time_window_hours': time_window_hours
        }
