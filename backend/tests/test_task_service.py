"""Unit tests for TaskService.

Tests the core functionality of task creation, querying, and management.
"""
import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.task_service import TaskService


@pytest.mark.asyncio
async def test_create_task(db_session: AsyncSession, test_user: User):
    """Test creating a new task."""
    service = TaskService(db_session)
    
    task = await service.create_task(
        user_id=test_user.id,
        task_type="concept_converse",
        input_data={"message": "test"},
        max_retries=3,
    )
    
    assert task.id is not None
    assert task.user_id == test_user.id
    assert task.task_type == "concept_converse"
    assert task.status == "pending"
    assert task.progress == 0
    assert task.input_data == {"message": "test"}
    assert task.max_retries == 3
    assert task.retry_count == 0


@pytest.mark.asyncio
async def test_get_task_success(db_session: AsyncSession, test_user: User):
    """Test getting a task that exists and belongs to the user."""
    service = TaskService(db_session)
    
    # Create a task
    created_task = await service.create_task(
        user_id=test_user.id,
        task_type="blueprint_generate",
        input_data={"project_id": "123"},
    )
    await db_session.commit()
    
    # Get the task
    retrieved_task = await service.get_task(created_task.id, test_user.id)
    
    assert retrieved_task.id == created_task.id
    assert retrieved_task.user_id == test_user.id


@pytest.mark.asyncio
async def test_get_task_not_found(db_session: AsyncSession, test_user: User):
    """Test getting a task that doesn't exist returns 404."""
    service = TaskService(db_session)
    
    with pytest.raises(HTTPException) as exc_info:
        await service.get_task("nonexistent-id", test_user.id)
    
    assert exc_info.value.status_code == 404
    assert "任务不存在" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_task_forbidden(db_session: AsyncSession, test_user: User):
    """Test getting a task that belongs to another user returns 403."""
    service = TaskService(db_session)
    
    # Create a task for test_user
    task = await service.create_task(
        user_id=test_user.id,
        task_type="chapter_generate",
        input_data={"chapter_id": "456"},
    )
    await db_session.commit()
    
    # Try to access with a different user_id
    with pytest.raises(HTTPException) as exc_info:
        await service.get_task(task.id, test_user.id + 999)
    
    assert exc_info.value.status_code == 403
    assert "无权访问" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_task_status(db_session: AsyncSession, test_user: User):
    """Test updating task status and progress."""
    service = TaskService(db_session)
    
    # Create a task
    task = await service.create_task(
        user_id=test_user.id,
        task_type="chapter_evaluate",
        input_data={"chapter_id": "789"},
    )
    await db_session.commit()
    
    # Update to processing
    await service.update_task_status(
        task_id=task.id,
        status="processing",
        progress=50,
        progress_message="正在处理...",
    )
    await db_session.commit()
    
    # Verify updates
    updated_task = await service.get_task(task.id, test_user.id)
    assert updated_task.status == "processing"
    assert updated_task.progress == 50
    assert updated_task.progress_message == "正在处理..."
    assert updated_task.started_at is not None
    
    # Update to completed
    await service.update_task_status(
        task_id=task.id,
        status="completed",
        progress=100,
        result_data={"result": "success"},
    )
    await db_session.commit()
    
    # Verify completion
    completed_task = await service.get_task(task.id, test_user.id)
    assert completed_task.status == "completed"
    assert completed_task.progress == 100
    assert completed_task.result_data == {"result": "success"}
    assert completed_task.completed_at is not None


@pytest.mark.asyncio
async def test_get_pending_tasks(db_session: AsyncSession, test_user: User):
    """Test getting pending tasks."""
    service = TaskService(db_session)
    
    # Create multiple tasks with different statuses
    await service.create_task(
        user_id=test_user.id,
        task_type="concept_converse",
        input_data={"msg": "1"},
    )
    await service.create_task(
        user_id=test_user.id,
        task_type="blueprint_generate",
        input_data={"msg": "2"},
    )
    
    task3 = await service.create_task(
        user_id=test_user.id,
        task_type="chapter_generate",
        input_data={"msg": "3"},
    )
    await db_session.commit()
    
    # Update one task to processing
    await service.update_task_status(task3.id, "processing")
    await db_session.commit()
    
    # Get pending tasks
    pending_tasks = await service.get_pending_tasks(limit=10)
    
    assert len(pending_tasks) == 2
    assert all(task.status == "pending" for task in pending_tasks)


@pytest.mark.asyncio
async def test_list_user_tasks(db_session: AsyncSession, test_user: User):
    """Test listing user tasks with optional status filter."""
    service = TaskService(db_session)
    
    # Create tasks
    task1 = await service.create_task(
        user_id=test_user.id,
        task_type="concept_converse",
        input_data={"msg": "1"},
    )
    task2 = await service.create_task(
        user_id=test_user.id,
        task_type="blueprint_generate",
        input_data={"msg": "2"},
    )
    await db_session.commit()
    
    # Update one to completed
    await service.update_task_status(task1.id, "completed")
    await db_session.commit()
    
    # List all user tasks
    all_tasks = await service.list_user_tasks(test_user.id)
    assert len(all_tasks) == 2
    
    # List only completed tasks
    completed_tasks = await service.list_user_tasks(test_user.id, status="completed")
    assert len(completed_tasks) == 1
    assert completed_tasks[0].id == task1.id
    
    # List only pending tasks
    pending_tasks = await service.list_user_tasks(test_user.id, status="pending")
    assert len(pending_tasks) == 1
    assert pending_tasks[0].id == task2.id


@pytest.mark.asyncio
async def test_cleanup_expired_tasks(db_session: AsyncSession, test_user: User):
    """Test cleaning up expired tasks."""
    service = TaskService(db_session)
    
    # Create a task
    task = await service.create_task(
        user_id=test_user.id,
        task_type="outline_generate",
        input_data={"msg": "test"},
    )
    await db_session.commit()
    
    # Manually set expires_at to the past
    task.expires_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()
    
    # Clean up expired tasks
    deleted_count = await service.cleanup_expired_tasks()
    await db_session.commit()
    
    assert deleted_count == 1
    
    # Verify task is deleted
    with pytest.raises(HTTPException) as exc_info:
        await service.get_task(task.id, test_user.id)
    assert exc_info.value.status_code == 404
