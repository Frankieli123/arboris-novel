# MuMu 项目 MCP 调用详细位置

## 1. 大纲生成模块 (outlines.py)

### 1.1 全新生成大纲
**文件**：`MuMuAINovel-main/backend/app/api/outlines.py`
**函数**：`generate_outline_new()`
**行号**：约 350-410

```python
@router.post("/projects/{project_id}/outlines/generate")
async def generate_outline_new(
    project_id: int,
    request: OutlineGenerateRequest,  # 包含 enable_mcp 字段
    ...
):
    # 🔍 MCP工具增强：收集情节设计参考资料
    mcp_reference_materials = ""
    if request.enable_mcp:
        try:
            # 构建搜索提示词
            mcp_search_prompt = f"""
            请帮我搜索以下小说情节设计的参考资料：
            - 小说类型：{project.genre}
            - 故事主题：{project.theme}
            - 目标章节数：{request.chapter_count}
            """
            
            # 调用 MCP 工具
            mcp_result = await ai_service.generate_with_mcp(
                prompt=mcp_search_prompt,
                user_id="system",
                db_session=db,
                enable_mcp=True,
                max_tool_rounds=2,
                tool_choice="auto",
                provider=request.provider,
                model=request.model
            )
            
            mcp_reference_materials = mcp_result.get("content", "")
        except Exception as e:
            logger.error(f"MCP工具调用失败: {e}")
    
    # 将参考资料注入到大纲生成提示词
    final_prompt = f"""
    {base_prompt}
    
    参考资料：
    {mcp_reference_materials}
    """
```

**用途**：搜索情节设计参考资料，帮助生成更合理的大纲结构

---

### 1.2 续写大纲
**文件**：`MuMuAINovel-main/backend/app/api/outlines.py`
**函数**：`continue_outline()`
**行号**：约 570-700

```python
@router.post("/projects/{project_id}/outlines/continue")
async def continue_outline(
    project_id: int,
    request: OutlineGenerateRequest,
    ...
):
    # 分批生成，每批5章
    for batch_num in range(total_batches):
        # 🔍 MCP工具增强：收集续写参考资料
        mcp_reference_materials = ""
        if request.enable_mcp:
            try:
                mcp_search_prompt = f"""
                请帮我搜索续写参考资料：
                - 已有章节数：{len(existing_outlines)}
                - 当前情节阶段：{current_stage}
                - 需要续写的方向：{continuation_direction}
                """
                
                mcp_result = await ai_service.generate_with_mcp(
                    prompt=mcp_search_prompt,
                    user_id=user_id,
                    db_session=db,
                    enable_mcp=True,
                    max_tool_rounds=2,
                    tool_choice="auto"
                )
                
                mcp_reference_materials = mcp_result.get("content", "")
            except Exception as e:
                logger.error(f"MCP工具调用失败: {e}")
```

**用途**：搜索续写参考资料，确保续写内容与前文连贯

---

### 1.3 流式生成大纲
**文件**：`MuMuAINovel-main/backend/app/api/outlines.py`
**函数**：`generate_outline_stream()`
**行号**：约 870-940

```python
@router.post("/projects/{project_id}/outlines/generate/stream")
async def generate_outline_stream(request: Request):
    async def event_generator():
        # 🔍 MCP工具增强：收集情节设计参考资料
        mcp_reference_materials = ""
        if enable_mcp:
            try:
                yield await SSEResponse.send_progress("🔍 使用MCP工具收集参考资料...", 18)
                
                mcp_result = await ai_service.generate_with_mcp(
                    prompt=mcp_search_prompt,
                    user_id="system",
                    db_session=db,
                    enable_mcp=True,
                    max_tool_rounds=2,
                    tool_choice="auto"
                )
                
                mcp_reference_materials = mcp_result.get("content", "")
                yield await SSEResponse.send_progress("✅ MCP参考资料收集完成", 25)
            except Exception as e:
                yield await SSEResponse.send_progress(f"⚠️ MCP工具调用失败: {e}", 25)
```

**用途**：实时搜索参考资料，并通过 SSE 返回进度

---

## 2. 章节生成模块 (chapters.py)

### 2.1 生成章节内容
**文件**：`MuMuAINovel-main/backend/app/api/chapters.py`
**函数**：`generate_chapter_stream()`
**行号**：约 945-1170

