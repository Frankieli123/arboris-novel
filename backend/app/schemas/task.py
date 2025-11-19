"""任务相关的Pydantic schemas"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    """任务创建响应"""
    
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    """任务状态查询响应"""
    
    task_id: str = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态: pending, processing, completed, failed")
    progress: int = Field(..., description="进度百分比(0-100)")
    progress_message: Optional[str] = Field(None, description="进度描述")
    result_data: Optional[Dict[str, Any]] = Field(None, description="任务结果数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    
    class Config:
        from_attributes = True


class TaskSummary(BaseModel):
    """任务摘要"""
    
    task_id: str = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="进度百分比")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


# 各个任务类型的输入schema

class ConceptConverseTaskInput(BaseModel):
    """概念对话任务输入"""
    
    project_id: str = Field(..., description="项目ID")
    user_input: Dict[str, Any] = Field(..., description="用户输入")
    conversation_state: Dict[str, Any] = Field(default_factory=dict, description="对话状态")


class BlueprintGenerateTaskInput(BaseModel):
    """蓝图生成任务输入"""
    
    project_id: str = Field(..., description="项目ID")


class ChapterGenerateTaskInput(BaseModel):
    """章节生成任务输入"""
    
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节号")
    writing_notes: Optional[str] = Field(None, description="写作备注")


class ChapterEvaluateTaskInput(BaseModel):
    """章节评估任务输入"""
    
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节号")


class OutlineGenerateTaskInput(BaseModel):
    """大纲生成任务输入"""
    
    project_id: str = Field(..., description="项目ID")
    start_chapter: int = Field(..., description="起始章节号")
    num_chapters: int = Field(..., description="章节数量")


class TaskHealthResponse(BaseModel):
    """任务健康检查响应"""
    
    worker_running: bool = Field(..., description="Worker是否正在运行")
    max_workers: int = Field(..., description="最大并发任务数")
    processing_count: int = Field(..., description="当前处理中的任务数")
    pending_count: int = Field(..., description="待处理任务数")
    
    class Config:
        from_attributes = True


class AdminTaskSummary(BaseModel):
    """管理员任务摘要（包含用户信息）"""
    
    id: str = Field(..., description="任务ID", alias="task_id")
    user_id: int = Field(..., description="用户ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="进度百分比")
    created_at: datetime = Field(..., description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    class Config:
        from_attributes = True
        populate_by_name = True


class TaskStatistics(BaseModel):
    """任务统计信息"""
    
    total_tasks: int = Field(..., description="总任务数")
    pending_tasks: int = Field(..., description="待处理任务数")
    processing_tasks: int = Field(..., description="处理中任务数")
    completed_tasks: int = Field(..., description="已完成任务数")
    failed_tasks: int = Field(..., description="失败任务数")
    tasks_by_type: Dict[str, int] = Field(..., description="按类型分组的任务数")
    avg_execution_time_seconds: float = Field(..., description="平均执行时间（秒）")
    success_rate_percent: float = Field(..., description="成功率（百分比）")
    avg_waiting_time_seconds: float = Field(..., description="平均等待时间（秒）")
