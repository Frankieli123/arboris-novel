"""测试管理员任务监控端点"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.async_task import AsyncTask
from app.models.user import User
from app.services.task_service import TaskService


@pytest.mark.asyncio
async def test_admin_task_stats_endpoint(async_client, admin_token, test_session: AsyncSession):
    """测试管理员任务统计端点"""
    # 创建一些测试任务
    task_service = TaskService(test_session)
    
    # 创建不同状态的任务
    await task_service.create_task(
        user_id=1,
        task_type="concept_converse",
        input_data={"test": "data"},
    )
    
    task2 = await task_service.create_task(
        user_id=1,
        task_type="blueprint_generate",
        input_data={"test": "data"},
    )
    await task_service.update_task_status(task2.id, "completed", progress=100)
    
    task3 = await task_service.create_task(
        user_id=1,
        task_type="chapter_generate",
        input_data={"test": "data"},
    )
    await task_service.update_task_status(task3.id, "failed", error_message="测试错误")
    
    await test_session.commit()
    
    # 调用统计端点
    response = await async_client.get(
        "/api/admin/tasks/stats",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # 验证统计数据
    assert "total_tasks" in data
    assert "pending_tasks" in data
    assert "processing_tasks" in data
    assert "completed_tasks" in data
    assert "failed_tasks" in data
    assert "tasks_by_type" in data
    assert "avg_execution_time_seconds" in data
    assert "success_rate_percent" in data
    assert "avg_waiting_time_seconds" in data
    
    assert data["total_tasks"] >= 3
    assert data["pending_tasks"] >= 1
    assert data["completed_tasks"] >= 1
    assert data["failed_tasks"] >= 1


@pytest.mark.asyncio
async def test_admin_list_all_tasks_endpoint(async_client, admin_token, test_session: AsyncSession):
    """测试管理员任务列表端点"""
    # 创建一些测试任务
    task_service = TaskService(test_session)
    
    task1 = await task_service.create_task(
        user_id=1,
        task_type="concept_converse",
        input_data={"test": "data1"},
    )
    
    task2 = await task_service.create_task(
        user_id=1,
        task_type="blueprint_generate",
        input_data={"test": "data2"},
    )
    
    await test_session.commit()
    
    # 调用列表端点
    response = await async_client.get(
        "/api/admin/tasks",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # 验证返回的是列表
    assert isinstance(data, list)
    assert len(data) >= 2
    
    # 验证任务数据结构
    for task in data:
        assert "task_id" in task
        assert "user_id" in task
        assert "task_type" in task
        assert "status" in task
        assert "progress" in task
        assert "created_at" in task


@pytest.mark.asyncio
async def test_admin_list_tasks_with_filters(async_client, admin_token, test_session: AsyncSession):
    """测试管理员任务列表端点的过滤功能"""
    # 创建不同类型和状态的任务
    task_service = TaskService(test_session)
    
    # 创建pending状态的concept_converse任务
    await task_service.create_task(
        user_id=1,
        task_type="concept_converse",
        input_data={"test": "data1"},
    )
    
    # 创建completed状态的blueprint_generate任务
    task2 = await task_service.create_task(
        user_id=1,
        task_type="blueprint_generate",
        input_data={"test": "data2"},
    )
    await task_service.update_task_status(task2.id, "completed", progress=100)
    
    await test_session.commit()
    
    # 测试按状态过滤
    response = await async_client.get(
        "/api/admin/tasks?status=pending",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert all(task["status"] == "pending" for task in data)
    
    # 测试按任务类型过滤
    response = await async_client.get(
        "/api/admin/tasks?task_type=blueprint_generate",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert all(task["task_type"] == "blueprint_generate" for task in data)


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin_permission(async_client, test_session: AsyncSession):
    """测试管理员端点需要管理员权限"""
    from app.core.security import create_access_token
    
    # Create a non-admin user in the test database
    non_admin_user = User(
        username="regularuser",
        email="regular@example.com",
        hashed_password="hashed_password_here",
        is_active=True,
        is_admin=False,
    )
    test_session.add(non_admin_user)
    await test_session.commit()
    await test_session.refresh(non_admin_user)
    
    # Create token for non-admin user
    user_token = create_access_token(
        subject=non_admin_user.username,
        extra_claims={"is_admin": non_admin_user.is_admin}
    )
    
    # 使用普通用户token访问管理员端点
    response = await async_client.get(
        "/api/admin/tasks/stats",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 403
    
    response = await async_client.get(
        "/api/admin/tasks",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    
    assert response.status_code == 403