```python
@router.post("/projects/{project_id}/chapters/{chapter_id}/generate/stream")
async def generate_chapter_stream(
    project_id: int,
    chapter_id: int,
    generate_request: ChapterGenerateRequest,  # 包含 enable_mcp 字段
    ...
):
    async def event_generator():
        # 🔧 MCP工具增强：收集章节参考资料
        mcp_reference_materials = ""
        if enable_mcp and current_user_id:
            try:
                yield f"data: {json.dumps({'type': 'progress', 'message': '🔍 尝试使用MCP工具收集参考资料...', 'progress': 28}, ensure_ascii=False)}\n\n"
                
                # 构建搜索提示词
                mcp_search_prompt = f"""
                请帮我搜索以下章节的参考资料：
                - 章节标题：{chapter.title}
                - 章节摘要：{chapter.summary}
                - 故事背景：{project.background}
                """
                
                mcp_result = await ai_service.generate_with_mcp(
                    prompt=mcp_search_prompt,
                    user_id=current_user_id,
                    db_session=db_session,
                    enable_mcp=True,
                    max_tool_rounds=2,
                    tool_choice="auto"
                )
                
                mcp_reference_materials = mcp_result.get("content", "")
                
                yield f"data: {json.dumps({'type': 'progress', 'message': '✅ MCP参考资料收集完成', 'progress': 35}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'progress', 'message': f'⚠️ MCP工具调用失败: {e}', 'progress': 35}, ensure_ascii=False)}\n\n"
        
        # 将参考资料注入到章节生成提示词
        final_prompt = f"""
        {base_prompt}
        
        参考资料：
        {mcp_reference_materials}
        """
```

**用途**：根据章节主题搜索相关参考资料，生成更丰富的章节内容

---

## 3. 角色生成模块 (characters.py)

### 3.1 生成角色设定
**文件**：`MuMuAINovel-main/backend/app/api/characters.py`
**函数**：`generate_character()`
**行号**：约 440-450

```python
@router.post("/projects/{project_id}/characters/generate")
async def generate_character(
    project_id: int,
    request: CharacterGenerateRequest,  # 包含 enable_mcp 字段
    ...
):
    # 🔍 MCP工具增强：收集角色参考资料
    mcp_reference_materials = ""
    if request.enable_mcp:
        try:
            mcp_search_prompt = f"""
            请帮我搜索以下角色的参考资料：
            - 角色类型：{request.character_type}
            - 角色特征：{request.requirements}
            - 故事背景：{project.background}
            """
            
            mcp_result = await ai_service.generate_with_mcp(
                prompt=mcp_search_prompt,
                user_id=user_id,
                db_session=db,
                enable_mcp=True,
                max_tool_rounds=2,
                tool_choice="auto"
            )
            
            mcp_reference_materials = mcp_result.get("content", "")
        except Exception as e:
            logger.error(f"MCP工具调用失败: {e}")
```

**用途**：搜索人物原型参考，帮助生成更立体的角色设定

---

### 3.2 批量生成角色
**文件**：`MuMuAINovel-main/backend/app/api/characters.py`
**函数**：`batch_generate_characters()`
**行号**：约 810-820

```python
@router.post("/projects/{project_id}/characters/batch-generate")
async def batch_generate_characters(
    project_id: int,
    request: CharacterBatchGenerateRequest,
    ...
):
    for character_type in request.character_types:
        # 每个角色都使用 MCP 搜索参考
        mcp_result = await ai_service.generate_with_mcp(
            prompt=mcp_search_prompt,
            user_id=user_id,
            db_session=db,
            enable_mcp=True,
            max_tool_rounds=2,
            tool_choice="auto"
        )
```

**用途**：批量生成多个角色时，为每个角色搜索参考资料

---

## 4. 向导流式生成模块 (wizard_stream.py)

### 4.1 大纲向导
**文件**：`MuMuAINovel-main/backend/app/api/wizard_stream.py`
**函数**：`outline_wizard_stream()`
**行号**：约 50-100

```python
@router.post("/wizard/outline/stream")
async def outline_wizard_stream(request: Request):
    async def event_generator():
        enable_mcp = data.get("enable_mcp", True)  # 默认启用MCP
        
        # MCP工具增强：收集参考资料
        reference_materials = ""
        if enable_mcp and user_id:
            try:
                yield await SSEResponse.send_progress("🔍 尝试使用MCP工具收集参考资料...", 18)
                
                mcp_result = await ai_service.generate_with_mcp(
                    prompt=mcp_search_prompt,
                    user_id=user_id,
                    db_session=db,
                    enable_mcp=True,
                    max_tool_rounds=2,
                    tool_choice="auto"
                )
                
                reference_materials = mcp_result.get("content", "")
                yield await SSEResponse.send_progress("✅ MCP参考资料收集完成", 25)
            except Exception as e:
                yield await SSEResponse.send_progress(f"⚠️ MCP工具调用失败: {e}", 25)
```

**用途**：向导式生成大纲时，实时搜索参考资料

---

### 4.2 角色向导
**文件**：`MuMuAINovel-main/backend/app/api/wizard_stream.py`
**函数**：`character_wizard_stream()`
**行号**：约 300-360

