import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user, get_mcp_registry
from ...db.session import get_session
from ...mcp.registry import MCPPluginRegistry
from ...models.novel import Chapter, ChapterOutline
from ...schemas.novel import (
    ChapterPlanItem,
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    NovelProject as NovelProjectSchema,
    OutlineChaptersResponse,
    OutlineExpansionRequest,
    OutlineExpansionResponse,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
    UpdateExpansionPlanRequest,
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
from .novels import _auto_expand_chapter_outlines

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


def _ensure_prompt(prompt: str | None, name: str) -> str:
    if not prompt:
        raise HTTPException(status_code=500, detail=f"未配置名为 {name} 的提示词，请联系管理员")
    return prompt


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

    # 按原有流程：先按章节号获取/创建章节，再补充其所属大纲信息
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    outline = None
    # 如果章节已经绑定了大纲（例如由拆分生成的子章节），优先使用该大纲
    if getattr(chapter, "outline_id", None):
        for o in project.outlines:
            if o.id == chapter.outline_id:
                outline = o
                break

    # 兼容旧模式：如果章节上还没有绑定大纲，则仍然允许通过章节号直接查找对应大纲
    if outline is None:
        outline = await novel_service.get_outline(project_id, request.chapter_number)

    if not outline:
        logger.warning("项目 %s 未找到第 %s 章对应的大纲记录，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    # 显式绑定章节与纲要，便于后续按大纲维度管理多章节
    if not getattr(chapter, "outline_id", None):
        chapter.outline_id = outline.id
    if not getattr(chapter, "sub_index", None):
        chapter.sub_index = 1
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

    # 如果该章节来自大纲拆分，优先使用 expansion_plan 中的细粒度规划补充标题与摘要
    plan = getattr(chapter, "expansion_plan", None)
    child_plan_text = ""
    if isinstance(plan, dict):
        plan_title = plan.get("title")
        plan_summary = plan.get("plot_summary") or plan.get("summary")
        if plan_title:
            outline_title = f"{outline_title} - {plan_title}"
        if plan_summary:
            if outline_summary and outline_summary != "暂无摘要":
                outline_summary = f"{outline_summary}\n子章节剧情摘要：{plan_summary}"
            else:
                outline_summary = plan_summary

        plan_parts: List[str] = []
        if plan_title:
            plan_parts.append(f"子章节标题：{plan_title}")
        if plan_summary:
            plan_parts.append(f"剧情摘要：{plan_summary}")
        if plan.get("narrative_goal"):
            plan_parts.append(f"叙事目标：{plan['narrative_goal']}")
        if plan.get("conflict_type"):
            plan_parts.append(f"冲突类型：{plan['conflict_type']}")
        if isinstance(plan.get("key_events"), list) and plan["key_events"]:
            plan_parts.append("关键事件：")
            for ev in plan["key_events"]:
                plan_parts.append(f"- {ev}")
        child_plan_text = "\n".join(plan_parts)

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
    # 基于 Blueprint Schema 中的 chapter_outline 构造「章节大纲骨架」，对齐 MuMu 的 outlines_context 思路
    # 若某章节已经有真实内容摘要（completed_chapters），则骨架中优先展示真实摘要，未来章节则展示大纲摘要
    outlines_context_lines: List[str] = []
    completed_map = {c["chapter_number"]: c for c in completed_chapters}
    chapter_outline_list = getattr(project_schema.blueprint, "chapter_outline", None) or []
    for item in sorted(chapter_outline_list, key=lambda x: x.chapter_number):
        num = item.chapter_number
        title = item.title or ""
        # 已完成章节优先使用 real_summary，未完成的使用大纲摘要
        completed = completed_map.get(num)
        if completed and completed.get("summary"):
            summary = completed["summary"]
        else:
            summary = item.summary or ""
        children = getattr(item, "children", None) or []

        if summary:
            base = f"第{num}章《{title}》：{summary}"
        else:
            base = f"第{num}章《{title}》"

        # 如果该大纲已拆分出子章节，则追加其章节号信息，帮助模型理解章节与子章节的映射
        if children:
            child_nums = [
                str(getattr(child, "chapter_number", None))
                for child in children
                if getattr(child, "chapter_number", None) is not None
            ]
            if child_nums:
                base += f"（当前大纲下章节：第{'、'.join(child_nums)}章）"

        outlines_context_lines.append(base)

    outlines_context = "\n".join(outlines_context_lines) if outlines_context_lines else "暂无章节大纲骨架"

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
        planning_system_prompt = _ensure_prompt(
            await prompt_service.get_prompt("chapter_mcp_planning"),
            "chapter_mcp_planning",
        )
        planning_messages = [
            {
                "role": "system",
                "content": planning_system_prompt,
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

    prompt_sections: List[tuple[str, str]] = [
        ("[世界蓝图](JSON)", blueprint_text),
        ("[章节大纲骨架]", outlines_context),
        # ("[前情摘要]", completed_section),
        ("[上一章摘要]", previous_summary_text),
        ("[上一章结尾]", previous_tail_excerpt),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要]", rag_summaries_text),
    ]

    if child_plan_text:
        prompt_sections.append(("[子章节规划]", child_plan_text))

    prompt_sections.append(
        (
            "[当前章节目标]",
            f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}",
        )
    )
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
        planning_system_prompt = _ensure_prompt(
            await prompt_service.get_prompt("outline_mcp_planning"),
            "outline_mcp_planning",
        )
        planning_messages = [
            {
                "role": "system",
                "content": planning_system_prompt,
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

    # new 模式：按 MuMu 行为清空旧大纲后整体写入新的章节大纲；同时清空所有已有章节
    if actual_mode == "new":
        await session.execute(
            delete(ChapterOutline).where(ChapterOutline.project_id == project_id)
        )
        await session.execute(
            delete(Chapter).where(Chapter.project_id == project_id)
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

    # 解析本次请求中是否指定了自动拆分每条大纲的章节数
    auto_expand_target = getattr(request, "auto_expand_target_chapter_count", None)

    # 在全新生成 / 续写模式下，根据最新章节大纲自动拆分章节
    if actual_mode in ("new", "continue"):
        try:
            kwargs = {}
            if auto_expand_target is not None:
                kwargs["target_chapter_count"] = auto_expand_target
                kwargs["use_admin_setting"] = False

            await _auto_expand_chapter_outlines(
                project_id=project_id,
                session=session,
                current_user=current_user,
                mcp_registry=mcp_registry,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "项目 %s 重新生成章节大纲后自动拆分章节失败，将继续返回项目数据: %s",
                project_id,
                exc,
            )

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.post(
    "/novels/{project_id}/outlines/{outline_id}/expand",
    response_model=OutlineExpansionResponse,
)
async def expand_outline_to_chapters(
    project_id: str,
    outline_id: int,
    request: OutlineExpansionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
    mcp_registry: MCPPluginRegistry = Depends(get_mcp_registry),
) -> OutlineExpansionResponse:
    """根据单个章节大纲展开为多章节规划，并可自动创建章节记录。"""

    novel_service = NovelService(session)
    prompt_service = PromptService(session)

    # 初始化 MCP 工具服务与 LLM 服务
    mcp_tool_service = MCPToolService(session, mcp_registry)
    llm_service = LLMService(session, mcp_tool_service=mcp_tool_service)

    # 校验项目归属
    await novel_service.ensure_project_owner(project_id, current_user.id)

    # 获取大纲记录，确保属于当前项目
    result = await session.execute(
        select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.id == outline_id,
        )
    )
    outline = result.scalars().first()
    if not outline:
        logger.warning("项目 %s 未找到大纲 %s，无法展开", project_id, outline_id)
        raise HTTPException(status_code=404, detail="大纲不存在")

    # 读取项目整体蓝图，用于构建上下文
    project_schema = await novel_service.get_project_schema(project_id, current_user.id)
    blueprint = project_schema.blueprint
    blueprint_dict: Dict[str, Any] = blueprint.model_dump() if blueprint else {}

    world_setting = blueprint_dict.get("world_setting") or {}
    characters = blueprint_dict.get("characters") or []
    chapter_outlines = blueprint_dict.get("chapter_outline") or []

    # 构造前后大纲上下文，帮助模型控制剧情边界
    prev_outline_desc = ""
    next_outline_desc = ""
    if chapter_outlines:
        current_ch_no = outline.chapter_number
        sorted_outlines = sorted(
            chapter_outlines,
            key=lambda o: o.get("chapter_number", 0),
        )
        idx = next(
            (i for i, o in enumerate(sorted_outlines) if o.get("chapter_number") == current_ch_no),
            None,
        )
        if idx is not None:
            if idx > 0:
                prev = sorted_outlines[idx - 1]
                prev_outline_desc = (
                    f"【前一节】第{prev.get('chapter_number')}章 {prev.get('title')}: "
                    f"{prev.get('summary', '')}"
                )
            if idx + 1 < len(sorted_outlines):
                nxt = sorted_outlines[idx + 1]
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

    # 角色摘要文本
    characters_lines: List[str] = []
    for c in characters:
        name = c.get("name") or "未知角色"
        identity = c.get("identity") or ""
        personality = c.get("personality") or ""
        snippet = personality[:80] if personality else "暂无描述"
        line = f"- {name}: {identity}；性格：{snippet}"
        characters_lines.append(line)
    characters_text = "\n".join(characters_lines) if characters_lines else "暂无角色信息"

    outline_summary = outline.summary or "暂无摘要"

    strategy_desc = {
        "balanced": "均衡展开：每章剧情量相当，节奏平稳",
        "climax": "高潮重点：重点章节剧情更丰满，其它章节略简",
        "detail": "细节丰富：每章都深入描写，场景和情感更细腻",
    }
    strategy_instruction = strategy_desc.get(request.expansion_strategy, strategy_desc["balanced"])
    system_prompt = _ensure_prompt(
        await prompt_service.get_prompt("outline_expansion"),
        "outline_expansion",
    )

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
            "target_chapter_count": request.target_chapter_count,
            "expansion_strategy": request.expansion_strategy,
            "strategy_instruction": strategy_instruction,
            "enable_scene_analysis": request.enable_scene_analysis,
        },
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    raw = await llm_service.generate_text(
        messages=messages,
        temperature=0.7,
        user_id=current_user.id,
        timeout=600.0,
        response_format=None,
    )

    normalized = unwrap_markdown_json(remove_think_tags(raw))
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        logger.error(
            "项目 %s 大纲 %s 展开 JSON 解析失败: %s, 原始内容预览: %s",
            project_id,
            outline_id,
            exc,
            normalized[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"大纲展开失败，AI 返回的内容格式不正确: {str(exc)}",
        ) from exc

    # 兼容模型返回单个对象的情况
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
            logger.warning("跳过无法解析的章节规划条目: %s, error=%s", item, exc)

    if not chapter_plans:
        raise HTTPException(status_code=500, detail="AI 未能生成有效的章节规划")

    created_chapters_payload: Optional[List[Dict[str, Any]]] = None

    if request.auto_create_chapters:
        # 计算起始章节号
        result = await session.execute(
            select(func.max(Chapter.chapter_number)).where(Chapter.project_id == project_id)
        )
        max_number = result.scalar()
        start_chapter_number = (max_number or 0) + 1

        created: List[Chapter] = []
        for idx, plan in enumerate(chapter_plans):
            chapter_number = start_chapter_number + idx
            sub_index = plan.sub_index or (idx + 1)

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
            created.append(chapter)

        await session.commit()
        for ch in created:
            await session.refresh(ch)

        created_chapters_payload = [
            {
                "id": ch.id,
                "chapter_number": ch.chapter_number,
                "sub_index": ch.sub_index,
                "title": (ch.expansion_plan or {}).get("title")
                if isinstance(ch.expansion_plan, dict)
                else None,
                "status": ch.status,
            }
            for ch in created
        ]

        logger.info(
            "项目 %s 大纲 %s 已根据规划创建 %s 个章节记录，起始章节号 %s",
            project_id,
            outline_id,
            len(created),
            start_chapter_number,
        )

    return OutlineExpansionResponse(
        outline_id=outline.id,
        outline_title=outline.title or f"第{outline.chapter_number}章",
        target_chapter_count=request.target_chapter_count,
        actual_chapter_count=len(chapter_plans),
        expansion_strategy=request.expansion_strategy,
        chapter_plans=chapter_plans,
        created_chapters=created_chapters_payload,
    )


@router.get(
    "/novels/{project_id}/outlines/{outline_id}/chapters",
    response_model=OutlineChaptersResponse,
)
async def get_outline_chapters(
    project_id: str,
    outline_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> OutlineChaptersResponse:
    """查询某个大纲下已经展开出的章节及其规划。"""

    novel_service = NovelService(session)

    # 校验项目归属
    await novel_service.ensure_project_owner(project_id, current_user.id)

    # 确认大纲存在且属于当前项目
    result = await session.execute(
        select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.id == outline_id,
        )
    )
    outline = result.scalars().first()
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")

    # 查询该大纲下的章节
    result = await session.execute(
        select(Chapter)
        .where(
            Chapter.project_id == project_id,
            Chapter.outline_id == outline_id,
        )
        .order_by(Chapter.chapter_number, Chapter.sub_index)
    )
    chapters = result.scalars().all()

    if not chapters:
        return OutlineChaptersResponse(
            has_chapters=False,
            chapter_count=0,
            chapters=[],
            expansion_plans=None,
        )

    # 还原每个章节的规划
    plans: List[ChapterPlanItem] = []
    for ch in chapters:
        plan_data = getattr(ch, "expansion_plan", None)
        if isinstance(plan_data, dict):
            try:
                plans.append(ChapterPlanItem.model_validate(plan_data))
            except Exception:
                continue

    return OutlineChaptersResponse(
        has_chapters=True,
        chapter_count=len(chapters),
        chapters=[
            {
                "id": ch.id,
                "chapter_number": ch.chapter_number,
                "sub_index": ch.sub_index or 1,
                "title": (ch.expansion_plan or {}).get("title")
                if isinstance(ch.expansion_plan, dict)
                else None,
                "status": ch.status,
            }
            for ch in chapters
        ],
        expansion_plans=plans or None,
    )


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


@router.post("/novels/{project_id}/chapters/update-expansion-plan", response_model=NovelProjectSchema)
async def update_expansion_plan(
    project_id: str,
    request: UpdateExpansionPlanRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """更新指定章节的展开规划（expansion_plan）。"""

    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    stmt = select(Chapter).where(
        Chapter.project_id == project_id,
        Chapter.chapter_number == request.chapter_number,
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    chapter.expansion_plan = request.expansion_plan.model_dump()
    await session.commit()

    logger.info(
        "用户 %s 更新项目 %s 第 %s 章展开规划",
        current_user.id,
        project_id,
        request.chapter_number,
    )

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
