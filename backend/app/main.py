"""FastAPI 应用入口，负责装配路由、依赖与生命周期管理。"""

import logging
from logging.config import dictConfig
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db.init_db import init_db
from .services.prompt_service import PromptService
from .services.task_service import TaskService
from .services.task_worker import TaskWorker
from .db.session import AsyncSessionLocal
from .api.routers import api_router


dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "loggers": {
            "backend": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "app": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.app": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.api": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.services": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"],
        },
    }
)


logger = logging.getLogger(__name__)

# 全局TaskWorker实例
task_worker: TaskWorker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global task_worker
    
    # 应用启动时初始化数据库，并预热提示词缓存
    await init_db()
    async with AsyncSessionLocal() as session:
        prompt_service = PromptService(session)
        await prompt_service.preload()
    
    # 恢复处于processing状态的任务
    logger.info("Recovering processing tasks...")
    async with AsyncSessionLocal() as session:
        task_service = TaskService(session, retention_days=settings.task_retention_days)
        recovered_count = await task_service.recover_processing_tasks()
        await session.commit()
        logger.info(f"Recovered {recovered_count} processing tasks to pending state")
    
    # 启动TaskWorker
    logger.info("Starting TaskWorker...")
    task_worker = TaskWorker(
        max_workers=settings.task_worker_max_workers,
        max_execution_time=settings.task_max_execution_time,
        retention_days=settings.task_retention_days
    )
    await task_worker.start()
    logger.info("TaskWorker started successfully")
    
    yield
    
    # 应用关闭时停止TaskWorker
    if task_worker:
        logger.info("Stopping TaskWorker...")
        await task_worker.stop()
        logger.info("TaskWorker stopped successfully")


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置，生产环境建议改为具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


# 健康检查接口（用于 Docker 健康检查和监控）
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """健康检查接口，返回应用状态。"""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
    }


@app.get("/api/health/tasks", tags=["Health"])
async def task_health_check():
    """
    任务系统健康检查接口
    
    返回worker状态、当前处理中的任务数、待处理任务数和性能指标
    """
    from .db.session import AsyncSessionLocal
    from .services.task_service import TaskService
    from .services.task_metrics_service import TaskMetricsService
    
    async with AsyncSessionLocal() as session:
        task_service = TaskService(session)
        metrics_service = TaskMetricsService(session)
        
        # 获取任务统计
        processing_count = await task_service.count_tasks_by_status("processing")
        pending_count = await task_service.count_tasks_by_status("pending")
        completed_count = await task_service.count_tasks_by_status("completed")
        failed_count = await task_service.count_tasks_by_status("failed")
        
        # 获取性能指标（最近1小时）
        try:
            execution_metrics = await metrics_service.get_task_execution_metrics(time_window_hours=1)
            success_metrics = await metrics_service.get_task_success_rate(time_window_hours=1)
            waiting_metrics = await metrics_service.get_task_waiting_time_metrics(time_window_hours=1)
        except Exception as e:
            # 如果获取指标失败，返回空指标
            execution_metrics = {"avg_execution_time_seconds": 0}
            success_metrics = {"success_rate_percent": 0}
            waiting_metrics = {"avg_waiting_time_seconds": 0}
    
    # 获取worker状态
    worker_running = task_worker.is_running() if task_worker else False
    max_workers = task_worker.get_max_workers() if task_worker else 0
    
    return {
        "worker_running": worker_running,
        "max_workers": max_workers,
        "task_counts": {
            "processing": processing_count,
            "pending": pending_count,
            "completed": completed_count,
            "failed": failed_count,
        },
        "performance_metrics": {
            "avg_execution_time_seconds": execution_metrics.get("avg_execution_time_seconds", 0),
            "success_rate_percent": success_metrics.get("success_rate_percent", 0),
            "avg_waiting_time_seconds": waiting_metrics.get("avg_waiting_time_seconds", 0),
        }
    }