```python
@router.post("/wizard/character/stream")
async def character_wizard_stream(request: Request):
    async def event_generator():
        enable_mcp = data.get("enable_mcp", True)
        
        # MCP工具增强：收集角色参考资料
        character_reference_materials = ""
        if enable_mcp and user_id:
            try:
                yield await SSEResponse.send_progress("🔍 尝试使用MCP工具收集角色参考资料...", 8)
                
                mcp_result = await ai_service.generate_with_mcp(
                    prompt=mcp_search_prompt,
                    user_id=user_id,
                    db_session=db,
                    enable_mcp=True,
                    max_tool_rounds=2,
                    tool_choice="auto"
                )
                
                character_reference_materials = mcp_result.get("content", "")
                yield await SSEResponse.send_progress("✅ MCP角色参考资料收集完成", 15)
            except Exception as e:
                yield await SSEResponse.send_progress(f"⚠️ MCP工具调用失败: {e}", 15)
```

**用途**：向导式生成角色时，实时搜索角色参考资料

---

## 5. AI 服务核心方法 (ai_service.py)

### 5.1 generate_with_mcp()
**文件**：`MuMuAINovel-main/backend/app/services/ai_service.py`
**函数**：`generate_with_mcp()`
**行号**：约 640-750

```python
async def generate_with_mcp(
    self,
    prompt: str,
    user_id: str,
    db_session,
    enable_mcp: bool = True,
    max_tool_rounds: int = 3,
    tool_choice: str = "auto",
    **kwargs
):
    """
    使用MCP工具增强的文本生成
    
    工作流程：
    1. 获取用户启用的MCP工具
    2. 第一轮：AI分析任务，决定是否使用工具
    3. 如果AI请求工具调用，执行工具并收集结果
    4. 第二轮：AI基于工具结果生成最终内容
    5. 支持最多3轮工具调用
    """
    
    # 1. 获取MCP工具
    tools = await mcp_tool_service.get_user_enabled_tools(
        user_id=user_id,
        db_session=db_session
    )
    
    # 2. 工具调用循环
    conversation_history = [{"role": "user", "content": prompt}]
    
    for round_num in range(max_tool_rounds):
        # 调用AI（第一轮传递工具列表）
        ai_response = await self.generate_text(
            prompt=conversation_history[-1]["content"],
            tools=tools if round_num == 0 else None,
            tool_choice=tool_choice if round_num == 0 else None,
            **kwargs
        )
        
        # 检查是否有工具调用
        tool_calls = ai_response.get("tool_calls", [])
        
        if not tool_calls:
            # AI返回最终内容
            return {
                "content": ai_response.get("content", ""),
                "tool_calls_made": result["tool_calls_made"],
                "tools_used": result["tools_used"],
                "finish_reason": ai_response.get("finish_reason", "stop"),
                "mcp_enhanced": True
            }
        
        # 3. 执行工具调用
        tool_results = await mcp_tool_service.execute_tool_calls(
            user_id=user_id,
            tool_calls=tool_calls,
            db_session=db_session
        )
        
        # 4. 构建工具上下文
        tool_context = await mcp_tool_service.build_tool_context(
            tool_results,
            format="markdown"
        )
        
        # 5. 更新对话历史
        conversation_history.append({
            "role": "assistant",
            "content": ai_response.get("content", ""),
            "tool_calls": tool_calls
        })
        conversation_history.append({
            "role": "tool",
            "content": tool_context
        })
```

**用途**：核心方法，实现多轮工具调用逻辑

---

## 总结

### MCP 调用的统一模式

所有业务场景都遵循相同的模式：

```python
# 1. 检查是否启用 MCP
if enable_mcp:
    try:
        # 2. 构建搜索提示词
        mcp_search_prompt = f"请帮我搜索关于 {topic} 的参考资料"
        
        # 3. 调用 MCP 工具
        mcp_result = await ai_service.generate_with_mcp(
            prompt=mcp_search_prompt,
            user_id=user_id,
            db_session=db,
            enable_mcp=True,
            max_tool_rounds=2,
            tool_choice="auto"
        )
        
        # 4. 提取参考资料
        reference_materials = mcp_result.get("content", "")
        
        # 5. 将参考资料注入到最终提示词
        final_prompt = f"{base_prompt}\n\n参考资料：\n{reference_materials}"
        
    except Exception as e:
        logger.error(f"MCP工具调用失败: {e}")
        # 降级为普通生成
```

### 关键特点

1. **所有生成场景都支持 MCP**：大纲、章节、角色、向导
2. **统一的调用接口**：都通过 `ai_service.generate_with_mcp()`
3. **优雅的降级处理**：MCP 失败时自动降级为普通生成
4. **用户可控**：通过 `enable_mcp` 参数控制是否使用
5. **实时反馈**：流式接口中显示 MCP 调用进度
