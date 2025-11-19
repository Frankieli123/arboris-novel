"""任务管理API路由"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.task import (
    BlueprintGenerateTaskInput,
    ChapterEvaluateTaskInput,
    ChapterGenerateTaskInput,
    ConceptConverseTaskInput,
    OutlineGenerateTaskInput,
    TaskHealthResponse,
    TaskResponse,
    TaskStatusResponse,
    TaskSummary,
)
from ...schemas.user import UserInDB
from ...services.task_service import TaskService
from ...services.task_metrics_service import TaskMetricsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.post("/concept-converse", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_concept_converse_task(
    request: ConceptConverseTaskInput,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> TaskResponse:
    """创建概念对话任务"""
    task_service = TaskService(session)
    
    input_data = {
        "project_id": request.project_id,
        "user_input": request.user_input,
        "conversation_state": request.conversation_state,
    }
    
    task = await task_service.create_task(
        user_id=current_user.id,
        task_type="concept_converse",
        input_data=input_data,
        max_retries=2,
    )
    await session.commit()
    
    logger.info(
        "用户 %s 创建概念对话任务 %s，项目 %s",
        current_user.id,
        task.id,
        request.project_id,
    )
    
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        created_at=task.created_at,
    )


@router.post("/blueprint-generate", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_blueprint_generate_task(
    request: BlueprintGenerateTaskInput,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> TaskResponse:
    """创建蓝图生成任务"""
    task_service = TaskService(session)
    
    input_data = {
        "project_id": request.project_id,
    }
    
    task = await task_service.create_task(
        user_id=current_user.id,
        task_type="blueprint_generate",
        input_data=input_data,
        max_retries=2,
    )
    await session.commit()
    
    logger.info(
        "用户 %s 创建蓝图生成任务 %s，项目 %s",
        current_user.id,
        task.id,
        request.project_id,
    )
    
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        created_at=task.created_at,
    )


@router.post("/chapter-generate", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter_generate_task(
    request: ChapterGenerateTaskInput,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> TaskResponse:
    """创建章节生成任务"""
    task_service = TaskService(session)
    
    input_data = {
        "project_id": request.project_id,
        "chapter_number": request.chapter_number,
        "writing_notes": request.writing_notes,
    }
    
    task = await task_service.create_task(
        user_id=current_user.id,
        task_type="chapter_generate",
        input_data=input_data,
        max_retries=1,
    )
    await session.commit()
    
    logger.info(
        "用户 %s 创建章节生成任务 %s，项目 %s 第 %s 章",
        current_user.id,
        task.id,
        request.project_id,
        request.chapter_number,
    )
    
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        created_at=task.created_at,
    )


@router.post("/chapter-evaluate", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_chapter_evaluate_task(
    request: ChapterEvaluateTaskInput,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> TaskResponse:
    """创建章节评估任务"""
    task_service = TaskService(session)
    
    input_data = {
        "project_id": request.project_id,
        "chapter_number": request.chapter_number,
    }
    
    task = await task_service.create_task(
        user_id=current_user.id,
        task_type="chapter_evaluate",
        input_data=input_data,
        max_retries=2,
    )
    await session.commit()
    
    logger.info(
        "用户 %s 创建章节评估任务 %s，项目 %s 第 %s 章",
        current_user.id,
        task.id,
        request.project_id,
        request.chapter_number,
    )
    
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        created_at=task.created_at,
    )


@router.post("/outline-generate", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_outline_generate_task(
    request: OutlineGenerateTaskInput,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> TaskResponse:
    """创建大纲生成任务"""
    task_service = TaskService(session)
    
    input_data = {
        "project_id": request.project_id,
        "start_chapter": request.start_chapter,
        "num_chapters": request.num_chapters,
    }
    
    task = await task_service.create_task(
        user_id=current_user.id,
        task_type="outline_generate",
        input_data=input_data,
        max_retries=2,
    )
    await session.commit()
    
    logger.info(
        "用户 %s 创建大纲生成任务 %s，项目 %s，起始章节 %s，数量 %s",
        current_user.id,
        task.id,
        request.project_id,
        request.start_chapter,
        request.num_chapters,
    )
    
    return TaskResponse(
        task_id=task.id,
        status=task.status,
        created_at=task.created_at,
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> TaskStatusResponse:
    """查询任务状态"""
    task_service = TaskService(session)
    
    task = await task_service.get_task(task_id, current_user.id)
    
    return TaskStatusResponse(
        task_id=task.id,
        task_type=task.task_type,
        status=task.status,
        progress=task.progress,
        progress_message=task.progress_message,
        result_data=task.result_data,
        error_message=task.error_message,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


@router.get("", response_model=List[TaskSummary])
async def list_user_tasks(
    status: Optional[str] = Query(None, description="按状态过滤"),
    limit: int = Query(50, ge=1, le=100, description="返回的最大任务数"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[TaskSummary]:
    """查询用户任务列表"""
    task_service = TaskService(session)
    
    tasks = await task_service.list_user_tasks(
        user_id=current_user.id,
        status=status,
        limit=limit,
    )
    
    return [
        TaskSummary(
            task_id=task.id,
            task_type=task.task_type,
            status=task.status,
            progress=task.progress,
            created_at=task.created_at,
        )
        for task in tasks
    ]


@router.get("/metrics/comprehensive", response_model=dict)
async def get_comprehensive_metrics(
    task_type: Optional[str] = Query(None, description="任务类型过滤"),
    time_window_hours: int = Query(24, ge=1, le=168, description="时间窗口（小时）"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """
    获取综合性能指标
    
    包括：
    - 任务执行时间（平均、最小、最大）
    - 任务成功率
    - 任务等待时间（平均、最小、最大）
    """
    metrics_service = TaskMetricsService(session)
    
    metrics = await metrics_service.get_comprehensive_metrics(
        task_type=task_type,
        time_window_hours=time_window_hours
    )
    
    logger.info(
        "用户 %s 查询性能指标，任务类型: %s，时间窗口: %s小时",
        current_user.id,
        task_type or "全部",
        time_window_hours
    )
    
    return metrics


@router.get("/metrics/by-type", response_model=dict)
async def get_metrics_by_type(
    time_window_hours: int = Query(24, ge=1, le=168, description="时间窗口（小时）"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """
    获取按任务类型分组的性能指标
    
    返回每种任务类型的执行时间、成功率和等待时间统计
    """
    metrics_service = TaskMetricsService(session)
    
    metrics = await metrics_service.get_metrics_by_task_type(
        time_window_hours=time_window_hours
    )
    
    logger.info(
        "用户 %s 查询按类型分组的性能指标，时间窗口: %s小时",
        current_user.id,
        time_window_hours
    )
    
    return metrics



