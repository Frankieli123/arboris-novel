import json
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user, get_mcp_registry
from ...db.session import get_session
from ...models.novel import Chapter, ChapterOutline
from ...schemas.novel import (
    Blueprint,
    BlueprintGenerationResponse,
    BlueprintPatch,
    Chapter as ChapterSchema,
    ChapterPlanItem,
    ConverseRequest,
    ConverseResponse,
    NovelGenerateRequest,
    NovelGenerateResponse,
    NovelProject as NovelProjectSchema,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
    OrganizationDetail,
)
from ...schemas.user import UserInDB
from ...mcp.registry import MCPPluginRegistry
from ...services.llm_service import LLMService
from ...services.mcp_tool_service import MCPToolService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.admin_setting_service import AdminSettingService
from ...services.user_setting_service import UserSettingService
from ...utils.json_utils import remove_think_tags, sanitize_json_like_text, unwrap_markdown_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels", tags=["Novels"])

JSON_RESPONSE_INSTRUCTION = """
IMPORTANT: 你的回复必须是合法的 JSON 对象，并严格包含以下字段：
{
  "ai_message": "string",
  "ui_control": {
    "type": "single_choice | text_input | info_display",
    "options": [
      {"id": "option_1", "label": "string"}
    ],
    "placeholder": "string"
  },
  "conversation_state": {},
  "is_complete": false
}
不要输出额外的文本或解释。
"""


def _ensure_prompt(prompt: str | None, name: str) -> str:
    if not prompt:
        raise HTTPException(status_code=500, detail=f"未配置名为 {name} 的提示词，请联系管理员")
    return prompt


