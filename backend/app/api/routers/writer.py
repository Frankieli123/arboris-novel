import json
import logging
import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user, get_mcp_registry
from ...db.session import get_session
from ...mcp.registry import MCPPluginRegistry
from ...models.novel import Chapter, ChapterOutline
from ...schemas.novel import (
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    NovelProject as NovelProjectSchema,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.user import UserInDB
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.mcp_tool_service import MCPToolService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.vector_store_service import VectorStoreService
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json
from ...repositories.system_config_repository import SystemConfigRepository

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
    mcp_registry: MCPPluginRegistry = Depends(get_mcp_registry),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    
    # 初始化 MCP 工具服务
    mcp_tool_service = MCPToolService(session, mcp_registry)
    
    # 初始化 LLM 服务，传入 MCP 工具服务
    llm_service = LLMService(session, mcp_tool_service=mcp_tool_service)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.status = "generating"
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}
    # 收集所有可用的历史章节摘要，便于在 Prompt 中提供前情背景
    completed_chapters = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""
    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            summary = await llm_service.get_summary(
                existing.selected_version.content,
                temperature=0.15,
                user_id=current_user.id,
                timeout=180.0,
            )
            existing.real_summary = remove_think_tags(summary)
            await session.commit()
        completed_chapters.append(
            {
                "chapter_number": existing.chapter_number,
                "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
                "summary": existing.real_summary,
            }
        )
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    # 蓝图中禁止携带章节级别的细节信息，避免重复传输大段场景或对话内容
    banned_blueprint_keys = {
        "chapter_outline",
        "chapter_summaries",
        "chapter_details",
        "chapter_dialogues",
        "chapter_events",
        "conversation_history",
        "character_timelines",
    }
    for key in banned_blueprint_keys:
        if key in blueprint_dict:
            blueprint_dict.pop(key, None)

    writer_prompt = await prompt_service.get_prompt("writing")
    if not writer_prompt:
        logger.error("未配置名为 'writing' 的写作提示词，无法生成章节内容")
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置 'writing' 提示词")

    # 初始化向量检索服务，若未配置则自动降级为纯提示词生成
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    query_parts = [outline_title, outline_summary]
    if request.writing_notes:
        query_parts.append(request.writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    rag_context = await context_service.retrieve_for_generation(
        project_id=project_id,
        query_text=rag_query or outline.title or outline.summary or "",
        user_id=current_user.id,
    )
    chunk_count = len(rag_context.chunks) if rag_context and rag_context.chunks else 0
    summary_count = len(rag_context.summaries) if rag_context and rag_context.summaries else 0
    logger.info(
        "项目 %s 第 %s 章检索到 %s 个剧情片段和 %s 条摘要",
        project_id,
        request.chapter_number,
        chunk_count,
        summary_count,
    )
    # print("rag_context:",rag_context)
    # 将蓝图、前情、RAG 检索结果拼装成结构化段落，供模型理解
    blueprint_text = json.dumps(blueprint_dict, ensure_ascii=False, indent=2)
    completed_lines = [
        f"- 第{item['chapter_number']}章 - {item['title']}:{item['summary']}"
        for item in completed_chapters
    ]
    previous_summary_text = previous_summary_text or "暂无可用摘要"
    previous_tail_excerpt = previous_tail_excerpt or "暂无上一章结尾内容"
    completed_section = "\n".join(completed_lines) if completed_lines else "暂无前情摘要"
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"
    writing_notes = request.writing_notes or "无额外写作指令"

    mcp_reference_materials = ""
    try:
        planning_messages = [
            {
                "role": "system",
                "content": (
                    "你是一名资深小说写作助手，可以使用外部工具（MCP 插件）检索资料，"
                    "为后续章节写作提供真实、详细的背景信息。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"现在需要为小说项目生成第 {request.chapter_number} 章。\n\n"
                    f"[世界蓝图]\n{blueprint_text}\n\n"
                    f"[上一章摘要]\n{previous_summary_text}\n\n"
                    f"[检索到的剧情上下文]\n{rag_chunks_text}\n\n"
                    f"[检索到的章节摘要]\n{rag_summaries_text}\n\n"
                    "请分析这些信息，并在需要时调用可用的工具检索 1-3 条最有价值的背景资料，"
                    "并整理为供写作使用的参考笔记，不要直接写章节正文。"
                ),
            },
        ]
        planning_text = await llm_service.generate_text_with_mcp(
            messages=planning_messages,
            user_id=current_user.id,
            temperature=0.5,
            timeout=300.0,
        )
        mcp_reference_materials = planning_text or ""
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "项目 %s 第 %s 章 MCP 参考资料阶段失败，将使用普通模式写作: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        mcp_reference_materials = ""

    prompt_sections = [
        ("[世界蓝图](JSON)", blueprint_text),
        # ("[前情摘要]", completed_section),
        ("[上一章摘要]", previous_summary_text),
        ("[上一章结尾]", previous_tail_excerpt),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要]", rag_summaries_text),
        (
            "[当前章节目标]",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}",
        ),
    ]
    if mcp_reference_materials:
        prompt_sections.append(("[MCP 参考资料]", mcp_reference_materials))
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词：%s\n%s", writer_prompt, prompt_input)
    async def _generate_single_version(idx: int) -> Dict:
        try:
            # 使用 MCP 工具支持的生成方法
            messages = [
                {"role": "system", "content": writer_prompt},
                {"role": "user", "content": prompt_input}
            ]
            response = await llm_service.generate_text(
                messages=messages,
                temperature=0.9,
                user_id=current_user.id,
                timeout=600.0,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            try:
                return json.loads(normalized)
            except json.JSONDecodeError as parse_err:
                logger.warning(
                    "项目 %s 第 %s 章第 %s 个版本 JSON 解析失败，将原始内容作为纯文本处理: %s",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    parse_err,
                )
                return {"content": normalized}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "项目 %s 生成第 %s 章第 %s 个版本时发生异常: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}"
            )

    version_count = await _resolve_version_count(session)
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本",
        project_id,
        request.chapter_number,
        version_count,
    )
    raw_versions = []
    for idx in range(version_count):
        raw_versions.append(await _generate_single_version(idx))
    contents: List[str] = []
    metadata: List[Dict] = []
    for variant in raw_versions:
        if isinstance(variant, dict):
            if "content" in variant and isinstance(variant["content"], str):
                contents.append(variant["content"])
            elif "chapter_content" in variant:
                contents.append(str(variant["chapter_content"]))
            else:
                contents.append(json.dumps(variant, ensure_ascii=False))
            metadata.append(variant)
        else:
            contents.append(str(variant))
            metadata.append({"raw": variant})

    await novel_service.replace_chapter_versions(chapter, contents, metadata)
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本",
        project_id,
        request.chapter_number,
        len(contents),
    )
    return await _load_project_schema(novel_service, project_id, current_user.id)


