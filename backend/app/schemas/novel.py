from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChoiceOption(BaseModel):
    """前端选择项描述，用于动态 UI 控件。"""

    id: str
    label: str


class UIControl(BaseModel):
    """描述前端应渲染的组件类型与配置。"""

    type: str = Field(..., description="控件类型，如 single_choice/text_input")
    options: Optional[List[ChoiceOption]] = Field(default=None, description="可选项列表")
    placeholder: Optional[str] = Field(default=None, description="输入提示文案")


class ConverseResponse(BaseModel):
    """概念对话接口的统一返回体。"""

    ai_message: str
    ui_control: UIControl
    conversation_state: Dict[str, Any]
    is_complete: bool = False
    ready_for_blueprint: Optional[bool] = None


class ConverseRequest(BaseModel):
    """概念对话接口的请求体。"""

    user_input: Dict[str, Any]
    conversation_state: Dict[str, Any]


class ChapterGenerationStatus(str, Enum):
    NOT_GENERATED = "not_generated"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    SELECTING = "selecting"
    FAILED = "failed"
    EVALUATION_FAILED = "evaluation_failed"
    WAITING_FOR_CONFIRM = "waiting_for_confirm"
    SUCCESSFUL = "successful"


class ChapterOutline(BaseModel):
    chapter_number: int
    title: str
    summary: str


class Chapter(ChapterOutline):
    real_summary: Optional[str] = None
    content: Optional[str] = None
    versions: Optional[List[str]] = None
    evaluation: Optional[str] = None
    generation_status: ChapterGenerationStatus = ChapterGenerationStatus.NOT_GENERATED


class Relationship(BaseModel):
    character_from: str
    character_to: str
    description: str


class Blueprint(BaseModel):
    title: str
    target_audience: str = ""
    genre: str = ""
    style: str = ""
    tone: str = ""
    one_sentence_summary: str = ""
    full_synopsis: str = ""
    world_setting: Dict[str, Any] = {}
    characters: List[Dict[str, Any]] = []
    relationships: List[Relationship] = []
    chapter_outline: List[ChapterOutline] = []


class NovelProject(BaseModel):
    id: str
    user_id: int
    title: str
    initial_prompt: str
    conversation_history: List[Dict[str, Any]] = []
    blueprint: Optional[Blueprint] = None
    chapters: List[Chapter] = []

    class Config:
        from_attributes = True


class NovelProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    last_edited: str
    completed_chapters: int
    total_chapters: int


class BlueprintGenerationResponse(BaseModel):
    blueprint: Blueprint
    ai_message: str


class ChapterGenerationResponse(BaseModel):
    ai_message: str
    chapter_versions: List[Dict[str, Any]]


class NovelSectionType(str, Enum):
    OVERVIEW = "overview"
    WORLD_SETTING = "world_setting"
    CHARACTERS = "characters"
    RELATIONSHIPS = "relationships"
    CHAPTER_OUTLINE = "chapter_outline"
    CHAPTERS = "chapters"


class NovelSectionResponse(BaseModel):
    section: NovelSectionType
    data: Dict[str, Any]


class GenerateChapterRequest(BaseModel):
    chapter_number: int
    writing_notes: Optional[str] = Field(default=None, description="章节额外写作指令")


class SelectVersionRequest(BaseModel):
    chapter_number: int
    version_index: int


class EvaluateChapterRequest(BaseModel):
    chapter_number: int


class UpdateChapterOutlineRequest(BaseModel):
    chapter_number: int
    title: str
    summary: str


class DeleteChapterRequest(BaseModel):
    chapter_numbers: List[int]


class GenerateOutlineRequest(BaseModel):
    start_chapter: int
    num_chapters: int
    # 生成模式：auto(自动判断，有大纲则续写，暂无则新建) / new(全新生成，从第1章开始覆盖) / continue(在现有大纲后续写)
    mode: str = Field("auto", description="生成模式: auto(自动判断), new(全新生成), continue(续写)")
    # 故事发展方向提示（续写模式下可选）
    story_direction: Optional[str] = Field(
        default=None,
        description="故事发展方向提示，用于指导续写时的情节走向",
    )
    # 情节阶段：development(发展)、climax(高潮)、ending(结局)
    plot_stage: str = Field(
        default="development",
        description="情节阶段: development(发展), climax(高潮), ending(结局)",
    )
    # 是否在续写时保留现有的大纲结构（预留字段，当前实现中仅作为提示信息透传给提示词）
    keep_existing: bool = Field(
        default=True,
        description="是否保留现有大纲，仅在部分模式下作为提示信息使用",
    )


class BlueprintPatch(BaseModel):
    one_sentence_summary: Optional[str] = None
    full_synopsis: Optional[str] = None
    world_setting: Optional[Dict[str, Any]] = None
    characters: Optional[List[Dict[str, Any]]] = None
    relationships: Optional[List[Relationship]] = None
    chapter_outline: Optional[List[ChapterOutline]] = None


class EditChapterRequest(BaseModel):
    chapter_number: int
    content: str


class NovelGenerateRequest(BaseModel):
    """小说内容生成请求。"""
    
    prompt: str = Field(..., description="生成提示词")
    enable_mcp: bool = Field(default=True, description="是否启用 MCP 工具增强")
    temperature: float = Field(default=0.7, description="温度参数")
    max_length: int = Field(default=2000, description="最大生成长度")


class NovelGenerateResponse(BaseModel):
    """小说内容生成响应。"""
    
    content: str = Field(..., description="生成的内容")
    mcp_enhanced: bool = Field(..., description="是否使用了 MCP 增强")
    tools_used: List[str] = Field(default_factory=list, description="使用的工具列表")
    tool_calls_made: int = Field(..., description="工具调用次数")