@router.post("", response_model=NovelProjectSchema, status_code=status.HTTP_201_CREATED)
async def create_novel(
    title: str = Body(...),
    initial_prompt: str = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """为当前用户创建一个新的小说项目。"""
    novel_service = NovelService(session)
    project = await novel_service.create_project(current_user.id, title, initial_prompt)
    logger.info("用户 %s 创建项目 %s", current_user.id, project.id)
    return await novel_service.get_project_schema(project.id, current_user.id)


@router.get("", response_model=List[NovelProjectSummary])
async def list_novels(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[NovelProjectSummary]:
    """列出用户的全部小说项目摘要信息。"""
    novel_service = NovelService(session)
    projects = await novel_service.list_projects_for_user(current_user.id)
    logger.info("用户 %s 获取项目列表，共 %s 个", current_user.id, len(projects))
    return projects


@router.get("/{project_id}", response_model=NovelProjectSchema)
async def get_novel(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 查询项目 %s", current_user.id, project_id)
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.get("/{project_id}/sections/{section}", response_model=NovelSectionResponse)
async def get_novel_section(
    project_id: str,
    section: NovelSectionType,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelSectionResponse:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 的 %s 区段", current_user.id, project_id, section)
    return await novel_service.get_section_data(project_id, current_user.id, section)


@router.get("/{project_id}/organizations", response_model=List[OrganizationDetail])
async def list_organizations(
	project_id: str,
	session: AsyncSession = Depends(get_session),
	current_user: UserInDB = Depends(get_current_user),
) -> List[OrganizationDetail]:
	novel_service = NovelService(session)
	await novel_service.ensure_project_owner(project_id, current_user.id)
	data = await novel_service.list_organizations_with_members(project_id)
	return [OrganizationDetail.model_validate(item) for item in data]


@router.get("/{project_id}/chapters/{chapter_number}", response_model=ChapterSchema)
async def get_chapter(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 第 %s 章", current_user.id, project_id, chapter_number)
    return await novel_service.get_chapter_schema(project_id, current_user.id, chapter_number)


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_novels(
    project_ids: List[str] = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    novel_service = NovelService(session)
    await novel_service.delete_projects(project_ids, current_user.id)
    logger.info("用户 %s 删除项目 %s", current_user.id, project_ids)
    return {"status": "success", "message": f"成功删除 {len(project_ids)} 个项目"}


@router.post("/{project_id}/concept/converse", response_model=ConverseResponse)
async def converse_with_concept(
    project_id: str,
    request: ConverseRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ConverseResponse:
    """与概念设计师（LLM）进行对话，引导蓝图筹备。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    history_records = await novel_service.list_conversations(project_id)
    logger.info(
        "项目 %s 概念对话请求，用户 %s，历史记录 %s 条",
        project_id,
        current_user.id,
        len(history_records),
    )
    conversation_history = [
        {"role": record.role, "content": record.content}
        for record in history_records
    ]
    user_content = json.dumps(request.user_input, ensure_ascii=False)
    conversation_history.append({"role": "user", "content": user_content})

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("concept"), "concept")
    system_prompt = f"{system_prompt}\n{JSON_RESPONSE_INSTRUCTION}"

    llm_response = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        temperature=0.8,
        user_id=current_user.id,
        timeout=240.0,
    )
    llm_response = remove_think_tags(llm_response)

    try:
        normalized = unwrap_markdown_json(llm_response)
        sanitized = sanitize_json_like_text(normalized)
        parsed = json.loads(sanitized)
    except json.JSONDecodeError as exc:
        logger.exception(
            "Failed to parse concept converse response: project_id=%s user_id=%s error=%s\nOriginal response: %s\nNormalized: %s\nSanitized: %s",
            project_id,
            current_user.id,
            exc,
            llm_response[:1000],
            normalized[:1000] if 'normalized' in locals() else "N/A",
            sanitized[:1000] if 'sanitized' in locals() else "N/A",
        )
        raise HTTPException(
            status_code=500,
            detail=f"概念对话失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}"
        ) from exc

    await novel_service.append_conversation(project_id, "user", user_content)
    await novel_service.append_conversation(project_id, "assistant", normalized)

    logger.info("项目 %s 概念对话完成，is_complete=%s", project_id, parsed.get("is_complete"))

    if parsed.get("is_complete"):
        parsed["ready_for_blueprint"] = True

    parsed.setdefault("conversation_state", parsed.get("conversation_state", {}))
    return ConverseResponse(**parsed)


@router.post("/{project_id}/blueprint/world", response_model=BlueprintGenerationResponse)
async def generate_blueprint_world(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
    mcp_registry: MCPPluginRegistry = Depends(get_mcp_registry),
) -> BlueprintGenerationResponse:
    """多步蓝图生成：第一步，仅生成世界观与整体梗概。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)

    # 初始化 MCP 工具服务和支持 MCP 的 LLM 服务
    mcp_tool_service = MCPToolService(session, mcp_registry)
    llm_service = LLMService(session, mcp_tool_service=mcp_tool_service)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("[世界观蓝图][步骤1/4] 开始生成世界观蓝图, project_id=%s", project_id)

    history_records = await novel_service.list_conversations(project_id)
    if not history_records:
        logger.warning("项目 %s 缺少对话历史，无法生成世界观蓝图", project_id)
        raise HTTPException(status_code=400, detail="缺少对话历史，请先完成概念对话后再生成世界观蓝图")

    formatted_history: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content
        if not role or not content:
            continue
        try:
            normalized = unwrap_markdown_json(content)
            data = json.loads(normalized)
            if role == "user":
                user_value = data.get("value", data)
                if isinstance(user_value, str):
                    formatted_history.append({"role": "user", "content": user_value})
            elif role == "assistant":
                ai_message = data.get("ai_message") if isinstance(data, dict) else None
                if ai_message:
                    formatted_history.append({"role": "assistant", "content": ai_message})
        except (json.JSONDecodeError, AttributeError):
            continue

    if not formatted_history:
        logger.warning("项目 %s 对话历史格式异常，无法提取有效内容用于世界观生成", project_id)
        raise HTTPException(
            status_code=400,
            detail="无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话",
        )

    # 使用 MCP 工具进行资料/规划阶段
    logger.info("[世界观蓝图][步骤2/4] 进入 MCP 规划阶段, 准备检索世界观相关资料, project_id=%s", project_id)
    mcp_reference_text = ""
    try:
        planning_messages = [
            {
                "role": "system",
                "content": (
                    "你是一名资深小说策划与世界观设计顾问，可以调用外部 MCP 插件检索资料，"
                    "为后续的世界观与蓝图设计提供真实、系统的参考信息。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "下面是我们之前关于这部小说的概念对话内容，请先通读这些信息，"
                    "在需要时调用可用的工具，检索与题材、时代背景、世界观设定等相关的 1-3 条高价值资料，"
                    "并整理成供世界观设计使用的参考说明，不要直接输出最终 JSON 蓝图。\n\n"
                    + "\n".join(f"[{item['role']}]: {item['content']}" for item in formatted_history)
                ),
            },
        ]
        mcp_reference_text = await llm_service.generate_text_with_mcp(
            messages=planning_messages,
            user_id=current_user.id,
            temperature=0.5,
            timeout=600.0,
        )
        mcp_reference_text = mcp_reference_text or ""
        if mcp_reference_text:
            logger.info(
                "[世界观蓝图] MCP 规划阶段完成, 参考资料长度=%s, project_id=%s",
                len(mcp_reference_text),
                project_id,
            )
        else:
            logger.info("[世界观蓝图] MCP 规划阶段完成但未返回参考资料, project_id=%s", project_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "项目 %s 世界观 MCP 规划阶段失败，将在无 MCP 参考资料的情况下生成世界观: %s",
            project_id,
            exc,
        )
        mcp_reference_text = ""

    # 使用 worldbuilding 提示词，在对话历史基础上（可选地）附加 MCP 参考资料，生成世界观蓝图
    logger.info("[世界观蓝图][步骤3/4] 调用 LLM 生成世界观 JSON 蓝图, project_id=%s", project_id)
    system_prompt = _ensure_prompt(await prompt_service.get_prompt("worldbuilding"), "worldbuilding")

    conversation_for_world = list(formatted_history)
    if mcp_reference_text:
        conversation_for_world.append(
            {
                "role": "assistant",
                "content": (
                    "[MCP 参考资料]\n" + mcp_reference_text
                ),
            }
        )

    world_raw = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=conversation_for_world,
        temperature=0.35,
        user_id=current_user.id,
        timeout=900.0,
    )
    world_raw = remove_think_tags(world_raw)

    world_normalized = unwrap_markdown_json(world_raw)
    world_sanitized = sanitize_json_like_text(world_normalized)
    try:
        world_data = json.loads(world_sanitized)
    except json.JSONDecodeError as exc:  # noqa: BLE001
        logger.error(
            "项目 %s 世界观蓝图生成 JSON 解析失败: %s\n原始响应: %s\n标准化后: %s\n清洗后: %s",
            project_id,
            exc,
            world_raw[:500],
            world_normalized[:500],
            world_sanitized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"世界观蓝图生成失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}",
        ) from exc

    world_blueprint = Blueprint(**world_data)
    logger.info("[世界观蓝图][步骤4/4] 解析成功, 准备写入世界观到项目, project_id=%s", project_id)
    await novel_service.update_world_from_blueprint(project_id, world_blueprint)

    # 更新项目状态为 world_ready
    project.status = "world_ready"
    await session.commit()
    logger.info("项目 %s 世界观蓝图生成完成，状态标记为 world_ready", project_id)

    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    ai_message = "世界观已生成，可以继续生成角色与人物关系。"
    return BlueprintGenerationResponse(blueprint=project_schema.blueprint, ai_message=ai_message)


@router.post("/{project_id}/blueprint/characters", response_model=BlueprintGenerationResponse)
async def generate_blueprint_characters(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
    mcp_registry: MCPPluginRegistry = Depends(get_mcp_registry),
) -> BlueprintGenerationResponse:
    """多步蓝图生成：第二步，基于世界观生成角色与人物关系。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    mcp_tool_service = MCPToolService(session, mcp_registry)
    llm_service = LLMService(session, mcp_tool_service=mcp_tool_service)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("[角色蓝图][步骤1/4] 开始生成角色与关系蓝图, project_id=%s", project_id)

    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    blueprint = project_schema.blueprint
    if not blueprint or not (blueprint.world_setting or {}).get("core_rules"):
        logger.warning("项目 %s 尚未生成世界观蓝图，无法生成角色与关系", project_id)
        raise HTTPException(status_code=400, detail="请先生成世界观蓝图后再生成角色与关系")

    blueprint_dict = blueprint.model_dump()
    payload = {"blueprint": blueprint_dict}

    system_prompt = _ensure_prompt(
        await prompt_service.get_prompt("blueprint_characters"),
        "blueprint_characters",
    )

    # 使用与世界观/完整蓝图相同的方式，从概念对话中提取可用于生成的历史记录
    history_records = await novel_service.list_conversations(project_id)
    if not history_records:
        logger.warning("项目 %s 缺少对话历史，无法生成角色与关系蓝图", project_id)
        raise HTTPException(
            status_code=400,
            detail="缺少对话历史，请先完成概念对话后再生成角色与关系",
        )

    formatted_history: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content
        if not role or not content:
            continue
        try:
            normalized = unwrap_markdown_json(content)
            data = json.loads(normalized)
            if role == "user":
                user_value = data.get("value", data)
                if isinstance(user_value, str):
                    formatted_history.append({"role": "user", "content": user_value})
            elif role == "assistant":
                ai_message = data.get("ai_message") if isinstance(data, dict) else None
                if ai_message:
                    formatted_history.append({"role": "assistant", "content": ai_message})
        except (json.JSONDecodeError, AttributeError):
            continue

    if not formatted_history:
        logger.warning("项目 %s 对话历史格式异常，无法提取有效内容用于角色与关系生成", project_id)
        raise HTTPException(
            status_code=400,
            detail="无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话",
        )
    # 使用 MCP 工具进行资料/规划阶段，为角色与关系设计提供参考说明
    logger.info("[角色蓝图][步骤2/4] 进入 MCP 规划阶段, 准备检索角色与关系参考资料, project_id=%s", project_id)
    mcp_reference_text = ""
    try:
        planning_messages = [
            {
                "role": "system",
                "content": (
                    "你是一名资深角色设定与人物关系设计顾问，可以调用外部 MCP 插件检索资料，"
                    "为后续的角色与人物关系蓝图设计提供真实、系统的参考信息。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "下面是我们之前关于这部小说的概念对话内容，以及当前的世界观蓝图，请先通读这些信息，"
                    "在需要时调用可用的工具，检索与题材、时代背景、世界观设定、人物原型和关系网络等相关的 1-3 条高价值资料，"
                    "并整理成供角色与关系设计使用的参考说明，不要直接输出最终角色与关系的 JSON 蓝图。\n\n"
                    + "\n".join(f"[{item['role']}]: {item['content']}" for item in formatted_history)
                    + "\n\n[当前世界观蓝图](JSON):\n"
                    + json.dumps(payload, ensure_ascii=False, indent=2)
                ),
            },
        ]
        mcp_reference_text = await llm_service.generate_text_with_mcp(
            messages=planning_messages,
            user_id=current_user.id,
            temperature=0.5,
            timeout=600.0,
        )
        mcp_reference_text = mcp_reference_text or ""
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "项目 %s 角色与关系 MCP 规划阶段失败，将在无 MCP 参考资料的情况下生成角色与关系: %s",
            project_id,
            exc,
        )
        mcp_reference_text = ""

    conversation_for_characters: List[Dict[str, Any]] = list(formatted_history)
    if mcp_reference_text:
        conversation_for_characters.append(
            {
                "role": "assistant",
                "content": "[MCP 参考资料]\n" + mcp_reference_text,
            }
        )
    conversation_for_characters.append(
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        }
    )

    logger.info("[角色蓝图][步骤3/4] 调用 LLM 生成角色与关系 JSON 蓝图, project_id=%s", project_id)

    response_raw = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=conversation_for_characters,
        temperature=0.7,
        user_id=current_user.id,
        timeout=900.0,
    )
    response_raw = remove_think_tags(response_raw)
    response_normalized = unwrap_markdown_json(response_raw)
    response_sanitized = sanitize_json_like_text(response_normalized)

    try:
        data = json.loads(response_sanitized)
    except json.JSONDecodeError as exc:  # noqa: BLE001
        logger.error(
            "项目 %s 角色蓝图生成 JSON 解析失败: %s, 原始内容预览: %s",
            project_id,
            exc,
            response_sanitized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"角色与关系蓝图生成失败，AI 返回的内容格式不正确: {str(exc)}",
        ) from exc

    characters: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]

    if isinstance(data, list):
        entities = data
        characters = entities
        relationships = []

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            name = entity.get("name")
            if not name:
                continue
            rels = entity.get("relationships_array") or []
            if not isinstance(rels, list):
                continue
            for rel in rels:
                if not isinstance(rel, dict):
                    continue
                target_name = rel.get("target_character_name")
                if not target_name:
                    continue
                relationships.append(
                    {
                        "character_from": name,
                        "character_to": target_name,
                        "relationship_type": rel.get("relationship_type"),
                        "intimacy_level": rel.get("intimacy_level", 0),
                        "description": rel.get("description"),
                    }
                )
    elif isinstance(data, dict):
        characters = data.get("characters") or []
        relationships = data.get("relationships") or []
    else:
        logger.error(
            "项目 %s 角色蓝图生成返回了不支持的 JSON 类型: %s",
            project_id,
            type(data).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="角色与关系蓝图生成失败，AI 返回的 JSON 结构不正确，请联系管理员。",
        )

    patch: Dict[str, Any] = {
        "characters": characters,
        "relationships": relationships,
    }
    logger.info("[角色蓝图][步骤4/4] 解析成功, 准备写入角色与关系到蓝图, project_id=%s", project_id)
    await novel_service.patch_blueprint(project_id, patch)

    # 更新项目状态为 characters_ready
    project.status = "characters_ready"
    await session.commit()
    logger.info("项目 %s 角色与关系蓝图生成完成，状态标记为 characters_ready", project_id)

    updated_schema = await novel_service.get_project_schema(project_id, current_user.id)
    ai_message = "角色与人物关系已生成，可以继续生成章节大纲。"
    return BlueprintGenerationResponse(blueprint=updated_schema.blueprint, ai_message=ai_message)


@router.post("/{project_id}/blueprint/generate", response_model=BlueprintGenerationResponse)
async def generate_blueprint(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
    mcp_registry: MCPPluginRegistry = Depends(get_mcp_registry),
) -> BlueprintGenerationResponse:
    """根据完整对话生成可执行的小说蓝图。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)

    # 初始化 MCP 工具服务和支持 MCP 的 LLM 服务
    mcp_tool_service = MCPToolService(session, mcp_registry)
    llm_service = LLMService(session, mcp_tool_service=mcp_tool_service)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("[完整蓝图][步骤1/4] 开始生成完整小说蓝图, project_id=%s", project_id)

    # 统一整理概念对话历史，供后续各阶段复用
    history_records = await novel_service.list_conversations(project_id)
    if not history_records:
        logger.warning("项目 %s 缺少对话历史，无法生成蓝图", project_id)
        raise HTTPException(status_code=400, detail="缺少对话历史，请先完成概念对话后再生成蓝图")

    formatted_history: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content
        if not role or not content:
            continue
        try:
            normalized = unwrap_markdown_json(content)
            data = json.loads(normalized)
            if role == "user":
                user_value = data.get("value", data)
                if isinstance(user_value, str):
                    formatted_history.append({"role": "user", "content": user_value})
            elif role == "assistant":
                ai_message = data.get("ai_message") if isinstance(data, dict) else None
                if ai_message:
                    formatted_history.append({"role": "assistant", "content": ai_message})
        except (json.JSONDecodeError, AttributeError):
            continue

    if not formatted_history:
        logger.warning("项目 %s 对话历史格式异常，无法提取有效内容", project_id)
        raise HTTPException(
            status_code=400,
            detail="无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话",
        )

    # 子步骤 A：先生成世界观蓝图
    try:
        logger.info("[完整蓝图][步骤1/4] 子步骤A：调用世界观蓝图流水线, project_id=%s", project_id)
        await generate_blueprint_world(
            project_id=project_id,
            session=session,
            current_user=current_user,
            mcp_registry=mcp_registry,
        )
    except HTTPException:
        # 直接向前端透传 HTTP 异常
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "项目 %s 在完整蓝图子步骤A（世界观蓝图）阶段失败，终止完整蓝图生成: %s",
            project_id,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="世界观蓝图生成失败，无法继续生成完整蓝图，请稍后重试或联系管理员。",
        ) from exc

    # 子步骤 B：基于世界观生成角色与关系蓝图
    try:
        logger.info("[完整蓝图][步骤1/4] 子步骤B：调用角色与关系蓝图流水线, project_id=%s", project_id)
        await generate_blueprint_characters(
            project_id=project_id,
            session=session,
            current_user=current_user,
            mcp_registry=mcp_registry,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "项目 %s 在完整蓝图子步骤B（角色与关系蓝图）阶段失败，终止完整蓝图生成: %s",
            project_id,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail="角色与关系蓝图生成失败，无法继续生成完整蓝图，请稍后重试或联系管理员。",
        ) from exc

    # 重新读取当前项目蓝图（此时已包含世界观与角色/关系），用于第三阶段作为上下文
    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    current_blueprint = project_schema.blueprint
    if current_blueprint is None:
        raise HTTPException(
            status_code=500,
            detail="蓝图生成失败，未能获取项目蓝图，请稍后重试或联系管理员。",
        )

    # 此处不再提前将项目标记为 blueprint_ready，蓝图完成由第三步「生成章节大纲」决定
    await session.commit()
    ai_message = "世界观与角色蓝图已生成，下一步请使用章节大纲生成功能完成蓝图。"
    return BlueprintGenerationResponse(blueprint=current_blueprint, ai_message=ai_message)

    # 第二阶段：使用 MCP 工具进行资料/规划阶段，为「完整蓝图（含章节大纲）」收集参考资料
    mcp_reference_text = ""
    try:
        logger.info("[完整蓝图][步骤2/4] 进入 MCP 规划阶段, 准备检索蓝图设计参考资料, project_id=%s", project_id)
        planning_messages = [
            {
                "role": "system",
                "content": (
                    "你是一名资深小说策划与世界观设计顾问，可以调用外部 MCP 插件检索资料，"
                    "为后续的完整小说蓝图设计提供真实、系统的参考信息。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "下面是我们之前关于这部小说的概念对话内容，请先通读这些信息，"
                    "在需要时调用可用的工具，检索与题材、时代背景、世界观设定、人物关系、剧情结构等相关的 1-3 条高价值资料，"
                    "并整理成供蓝图编写使用的参考说明，不要直接输出最终蓝图 JSON。\n\n"
                    + "\n".join(f"[{item['role']}]: {item['content']}" for item in formatted_history)
                ),
            },
        ]
        mcp_reference_text = await llm_service.generate_text_with_mcp(
            messages=planning_messages,
            user_id=current_user.id,
            temperature=0.5,
            timeout=600.0,
        )
        mcp_reference_text = mcp_reference_text or ""
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "项目 %s 蓝图 MCP 规划阶段失败，将在无 MCP 参考资料的情况下生成蓝图: %s",
            project_id,
            exc,
        )
        mcp_reference_text = ""

    # 第三阶段：在 screenwriting 提示 + 对话历史基础上（可选地）附加 MCP 参考资料和当前蓝图 JSON，生成最终蓝图（含章节大纲）
    logger.info("[完整蓝图][步骤3/4] 调用 LLM 生成完整 JSON 蓝图, project_id=%s", project_id)
    system_prompt = _ensure_prompt(await prompt_service.get_prompt("screenwriting"), "screenwriting")
    # 追加说明：当提供 blueprint JSON 时，要求模型优先遵守其中既有的世界观与角色设定
    system_prompt = (
        f"{system_prompt}\n\n"
        "补充说明：如果对话中额外提供了名为 `blueprint` 的 JSON 对象，"
        "你应在不违背该对象中已确定的世界观与角色设定的前提下，"
        "主要补全或细化章节大纲等结构内容；仅在确有必要时对既有设定做小幅调整，并保持前后一致。"
    )

    conversation_for_blueprint = list(formatted_history)
    if mcp_reference_text:
        conversation_for_blueprint.append(
            {
                "role": "assistant",
                "content": "[MCP 参考资料]\n" + mcp_reference_text,
            }
        )

    # 将当前蓝图作为结构化 JSON 上下文追加到对话中
    if blueprint_context:
        conversation_for_blueprint.append(
            {
                "role": "user",
                "content": json.dumps({"blueprint": blueprint_context}, ensure_ascii=False),
            }
        )

    blueprint_raw = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=conversation_for_blueprint,
        temperature=0.3,
        user_id=current_user.id,
        timeout=1200.0,
    )
    blueprint_raw = remove_think_tags(blueprint_raw)

    blueprint_normalized = unwrap_markdown_json(blueprint_raw)
    blueprint_sanitized = sanitize_json_like_text(blueprint_normalized)
    try:
        blueprint_data = json.loads(blueprint_sanitized)
    except json.JSONDecodeError as exc:  # noqa: BLE001
        logger.error(
            "项目 %s 蓝图生成 JSON 解析失败: %s\n原始响应: %s\n标准化后: %s\n清洗后: %s",
            project_id,
            exc,
            blueprint_raw[:500],
            blueprint_normalized[:500],
            blueprint_sanitized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图生成失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}",
        ) from exc

    blueprint = Blueprint(**blueprint_data)
    logger.info(
        "[完整蓝图][步骤4/4] 解析成功, 准备合并世界观/概述并更新章节大纲, project_id=%s",
        project_id,
    )

    # 先仅根据完整蓝图更新世界观与概述等元信息，不改动角色、关系和章节大纲
    await novel_service.update_world_from_blueprint(project_id, blueprint)

    # 再单独使用 patch_blueprint 更新章节大纲，避免覆盖已有角色与关系
    patch: Dict[str, Any] = {}
    if blueprint.chapter_outline:
        patch["chapter_outline"] = [item.model_dump() for item in blueprint.chapter_outline]
    if patch:
        await novel_service.patch_blueprint(project_id, patch)

    # 同步项目标题与状态，由路由层控制
    if blueprint.title:
        project.title = blueprint.title
    project.status = "blueprint_ready"
    await session.commit()
    logger.info("项目 %s 标记为 blueprint_ready，当前标题为 %s", project_id, project.title)

    # 终阶段：根据章节大纲自动拆分章节规划并创建章节记录
    # 这一阶段属于增强体验逻辑，失败时不会影响蓝图生成结果
    auto_expand_enabled = False
    try:
        user_setting_service = UserSettingService(session)
        # 用户级优先
        user_enabled = await user_setting_service.get(current_user.id, "auto_expand_enabled")
        if user_enabled is not None:
            enabled_source = user_enabled
        else:
            admin_setting_service = AdminSettingService(session)
            enabled_source = await admin_setting_service.get("auto_expand_enabled", "false")

        auto_expand_enabled = str(enabled_source).strip().lower() in {"1", "true", "yes", "y", "on"}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "项目 %s 读取自动章节拆分启用配置失败，将按关闭处理: %s",
            project_id,
            exc,
        )

    if auto_expand_enabled:
        try:
            await _auto_expand_chapter_outlines(
                project_id=project_id,
                session=session,
                current_user=current_user,
                mcp_registry=mcp_registry,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "项目 %s 自动拆分章节时发生异常，将继续返回蓝图结果: %s",
                project_id,
                exc,
            )

    ai_message = "太棒了！我已经根据我们的对话整理出完整的小说蓝图。"
    return BlueprintGenerationResponse(blueprint=blueprint, ai_message=ai_message)


