from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class AsyncTask(Base):
    """异步任务表，用于管理长时间运行的后台任务。"""

    __tablename__ = "async_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow() + timedelta(days=7)
    )

    # 关系映射
    user: Mapped["User"] = relationship("User", back_populates="async_tasks")

    # 索引定义
    __table_args__ = (
        Index("idx_async_tasks_user_status", "user_id", "status"),
        Index("idx_async_tasks_status_created", "status", "created_at"),
        Index("idx_async_tasks_expires", "expires_at"),
    )
