# -*- coding: utf-8 -*-
"""Test task metrics service"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.async_task import AsyncTask
from app.services.task_metrics_service import TaskMetricsService


@pytest.mark.asyncio
async def test_get_task_execution_metrics_empty(db_session: AsyncSession):
    """Test execution metrics with empty database"""
    metrics_service = TaskMetricsService(db_session)
    
    metrics = await metrics_service.get_task_execution_metrics()
    
    assert metrics['total_count'] == 0
    assert metrics['avg_execution_time_seconds'] == 0


@pytest.mark.asyncio
async def test_get_task_success_rate_empty(db_session: AsyncSession):
    """Test success rate with empty database"""
    metrics_service = TaskMetricsService(db_session)
    
    metrics = await metrics_service.get_task_success_rate()
    
    assert metrics['total_count'] == 0
    assert metrics['success_count'] == 0
    assert metrics['success_rate_percent'] == 0


@pytest.mark.asyncio
async def test_get_comprehensive_metrics(db_session: AsyncSession):
    """Test comprehensive metrics"""
    now = datetime.utcnow()
    
    task = AsyncTask(
        id="test-1",
        user_id=1,
        task_type="test_task",
        status="completed",
        input_data={},
        created_at=now - timedelta(minutes=5),
        started_at=now - timedelta(minutes=4),
        completed_at=now - timedelta(minutes=3)
    )
    db_session.add(task)
    await db_session.commit()
    
    metrics_service = TaskMetricsService(db_session)
    metrics = await metrics_service.get_comprehensive_metrics()
    
    assert 'execution_time' in metrics
    assert 'success_rate' in metrics
    assert 'waiting_time' in metrics