@router.post("/{project_id}/blueprint/save", response_model=NovelProjectSchema)
async def save_blueprint(
    project_id: str,
    blueprint_data: Blueprint | None = Body(None),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """保存蓝图信息，可用于手动覆盖自动生成结果。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    if blueprint_data:
        await novel_service.replace_blueprint(project_id, blueprint_data)
        if blueprint_data.title:
            project.title = blueprint_data.title
            await session.commit()
        logger.info("项目 %s 手动保存蓝图", project_id)
    else:
        logger.warning("项目 %s 保存蓝图时未提供蓝图数据", project_id)
        raise HTTPException(status_code=400, detail="缺少蓝图数据，请提供有效的蓝图内容")

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.patch("/{project_id}/blueprint", response_model=NovelProjectSchema)
async def patch_blueprint(
    project_id: str,
    payload: BlueprintPatch,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """局部更新蓝图字段，对世界观或角色做微调。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    update_data = payload.model_dump(exclude_unset=True)
    await novel_service.patch_blueprint(project_id, update_data)
    logger.info("项目 %s 局部更新蓝图字段：%s", project_id, list(update_data.keys()))
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/generate", response_model=NovelGenerateResponse)
async def generate_novel_content(
    request: NovelGenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelGenerateResponse:
    """生成小说内容（支持 MCP 增强）。
    
    使用 LLM 生成小说内容，可选择启用 MCP 工具来增强生成能力。
    当 enable_mcp=True 时，系统会使用用户启用的 MCP 工具来搜索参考资料等。
    """
    llm_service = LLMService(session)
    
    logger.info(
        "用户 %s 请求生成内容，enable_mcp=%s",
        current_user.id,
        request.enable_mcp
    )
    
    # 使用 MCP 增强的生成
    result = await llm_service.generate_with_mcp(
        prompt=request.prompt,
        user_id=current_user.id,
        enable_mcp=request.enable_mcp,
        temperature=request.temperature,
        max_tool_rounds=3,
        tool_choice="auto"
    )
    
    logger.info(
        "用户 %s 生成完成，mcp_enhanced=%s，tools_used=%s",
        current_user.id,
        result["mcp_enhanced"],
        result["tools_used"]
    )
    
    return NovelGenerateResponse(
        content=result["content"],
        mcp_enhanced=result["mcp_enhanced"],
        tools_used=result["tools_used"],
        tool_calls_made=result["tool_calls_made"],
    )


async def _auto_expand_chapter_outlines(
    project_id: str,
    session: AsyncSession,
    current_user: UserInDB,
    mcp_registry: MCPPluginRegistry,
    *,
    target_chapter_count: int = 3,
    expansion_strategy: str = "balanced",
    enable_scene_analysis: bool = False,
    use_admin_setting: bool = True,
) -> None:
    """根据当前蓝图中的章节大纲，自动拆分为章节规划并创建章节记录。

    约定：
    - 仅在项目当前不存在任何章节记录时执行，避免重复拆分；
    - 使用与 writer.expand_outline_to_chapters 相同的提示词与解析方式；
    - 任意单个大纲拆分失败只记录日志并跳过，不影响整体流程。
    """
    novel_service = NovelService(session)
    prompt_service = PromptService(session)

    # 默认优先读取当前用户的拆分章节数（user_settings.auto_expand_target_chapter_count），
    # 若用户未配置，则回退到后台 Admin 设置（auto_expand_target_chapter_count）。
    # 当调用方显式指定 target_chapter_count 且希望优先使用该值时，可通过
    # use_admin_setting=False 跳过这一覆盖逻辑。
    if use_admin_setting:
        try:
            user_setting_service = UserSettingService(session)
            user_value = await user_setting_service.get(
                current_user.id,
                "auto_expand_target_chapter_count",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "项目 %s 读取用户级自动拆分章节数失败，将回退到后台配置: %s",
                project_id,
                exc,
            )
            user_value = None

        config_value = None
        if user_value is not None:
            config_value = user_value
        else:
            admin_setting_service = AdminSettingService(session)
            config_value = await admin_setting_service.get("auto_expand_target_chapter_count")

        if config_value is not None:
            try:
                parsed = int(str(config_value).strip())
                if parsed > 0:
                    target_chapter_count = parsed
            except (TypeError, ValueError):
                logger.warning(
                    "自动拆分章节数配置值无效：%s，将继续使用默认值 %s",
                    config_value,
                    target_chapter_count,
                )

    result = await session.execute(
        select(func.count(Chapter.id)).where(Chapter.project_id == project_id)
    )
    chapter_count = result.scalar() or 0
    if chapter_count > 0:
        logger.info(
            "项目 %s 已存在 %s 个章节记录，本次仅为尚未绑定章节的大纲尝试自动拆分",
            project_id,
            chapter_count,
        )

    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    blueprint = project_schema.blueprint
    if not blueprint:
        logger.info("项目 %s 当前尚无蓝图，跳过自动章节拆分", project_id)
        return

    blueprint_dict: Dict[str, Any] = blueprint.model_dump()
    world_setting = blueprint_dict.get("world_setting") or {}
    characters = blueprint_dict.get("characters") or []
    chapter_outline_dicts = blueprint_dict.get("chapter_outline") or []

    result = await session.execute(
        select(ChapterOutline)
        .where(ChapterOutline.project_id == project_id)
        .order_by(ChapterOutline.chapter_number)
    )
    outlines = list(result.scalars())
    if not outlines:
        logger.info("项目 %s 没有可用的章节大纲记录，跳过自动章节拆分", project_id)
        return

    result = await session.execute(
        select(Chapter.outline_id).where(Chapter.project_id == project_id)
    )
    existing_outline_ids = {row[0] for row in result if row[0] is not None}

    sorted_outline_dicts = sorted(
        chapter_outline_dicts,
        key=lambda o: o.get("chapter_number", 0),
    )
    outline_index_by_number: Dict[int, int] = {}
    for idx, item in enumerate(sorted_outline_dicts):
        number = item.get("chapter_number")
        if isinstance(number, int):
            outline_index_by_number[number] = idx

    characters_lines: List[str] = []
    for c in characters:
        name = c.get("name") or "未知角色"
        identity = c.get("identity") or ""
        personality = c.get("personality") or ""
        snippet = personality[:80] if personality else "暂无描述"
        line = f"- {name}: {identity}；性格：{snippet}"
        characters_lines.append(line)
    characters_text = "\n".join(characters_lines) if characters_lines else "暂无角色信息"

    strategy_desc: Dict[str, str] = {
        "balanced": "均衡展开：每章剧情量相当，节奏平稳",
        "climax": "高潮重点：重点章节剧情更丰满，其它章节略简",
        "detail": "细节丰富：每章都深入描写，场景和情感更细腻",
    }
    strategy_instruction = strategy_desc.get(expansion_strategy, strategy_desc["balanced"])

    system_prompt = _ensure_prompt(
        await prompt_service.get_prompt("outline_expansion"),
        "outline_expansion",
    )

    mcp_tool_service = MCPToolService(session, mcp_registry)
    llm_service = LLMService(session, mcp_tool_service=mcp_tool_service)

    result = await session.execute(
        select(func.max(Chapter.chapter_number)).where(Chapter.project_id == project_id)
    )
    max_number = result.scalar() or 0
    next_chapter_number = max_number + 1

    total_created = 0

    for outline in outlines:
        if existing_outline_ids and outline.id in existing_outline_ids:
            logger.info(
                "项目 %s 大纲 %s 已存在关联章节，跳过自动拆分",
                project_id,
                outline.id,
            )
            continue

        current_ch_no = outline.chapter_number

        prev_outline_desc = ""
        next_outline_desc = ""
        idx = outline_index_by_number.get(current_ch_no)
        if idx is not None and sorted_outline_dicts:
            if idx > 0:
                prev = sorted_outline_dicts[idx - 1]
                prev_outline_desc = (
                    f"【前一节】第{prev.get('chapter_number')}章 {prev.get('title')}: "
                    f"{prev.get('summary', '')}"
                )
            if idx + 1 < len(sorted_outline_dicts):
                nxt = sorted_outline_dicts[idx + 1]
                next_outline_desc = (
                    f"【后一节】第{nxt.get('chapter_number')}章 {nxt.get('title')}: "
                    f"{nxt.get('summary', '')}"
                )

        context_blocks: List[str] = []
        if prev_outline_desc:
            context_blocks.append(prev_outline_desc)
        if next_outline_desc:
            context_blocks.append(next_outline_desc)
        outline_context = "\n\n".join(context_blocks) if context_blocks else "（无前后文）"

        outline_summary = outline.summary or "暂无摘要"

        payload: Dict[str, Any] = {
            "project": {
                "id": project_schema.id,
                "title": project_schema.title,
                "genre": blueprint_dict.get("genre"),
                "target_audience": blueprint_dict.get("target_audience"),
                "style": blueprint_dict.get("style"),
                "tone": blueprint_dict.get("tone"),
                "one_sentence_summary": blueprint_dict.get("one_sentence_summary"),
            },
            "world_setting": world_setting,
            "characters_text": characters_text,
            "outline": {
                "id": outline.id,
                "chapter_number": outline.chapter_number,
                "title": outline.title,
                "summary": outline_summary,
            },
            "outline_context": outline_context,
            "expansion": {
                "target_chapter_count": target_chapter_count,
                "expansion_strategy": expansion_strategy,
                "strategy_instruction": strategy_instruction,
                "enable_scene_analysis": enable_scene_analysis,
            },
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        try:
            raw = await llm_service.generate_text(
                messages=messages,
                temperature=0.7,
                user_id=current_user.id,
                timeout=600.0,
                response_format=None,
            )
        except Exception as exc:
            logger.warning(
                "项目 %s 自动拆分章节时，大纲 %s 调用 LLM 失败: %s",
                project_id,
                outline.id,
                exc,
            )
            continue

        normalized = unwrap_markdown_json(remove_think_tags(raw))
        try:
            data = json.loads(normalized)
        except json.JSONDecodeError as exc:
            logger.error(
                "项目 %s 自动拆分章节时，大纲 %s 展开 JSON 解析失败: %s, 原始内容预览: %s",
                project_id,
                outline.id,
                exc,
                normalized[:500],
            )
            continue

        if isinstance(data, dict):
            plans_raw = [data]
        else:
            plans_raw = data

        chapter_plans: List[ChapterPlanItem] = []
        for item in plans_raw:
            try:
                plan = ChapterPlanItem.model_validate(item)
                chapter_plans.append(plan)
            except Exception as exc:
                logger.warning(
                    "项目 %s 自动拆分章节时，跳过无法解析的规划条目: %s, error=%s",
                    project_id,
                    item,
                    exc,
                )

        if not chapter_plans:
            logger.warning("项目 %s 大纲 %s 未生成任何有效的章节规划，已跳过", project_id, outline.id)
            continue

        created_chapters: List[Chapter] = []
        for idx_plan, plan in enumerate(chapter_plans):
            chapter_number = next_chapter_number
            next_chapter_number += 1
            sub_index = plan.sub_index or (idx_plan + 1)

            chapter = Chapter(
                project_id=project_id,
                outline_id=outline.id,
                chapter_number=chapter_number,
                sub_index=sub_index,
                status="not_generated",
                word_count=0,
                expansion_plan=plan.model_dump(),
            )
            session.add(chapter)
            created_chapters.append(chapter)

        await session.commit()
        for ch in created_chapters:
            await session.refresh(ch)

        created_count = len(created_chapters)
        total_created += created_count
        logger.info(
            "项目 %s 大纲 %s 已自动拆分并创建 %s 个章节记录，当前累计 %s 个章节",
            project_id,
            outline.id,
            created_count,
            total_created,
        )

    if total_created == 0:
        logger.info("项目 %s 自动拆分章节流程结束，但未创建任何章节记录", project_id)
    else:
        logger.info("项目 %s 自动拆分章节流程完成，共创建 %s 个章节记录", project_id, total_created)
