from pydantic import BaseModel, Field


class UserGeneralSettings(BaseModel):
    """用户首页“常规设置”。仅对当前用户生效。"""

    auto_expand_enabled: bool = Field(
        False,
        description="生成蓝图后是否自动拆分章节",
    )
    auto_expand_target_chapter_count: int = Field(
        3,
        ge=1,
        le=10,
        description="自动拆分每条大纲的章节数",
    )
    chapter_version_count: int = Field(
        3,
        ge=1,
        le=5,
        description="每次生成章节的候选版本数量",
    )
