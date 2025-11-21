"""FastAPI 应用入口，负责装配路由、依赖与生命周期管理。"""

import logging
from logging.config import dictConfig
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db.init_db import init_db
from .services.prompt_service import PromptService
from .db.session import AsyncSessionLocal
from .api.routers import api_router
from .mcp.registry import MCPPluginRegistry
from .mcp.config import MCPConfig


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时初始化数据库，并预热提示词缓存
    logger.info("正在初始化应用...")
    await init_db()
    async with AsyncSessionLocal() as session:
        prompt_service = PromptService(session)
        await prompt_service.preload()
    
    # 初始化 MCP 插件注册表
    logger.info("正在初始化 MCP 插件注册表...")
    mcp_registry = MCPPluginRegistry(
        max_clients=MCPConfig.MAX_CLIENTS,
        client_ttl=MCPConfig.CLIENT_TTL_SECONDS
    )
    app.state.mcp_registry = mcp_registry
    
    # 启动清理任务
    await mcp_registry.start_cleanup_task()
    logger.info("MCP 插件注册表已初始化并启动清理任务")
    
    yield
    
    # 应用关闭时清理资源
    logger.info("正在关闭应用...")
    await mcp_registry.shutdown()
    logger.info("应用已关闭")


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