async def _resolve_version_count(session: AsyncSession) -> int:
    repo = SystemConfigRepository(session)
    record = await repo.get_by_key("writer.chapter_versions")
    if record:
        try:
            value = int(record.value)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    env_value = os.getenv("WRITER_CHAPTER_VERSION_COUNT")
    if env_value:
        try:
            value = int(env_value)
            if value > 0:
                return value
        except ValueError:
            pass
    return 3


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法选择版本", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")

    selected = await novel_service.select_chapter_version(chapter, request.version_index)
    logger.info(
        "用户 %s 选择了项目 %s 第 %s 章的第 %s 个版本",
        current_user.id,
        project_id,
        request.chapter_number,
        request.version_index,
    )
    if selected and selected.content:
        summary = await llm_service.get_summary(
            selected.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
        await session.commit()

        # 选定版本后同步向量库，确保后续章节可检索到最新内容
        vector_store: Optional[VectorStoreService]
        if not settings.vector_store_enabled:
            vector_store = None
        else:
            try:
                vector_store = VectorStoreService()
            except RuntimeError as exc:
                logger.warning("向量库初始化失败，跳过章节向量同步: %s", exc)
                vector_store = None

        if vector_store:
            ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
            outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
            chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
            await ingestion_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter.chapter_number,
                title=chapter_title,
                content=selected.content,
                summary=chapter.real_summary,
                user_id=current_user.id,
            )
            logger.info(
                "项目 %s 第 %s 章已同步至向量库",
                project_id,
                chapter.chapter_number,
            )

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter:
        logger.warning("项目 %s 未找到第 %s 章，无法执行评估", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节不存在")
    if not chapter.versions:
        logger.warning("项目 %s 第 %s 章无可评估版本", project_id, request.chapter_number)
        raise HTTPException(status_code=400, detail="无可评估的章节版本")

    evaluator_prompt = await prompt_service.get_prompt("evaluation")
    if not evaluator_prompt:
        logger.error("缺少评估提示词，项目 %s 第 %s 章评估失败", project_id, request.chapter_number)
        raise HTTPException(status_code=500, detail="缺少评估提示词，请联系管理员配置 'evaluation' 提示词")

    project_schema = await novel_service._serialize_project(project)
    blueprint_dict = project_schema.blueprint.model_dump()

    versions_to_evaluate = [
        {"version_id": idx + 1, "content": version.content}
        for idx, version in enumerate(sorted(chapter.versions, key=lambda item: item.created_at))
    ]
    # print("blueprint_dict:",blueprint_dict)
    evaluator_payload = {
        "novel_blueprint": blueprint_dict,
        "content_to_evaluate": {
            "chapter_number": chapter.chapter_number,
            "versions": versions_to_evaluate,
        },
    }

    evaluation_raw = await llm_service.get_llm_response(
        system_prompt=evaluator_prompt,
        conversation_history=[{"role": "user", "content": json.dumps(evaluator_payload, ensure_ascii=False)}],
        temperature=0.3,
        user_id=current_user.id,
        timeout=360.0,
    )
    evaluation_clean = remove_think_tags(evaluation_raw)
    await novel_service.add_chapter_evaluation(chapter, None, evaluation_clean)
    logger.info("项目 %s 第 %s 章评估完成", project_id, request.chapter_number)

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapter_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
    mcp_registry: MCPPluginRegistry = Depends(get_mcp_registry),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)

    # 初始化 MCP 工具服务
    mcp_tool_service = MCPToolService(session, mcp_registry)

    # 初始化 LLM 服务，传入 MCP 工具服务
    llm_service = LLMService(session, mcp_tool_service=mcp_tool_service)

    # 校验项目归属
    await novel_service.ensure_project_owner(project_id, current_user.id)

    # 读取当前项目蓝图与已有章节大纲，用于智能判断生成模式
    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    blueprint_dict = project_schema.blueprint.model_dump()
    existing_outlines = blueprint_dict.get("chapter_outline") or []
    existing_count = len(existing_outlines)
    last_chapter_number = (
        max(outline.get("chapter_number", 0) for outline in existing_outlines)
        if existing_outlines
        else 0
    )

    # 计算实际执行模式：auto 根据是否已有大纲自动转为 new / continue
    requested_mode = getattr(request, "mode", "auto") or "auto"
    actual_mode = requested_mode
    if actual_mode == "auto":
        actual_mode = "continue" if existing_outlines else "new"

    if actual_mode == "continue" and not existing_outlines:
        logger.warning("项目 %s 请求续写大纲但当前没有任何章节大纲", project_id)
        raise HTTPException(status_code=400, detail="续写模式需要已有章节大纲，当前项目没有大纲")

    # 计算本次实际生成的起始章节与数量
    if actual_mode == "new":
        effective_start = 1
        effective_num = request.num_chapters
        # 全新生成时，为避免旧结构干扰提示词，将蓝图中的章节大纲清空后再送入模型
        blueprint_dict["chapter_outline"] = []
    elif actual_mode == "continue":
        effective_start = last_chapter_number + 1
        effective_num = request.num_chapters
    else:
        # 兼容旧行为：直接使用调用方提供的起始章节
        effective_start = request.start_chapter
        effective_num = request.num_chapters

    logger.info(
        "用户 %s 请求生成项目 %s 的章节大纲，模式 %s(实际 %s)，起始章节 %s，数量 %s，现有大纲数 %s",
        current_user.id,
        project_id,
        requested_mode,
        actual_mode,
        effective_start,
        effective_num,
        existing_count,
    )
    outline_prompt = await prompt_service.get_prompt("outline")
    if not outline_prompt:
        logger.error("缺少大纲提示词，项目 %s 大纲生成失败", project_id)
        raise HTTPException(status_code=500, detail="缺少大纲提示词，请联系管理员配置 'outline' 提示词")

    mcp_reference_materials = ""
    try:
        planning_messages = [
            {
                "role": "system",
                "content": (
                    "你是一名资深剧情策划助手，可以使用外部工具（MCP 插件）检索资料，"
                    "帮助设计更合理、更有张力的章节大纲。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"现在需要为小说项目生成章节大纲，起始章节为 {request.start_chapter}，连续 {request.num_chapters} 章。\n\n"
                    f"[世界蓝图]\n{json.dumps(blueprint_dict, ensure_ascii=False, indent=2)}\n\n"
                    "请在需要时调用可用的工具，检索与题材、时代背景、场景、情节结构相关的 1-3 条关键资料，"
                    "并整理成供大纲设计使用的参考说明，不要直接给出最终章节大纲 JSON。"
                ),
            },
        ]
        planning_text = await llm_service.generate_text_with_mcp(
            messages=planning_messages,
            user_id=current_user.id,
            temperature=0.5,
            timeout=300.0,
        )
        mcp_reference_materials = planning_text or ""
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "项目 %s 章节大纲 MCP 参考资料阶段失败，将使用普通模式生成: %s",
            project_id,
            exc,
        )
        mcp_reference_materials = ""

    # 组装提示负载，将模式与续写指导信息一并透传给 LLM
    wait_to_generate: Dict[str, Any] = {
        "start_chapter": effective_start,
        "num_chapters": effective_num,
        "mode": actual_mode,
        "original_start_chapter": request.start_chapter,
        "original_num_chapters": request.num_chapters,
        "keep_existing": getattr(request, "keep_existing", True),
    }

    if existing_outlines:
        wait_to_generate["existing_outline_count"] = existing_count
        wait_to_generate["last_chapter_number"] = last_chapter_number

    story_direction = getattr(request, "story_direction", None)
    if story_direction:
        wait_to_generate["story_direction"] = story_direction

    plot_stage = getattr(request, "plot_stage", None)
    if plot_stage:
        wait_to_generate["plot_stage"] = plot_stage

    payload = {
        "novel_blueprint": blueprint_dict,
        "wait_to_generate": wait_to_generate,
    }
    if mcp_reference_materials:
        payload["mcp_references"] = mcp_reference_materials

    # 使用 MCP 工具支持的生成方法
    messages = [
        {"role": "system", "content": outline_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
    ]
    response = await llm_service.generate_text(
        messages=messages,
        temperature=0.7,
        user_id=current_user.id,
        timeout=360.0,
    )
    normalized = unwrap_markdown_json(remove_think_tags(response))
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 大纲生成 JSON 解析失败: %s, 原始内容预览: %s",
            project_id,
            exc,
            normalized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"章节大纲生成失败，AI 返回的内容格式不正确: {str(exc)}"
        ) from exc

    new_outlines = data.get("chapters", [])

    # new 模式：按 MuMu 行为清空旧大纲后整体写入新的章节大纲
    if actual_mode == "new":
        await session.execute(
            delete(ChapterOutline).where(ChapterOutline.project_id == project_id)
        )
    for item in new_outlines:
        stmt = (
            select(ChapterOutline)
            .where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == item.get("chapter_number"),
            )
        )
        result = await session.execute(stmt)
        record = result.scalars().first()
        if record:
            record.title = item.get("title", record.title)
            record.summary = item.get("summary", record.summary)
        else:
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=item.get("chapter_number"),
                    title=item.get("title", ""),
                    summary=item.get("summary"),
                )
            )
    await session.commit()
    logger.info("项目 %s 章节大纲生成完成，新增/更新大纲数 %s，模式 %s", project_id, len(new_outlines), actual_mode)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 更新项目 %s 第 %s 章大纲",
        current_user.id,
        project_id,
        request.chapter_number,
    )

    stmt = (
        select(ChapterOutline)
        .where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    outline = result.scalars().first()
    if not outline:
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=request.chapter_number,
        )
        session.add(outline)

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()
    logger.info("项目 %s 第 %s 章大纲已更新", project_id, request.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    if not request.chapter_numbers:
        logger.warning("项目 %s 删除章节时未提供章节号", project_id)
        raise HTTPException(status_code=400, detail="请提供要删除的章节号列表")
    novel_service = NovelService(session)
    llm_service = LLMService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info(
        "用户 %s 删除项目 %s 的章节 %s",
        current_user.id,
        project_id,
        request.chapter_numbers,
    )
    await novel_service.delete_chapters(project_id, request.chapter_numbers)

    # 删除章节时同步清理向量库，避免过时内容被检索
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量删除: %s", exc)
            vector_store = None

    if vector_store:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        await ingestion_service.delete_chapters(project_id, request.chapter_numbers)
        logger.info(
            "项目 %s 已从向量库移除章节 %s",
            project_id,
            request.chapter_numbers,
        )

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = next((ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None)
    if not chapter or chapter.selected_version is None:
        logger.warning("项目 %s 第 %s 章尚未生成或未选择版本，无法编辑", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="章节尚未生成或未选择版本")

    chapter.selected_version.content = request.content
    chapter.word_count = len(request.content)
    logger.info("用户 %s 更新了项目 %s 第 %s 章内容", current_user.id, project_id, request.chapter_number)

    if request.content.strip():
        summary = await llm_service.get_summary(
            request.content,
            temperature=0.15,
            user_id=current_user.id,
            timeout=180.0,
        )
        chapter.real_summary = remove_think_tags(summary)
    await session.commit()

    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过章节向量更新: %s", exc)
            vector_store = None

    if vector_store and chapter.selected_version and chapter.selected_version.content:
        ingestion_service = ChapterIngestionService(llm_service=llm_service, vector_store=vector_store)
        outline = next((item for item in project.outlines if item.chapter_number == chapter.chapter_number), None)
        chapter_title = outline.title if outline and outline.title else f"第{chapter.chapter_number}章"
        await ingestion_service.ingest_chapter(
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            title=chapter_title,
            content=chapter.selected_version.content,
            summary=chapter.real_summary,
            user_id=current_user.id,
        )
        logger.info("项目 %s 第 %s 章更新内容已同步至向量库", project_id, chapter.chapter_number)

    return await novel_service.get_project_schema(project_id, current_user.id)
