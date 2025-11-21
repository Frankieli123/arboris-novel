"""MCP 插件相关的数据模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class MCPPlugin(Base):
    """MCP 插件配置表，存储插件的连接信息和认证配置。"""

    __tablename__ = "mcp_plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plugin_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    plugin_type: Mapped[str] = mapped_column(String(50), nullable=False, default="http")
    server_url: Mapped[str] = mapped_column(String(500), nullable=False)
    headers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 存储
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 存储
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 关系映射
    user_preferences: Mapped[list["UserPluginPreference"]] = relationship(
        "UserPluginPreference",
        back_populates="plugin",
        cascade="all, delete-orphan"
    )


class UserPluginPreference(Base):
    """用户插件偏好表，记录每个用户对插件的启用状态。"""

    __tablename__ = "user_plugin_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plugin_id: Mapped[int] = mapped_column(Integer, ForeignKey("mcp_plugins.id", ondelete="CASCADE"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="plugin_preferences")
    plugin: Mapped["MCPPlugin"] = relationship("MCPPlugin", back_populates="user_preferences")

    # 唯一约束
    __table_args__ = (
        UniqueConstraint("user_id", "plugin_id", name="uq_user_plugin"),
    )
