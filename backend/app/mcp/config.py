"""
MCP 系统配置模块。

定义 MCP 插件系统的所有配置常量，包括连接池、缓存、重试、超时等参数。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MCPConfig:
    """MCP 系统配置常量。
    
    使用 frozen dataclass 确保配置不可变。
    """
    
    # 连接池配置
    MAX_CLIENTS: int = 50  # 最大并发客户端连接数
    CLIENT_TTL_SECONDS: int = 3600  # 客户端会话 TTL（1小时）
    CLEANUP_INTERVAL_SECONDS: int = 300  # 清理任务执行间隔（5分钟）
    
    # 工具缓存配置
    TOOL_CACHE_TTL_MINUTES: int = 30  # 工具定义缓存有效期（30分钟）
    
    # 重试配置
    MAX_RETRIES: int = 3  # 最大重试次数
    BASE_RETRY_DELAY_SECONDS: float = 1.0  # 基础重试延迟（指数退避）
    MAX_RETRY_DELAY_SECONDS: float = 10.0  # 最大重试延迟
    
    # 超时配置
    CONNECT_TIMEOUT_SECONDS: float = 30.0  # 连接超时
    TOOL_CALL_TIMEOUT_SECONDS: float = 60.0  # 工具调用超时
    LIST_TOOLS_TIMEOUT_SECONDS: float = 10.0  # 列出工具超时
    
    # 健康检查配置
    ERROR_RATE_THRESHOLD: float = 0.5  # 错误率阈值（50%）
    MIN_CALLS_FOR_HEALTH_CHECK: int = 10  # 健康检查最小调用次数
