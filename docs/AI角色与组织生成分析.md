# AI角色与组织生成分析报告

> 本文档详细分析MuMuAINovel系统中AI生成角色和组织的实现方法、提示词设计和技术细节

## 目录

- [一、系统架构](#一系统架构)
- [二、角色生成](#二角色生成)
- [三、组织生成](#三组织生成)
- [四、技术实现细节](#四技术实现细节)
- [五、提示词设计原则](#五提示词设计原则)
- [六、使用示例](#六使用示例)

---

## 一、系统架构

### 1.1 核心文件结构

```
backend/
├── app/
│   ├── api/
│   │   ├── characters.py          # 角色生成API
│   │   └── organizations.py       # 组织生成API
│   ├── services/
│   │   ├── prompt_service.py      # 提示词管理服务
│   │   └── ai_service.py          # AI调用服务
│   └── models/
│       ├── character.py           # 角色数据模型
│       └── relationship.py        # 关系/组织模型
```

### 1.2 API端点

| 功能 | 端点 | 方法 | 说明 |
|------|------|------|------|
| 生成角色 | `/characters/generate` | POST | 非流式生成 |
| 生成角色(流式) | `/characters/generate-stream` | POST | SSE流式生成 |
| 生成组织 | `/organizations/generate` | POST | 非流式生成 |
| 生成组织(流式) | `/organizations/generate-stream` | POST | SSE流式生成 |


### 1.3 核心流程图

```
┌─────────────┐
│  用户请求   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  验证权限   │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ 获取项目上下文      │
│ - 世界观设定        │
│ - 已有角色/组织     │
│ - 主题/类型         │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 构建AI提示词        │
│ - 项目信息          │
│ - 用户要求          │
│ - 格式约束          │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 调用AI服务          │
│ - 支持MCP工具增强   │
│ - 搜索参考资料      │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 解析JSON响应        │
│ - 清理markdown标记  │
│ - 验证数据结构      │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 创建数据库记录      │
│ - Character表       │
│ - Organization表    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ 处理关系网络        │
│ - 角色关系          │
│ - 组织成员          │
└──────┬──────────────┘
       │
       ▼
┌─────────────┐
│  返回结果   │
└─────────────┘
```

---

## 二、角色生成

### 2.1 请求参数

```python
class CharacterGenerateRequest(BaseModel):
    """AI生成角色的请求模型"""
    project_id: str              # 项目ID（必填）
    name: Optional[str]          # 角色名称（可选，AI可生成）
    role_type: Optional[str]     # 角色定位：protagonist/supporting/antagonist
    background: Optional[str]    # 背景设定
    requirements: Optional[str]  # 其他要求
    enable_mcp: bool = True      # 是否启用MCP工具增强
```

### 2.2 角色生成提示词

**文件位置**: `backend/app/services/prompt_service.py`  
**提示词名称**: `SINGLE_CHARACTER_GENERATION`


#### 2.2.1 提示词结构

```
你是一位专业的角色设定师。请根据以下信息创建一个立体饱满的小说角色。

【项目上下文】
- 书名、主题、类型
- 世界观（时间、地点、氛围、规则）
- 已有角色列表
- 已有组织列表

【用户要求】
- 角色名称（可选）
- 角色定位（主角/配角/反派）
- 背景设定
- 其他要求

【生成内容要求】
1. 基本信息：姓名、年龄、性别
2. 外貌特征（100-150字）
3. 性格特点（150-200字）
4. 背景故事（200-300字）
5. 人际关系
6. 特殊能力/特长

【格式要求】
- 只返回纯JSON格式
- 禁止使用中文引号（""''）
- 使用【】或《》标记专有名词
- 不要包含markdown标记
```

#### 2.2.2 完整提示词示例

```python
SINGLE_CHARACTER_GENERATION = """你是一位专业的角色设定师。请根据以下信息创建一个立体饱满的小说角色。

{project_context}

{user_input}

请生成一个完整的角色卡片，包含以下所有信息：

1. **基本信息**：
   - 姓名：如果用户未提供，请生成一个符合世界观的名字
   - 年龄：具体数字或年龄段
   - 性别：男/女/其他

2. **外貌特征**（100-150字）：
   - 身高体型、面容特征、着装风格
   - 要符合角色定位和世界观设定

3. **性格特点**（150-200字）：
   - 核心性格特质（至少3个）
   - 优点和缺点
   - 特殊习惯或癖好
   - 性格要有复杂性和矛盾性

4. **背景故事**（200-300字）：
   - 家庭背景
   - 成长经历
   - 重要转折事件
   - 如何与项目主题关联
   - 融入用户提供的背景设定

5. **人际关系**：
   - 与现有角色的关系（如果有）
   - 重要的人际纽带
   - 社会地位和人脉

6. **特殊能力/特长**：
   - 擅长的领域
   - 特殊技能或知识
   - 符合世界观设定

**重要格式要求：**
1. 只返回纯JSON格式，不要包含任何markdown标记、代码块标记或其他说明文字
2. 不要在JSON字符串值中使用中文引号（""''），改用【】或《》
3. 文本描述中的专有名词使用【】标记

请严格按照以下JSON格式返回：
{
  "name": "角色姓名",
  "age": "年龄",
  "gender": "性别",
  "appearance": "外貌描述（100-150字）",
  "personality": "性格特点（150-200字）",
  "background": "背景故事（200-300字）",
  "traits": ["特长1", "特长2", "特长3"],
  
  "relationships_text": "人际关系的文字描述（用于显示）",
  
  "relationships": [
    {
      "target_character_name": "已存在的角色名称",
      "relationship_type": "关系类型（如：师父、朋友、敌人、父亲、母亲等）",
      "intimacy_level": 75,
      "description": "这段关系的详细描述",
      "started_at": "关系开始的故事时间点（可选）"
    }
  ],
  
  "organization_memberships": [
    {
      "organization_name": "已存在的组织名称",
      "position": "职位名称",
      "rank": 8,
      "loyalty": 80,
      "joined_at": "加入时间（可选）",
      "status": "active"
    }
  ]
}

**关系类型参考（请从中选择或自定义）：**
- 家族关系：父亲、母亲、兄弟、姐妹、子女、配偶、恋人
- 社交关系：师父、徒弟、朋友、同学、同事、邻居、知己
- 职业关系：上司、下属、合作伙伴
- 敌对关系：敌人、仇人、竞争对手、宿敌

**重要说明：**
1. relationships数组：只包含与上面列出的已存在角色的关系，通过target_character_name匹配
2. organization_memberships数组：只包含与上面列出的已存在组织的关系
3. intimacy_level是-100到100的整数（负值表示敌对、仇恨等关系），loyalty是0-100的整数
4. 如果没有关系或组织，对应数组为空[]
5. relationships_text是自然语言描述，用于展示给用户看

**角色设定要求：**
- 角色要符合项目的世界观和主题
- 如果是主角，要有明确的成长空间和目标动机
- 如果是反派，要有合理的动机，不能脸谱化
- 配角要有独特性，不能是工具人
- 所有设定要为故事服务

再次强调：
1. 只返回纯JSON对象，不要有```json```这样的标记
2. 文本中不要使用中文引号（""），改用【】或《》
3. 不要有任何额外的文字说明"""
```


### 2.3 返回数据结构

```json
{
  "name": "李明轩",
  "age": "25",
  "gender": "男",
  "appearance": "身高一米八，体型修长匀称。面容清秀，眉目间带着书卷气。常穿一袭青衫，腰间佩戴一块古玉。行走时步履沉稳，举手投足间透着儒雅之气。",
  "personality": "性格温和内敛，待人谦逊有礼。内心坚韧，有自己的原则和底线。喜欢独处思考，对世事有独到见解。虽不善言辞，但关键时刻能挺身而出。有时过于理想主义，容易陷入自我怀疑。",
  "background": "出身【天剑门】世家，自幼习武。但他更喜欢读书，常与父亲理念不合。十八岁那年，目睹师兄为争夺掌门之位而手足相残，对武林争斗心生厌倦。离开门派后游历江湖，希望找到武学之外的人生意义。",
  "traits": ["剑法精湛", "博览群书", "医术略通"],
  "relationships_text": "与【天剑门】掌门李天行为父子关系，但理念不合。与师妹林婉儿青梅竹马，情愫暗生。",
  "relationships": [
    {
      "target_character_name": "李天行",
      "relationship_type": "父亲",
      "intimacy_level": 40,
      "description": "父子关系紧张，父亲希望他继承掌门，但他志不在此"
    },
    {
      "target_character_name": "林婉儿",
      "relationship_type": "恋人",
      "intimacy_level": 85,
      "description": "青梅竹马，互有好感但未明说"
    }
  ],
  "organization_memberships": [
    {
      "organization_name": "天剑门",
      "position": "少门主",
      "rank": 8,
      "loyalty": 60,
      "status": "active"
    }
  ]
}
```

### 2.4 MCP工具增强

角色生成支持MCP（Model Context Protocol）工具增强，可以在生成过程中搜索参考资料。

```python
# 调用AI服务时启用MCP
result = await user_ai_service.generate_text_with_mcp(
    prompt=prompt,
    user_id=user_id,
    db_session=db,
    enable_mcp=True,        # 启用MCP工具
    max_tool_rounds=2,      # 最多2轮工具调用
    tool_choice="auto"      # 自动选择合适的工具
)
```

**MCP工具用途**：
- 搜索人物原型参考
- 查找角色背景资料
- 获取性格特征灵感
- 丰富角色设定细节

---

## 三、组织生成

### 3.1 请求参数

```python
class OrganizationGenerateRequest(BaseModel):
    """AI生成组织的请求模型"""
    project_id: str                    # 项目ID（必填）
    name: Optional[str]                # 组织名称（可选）
    organization_type: Optional[str]   # 组织类型（可选）
    background: Optional[str]          # 组织背景
    requirements: Optional[str]        # 特殊要求
    enable_mcp: bool = True            # 是否启用MCP工具增强
```

### 3.2 组织生成提示词

**文件位置**: `backend/app/services/prompt_service.py`  
**提示词名称**: `SINGLE_ORGANIZATION_GENERATION`


#### 3.2.1 提示词结构

```
你是一位专业的组织设定师。请根据以下信息创建一个完整的组织/势力设定。

【项目上下文】
- 书名、主题、类型
- 世界观设定
- 已有角色和组织

【用户要求】
- 组织名称（可选）
- 组织类型（可选）
- 背景设定
- 其他要求

【生成内容要求】
1. 基本信息：名称、类型、成立时间
2. 组织特性（150-200字）
3. 组织背景（200-300字）
4. 外在表现（100-150字）
5. 组织目的/宗旨
6. 势力等级（0-100）
7. 所在地点

【格式要求】
- 只返回纯JSON格式
- 禁止使用中文引号
- 使用【】或《》标记
```

#### 3.2.2 完整提示词示例

```python
SINGLE_ORGANIZATION_GENERATION = """你是一位专业的组织设定师。请根据以下信息创建一个完整的组织/势力设定。

{project_context}

{user_input}

请生成一个完整的组织设定，包含以下所有信息：

1. **基本信息**：
   - 组织名称：如果用户未提供，请生成一个符合世界观的名称
   - 组织类型：如帮派、公司、门派、学院、政府机构、宗教组织等
   - 成立时间：具体时间或时间段

2. **组织特性**（150-200字）：
   - 组织的核心理念和行事风格
   - 组织文化和价值观
   - 运作方式和管理模式
   - 特殊传统或规矩

3. **组织背景**（200-300字）：
   - 建立历史和起源
   - 发展历程和重要事件
   - 目前的地位和影响力
   - 如何与项目主题关联
   - 融入用户提供的背景设定

4. **外在表现**（100-150字）：
   - 总部或主要据点位置
   - 标志性建筑或场所
   - 组织标志、徽章、制服等
   - 可辨识的外在特征

5. **组织目的/宗旨**：
   - 明确的组织目标
   - 长期愿景
   - 行动准则

6. **势力等级**：
   - 在世界中的影响力（0-100）
   - 综合实力评估

7. **所在地点**：
   - 主要活动区域
   - 势力范围

**重要格式要求：**
1. 只返回纯JSON格式，不要包含任何markdown标记、代码块标记或其他说明文字
2. 不要在JSON字符串值中使用中文引号（""''），改用【】或《》
3. 文本描述中的专有名词使用【】标记

请严格按照以下JSON格式返回：
{
  "name": "组织名称",
  "is_organization": true,
  "organization_type": "组织类型",
  "personality": "组织特性（150-200字）",
  "background": "组织背景（200-300字）",
  "appearance": "外在表现（100-150字）",
  "organization_purpose": "组织目的和宗旨",
  "power_level": 75,
  "location": "所在地点",
  "motto": "组织格言或口号",
  "traits": ["特征1", "特征2", "特征3"],
  "color": "组织代表颜色（如：深红色、金色、黑色等）",
  "organization_members": ["重要成员1", "重要成员2", "重要成员3"]
}

**组织设定要求：**
- 组织要符合项目的世界观和主题
- 目标和行动要合理，不能过于理想化或脸谱化
- 要有存在的必要性，能推动故事发展
- 内部要有层级和结构
- 与其他势力要有互动关系

**说明**：
1. power_level是0-100的整数，表示组织在世界中的影响力
2. organization_members是组织内重要成员的名字列表（如果已有角色，可以关联）
3. 所有文本描述要详细具体，避免空泛

再次强调：
1. 只返回纯JSON对象，不要有```json```这样的标记
2. 文本中不要使用中文引号（""），改用【】或《》
3. 不要有任何额外的文字说明"""
```

### 3.3 返回数据结构

```json
{
  "name": "天剑门",
  "is_organization": true,
  "organization_type": "武林门派",
  "personality": "【天剑门】以剑道为宗，讲究正气凛然、行侠仗义。门规森严，弟子需恪守【十戒】。内部采用长老会制度，重大决策需集体表决。门派注重传承，每代只收精英弟子。行事光明磊落，但有时过于刚正不阿，不懂变通。",
  "background": "【天剑门】创立于三百年前，由剑圣【李无极】所建。初期只是小门小派，后因协助朝廷平定叛乱而声名鹊起。历代掌门皆为剑道高手，门派逐渐发展为江湖第一大派。五十年前的【血月之夜】，门派遭遇魔教围攻，损失惨重，从此与魔教结下血仇。如今门派实力恢复，但内部出现改革派与保守派之争。",
  "appearance": "总部位于【青云山】之巅，建有【剑阁】【演武场】【藏经楼】等建筑。山门前立有巨大石碑，刻着【天剑门】三个大字。弟子统一穿青色道袍，腰间佩剑，胸前绣有【天剑】徽记。",
  "organization_purpose": "以剑道匡扶正义，维护武林秩序，铲除邪魔外道，保护百姓安宁",
  "power_level": 85,
  "location": "青云山脉，势力范围覆盖江南三省",
  "motto": "剑指苍穹，正气长存",
  "traits": ["剑法精湛", "门规森严", "正派领袖"],
  "color": "青色",
  "organization_members": ["李天行", "林婉儿", "张无忌"]
}
```

### 3.4 组织特有字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `is_organization` | boolean | 标记为组织类型（必须为true） |
| `power_level` | int | 势力等级（0-100），表示影响力 |
| `location` | string | 组织所在地或主要活动区域 |
| `motto` | string | 组织格言、口号或宗旨 |
| `color` | string | 组织代表颜色（视觉识别） |
| `organization_type` | string | 组织类型（门派/帮派/公司等） |
| `organization_purpose` | string | 组织目的和宗旨 |

---

## 四、技术实现细节

### 4.1 数据库设计

#### 4.1.1 Character表（角色/组织统一表）

```sql
CREATE TABLE characters (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    age VARCHAR,
    gender VARCHAR,
    is_organization BOOLEAN DEFAULT FALSE,  -- 区分角色/组织
    role_type VARCHAR,                      -- protagonist/supporting/antagonist
    personality TEXT,
    background TEXT,
    appearance TEXT,
    relationships TEXT,                     -- 关系文本描述
    organization_type VARCHAR,              -- 组织类型
    organization_purpose TEXT,              -- 组织目的
    organization_members TEXT,              -- 组织成员JSON
    traits TEXT,                            -- 特长JSON数组
    avatar_url VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```


#### 4.1.2 Organization表（组织详情表）

```sql
CREATE TABLE organizations (
    id VARCHAR PRIMARY KEY,
    character_id VARCHAR NOT NULL,          -- 关联Character表
    project_id VARCHAR NOT NULL,
    member_count INTEGER DEFAULT 0,         -- 成员数量
    power_level INTEGER DEFAULT 50,         -- 势力等级
    location VARCHAR,                       -- 所在地
    motto VARCHAR,                          -- 格言
    color VARCHAR,                          -- 代表颜色
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(id)
);
```

#### 4.1.3 CharacterRelationship表（角色关系表）

```sql
CREATE TABLE character_relationships (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR NOT NULL,
    character_from_id VARCHAR NOT NULL,     -- 关系发起者
    character_to_id VARCHAR NOT NULL,       -- 关系目标
    relationship_name VARCHAR,              -- 关系名称
    intimacy_level INTEGER DEFAULT 50,      -- 亲密度（-100到100）
    description TEXT,                       -- 关系描述
    started_at VARCHAR,                     -- 关系开始时间
    source VARCHAR DEFAULT 'manual',        -- 来源：ai/manual
    created_at TIMESTAMP,
    FOREIGN KEY (character_from_id) REFERENCES characters(id),
    FOREIGN KEY (character_to_id) REFERENCES characters(id)
);
```

#### 4.1.4 OrganizationMember表（组织成员表）

```sql
CREATE TABLE organization_members (
    id VARCHAR PRIMARY KEY,
    organization_id VARCHAR NOT NULL,       -- 组织ID
    character_id VARCHAR NOT NULL,          -- 角色ID
    position VARCHAR,                       -- 职位
    rank INTEGER DEFAULT 0,                 -- 等级
    loyalty INTEGER DEFAULT 50,             -- 忠诚度（0-100）
    contribution INTEGER DEFAULT 0,         -- 贡献值
    status VARCHAR DEFAULT 'active',        -- 状态：active/inactive/expelled
    joined_at VARCHAR,                      -- 加入时间
    left_at VARCHAR,                        -- 离开时间
    notes TEXT,                             -- 备注
    source VARCHAR DEFAULT 'manual',        -- 来源：ai/manual
    created_at TIMESTAMP,
    FOREIGN KEY (organization_id) REFERENCES organizations(id),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);
```

### 4.2 JSON解析与清理

AI返回的内容可能包含markdown标记，需要清理后再解析：

```python
# 清理AI响应
cleaned_response = ai_response.strip()

# 移除markdown代码块标记
if cleaned_response.startswith("```json"):
    cleaned_response = cleaned_response[7:]
if cleaned_response.startswith("```"):
    cleaned_response = cleaned_response[3:]
if cleaned_response.endswith("```"):
    cleaned_response = cleaned_response[:-3]

cleaned_response = cleaned_response.strip()

# 解析JSON
try:
    character_data = json.loads(cleaned_response)
except json.JSONDecodeError as e:
    logger.error(f"JSON解析失败: {str(e)}")
    raise HTTPException(
        status_code=500,
        detail=f"AI返回的内容无法解析为JSON。错误：{str(e)}"
    )
```

### 4.3 关系网络处理

#### 4.3.1 角色关系处理

```python
# 只处理非组织角色的关系
if not is_organization:
    relationships_data = character_data.get("relationships", [])
    
    for rel in relationships_data:
        target_name = rel.get("target_character_name")
        
        # 查找目标角色
        target_result = await db.execute(
            select(Character).where(
                Character.project_id == project_id,
                Character.name == target_name
            )
        )
        target_char = target_result.scalar_one_or_none()
        
        if target_char:
            # 创建关系记录
            relationship = CharacterRelationship(
                project_id=project_id,
                character_from_id=character.id,
                character_to_id=target_char.id,
                relationship_name=rel.get("relationship_type"),
                intimacy_level=rel.get("intimacy_level", 50),
                description=rel.get("description", ""),
                started_at=rel.get("started_at"),
                source="ai"
            )
            db.add(relationship)
```

#### 4.3.2 组织成员关系处理

```python
# 处理角色加入组织的关系
org_memberships = character_data.get("organization_memberships", [])

for membership in org_memberships:
    org_name = membership.get("organization_name")
    
    # 查找组织
    org_char_result = await db.execute(
        select(Character).where(
            Character.project_id == project_id,
            Character.name == org_name,
            Character.is_organization == True
        )
    )
    org_char = org_char_result.scalar_one_or_none()
    
    if org_char:
        # 获取Organization记录
        org_result = await db.execute(
            select(Organization).where(
                Organization.character_id == org_char.id
            )
        )
        org = org_result.scalar_one_or_none()
        
        # 创建成员关系
        member = OrganizationMember(
            organization_id=org.id,
            character_id=character.id,
            position=membership.get("position", "成员"),
            rank=membership.get("rank", 0),
            loyalty=membership.get("loyalty", 50),
            joined_at=membership.get("joined_at"),
            status=membership.get("status", "active"),
            source="ai"
        )
        db.add(member)
        
        # 更新组织成员计数
        org.member_count += 1
```

### 4.4 流式生成（SSE）

支持Server-Sent Events流式返回进度：

```python
async def generate_character_stream(request, http_request, db, user_ai_service):
    """流式生成角色"""
    async def generate() -> AsyncGenerator[str, None]:
        try:
            # 发送进度
            yield await SSEResponse.send_progress("开始生成角色...", 0)
            
            # 获取上下文
            yield await SSEResponse.send_progress("获取项目上下文...", 10)
            
            # 构建提示词
            yield await SSEResponse.send_progress("构建AI提示词...", 20)
            
            # 调用AI
            yield await SSEResponse.send_progress("调用AI服务...", 30)
            
            # 解析响应
            yield await SSEResponse.send_progress("解析AI响应...", 60)
            
            # 创建记录
            yield await SSEResponse.send_progress("创建角色记录...", 75)
            
            # 处理关系
            yield await SSEResponse.send_progress("处理关系网络...", 90)
            
            # 完成
            yield await SSEResponse.send_progress("角色生成完成！", 100, "success")
            
            # 发送结果
            yield await SSEResponse.send_result({"character": character_dict})
            yield await SSEResponse.send_done()
            
        except Exception as e:
            yield await SSEResponse.send_error(f"生成失败: {str(e)}")
    
    return create_sse_response(generate())
```

---

## 五、提示词设计原则

### 5.1 核心原则

#### 1. **结构化输出**
- 明确的JSON schema定义
- 每个字段都有详细说明
- 减少AI自由发挥空间

#### 2. **字数控制**
- 外貌：100-150字
- 性格：150-200字
- 背景：200-300字
- 确保内容质量和详细度

#### 3. **格式约束**
- 禁止中文引号（""''）
- 禁止markdown标记
- 使用【】或《》标记专有名词
- 只返回纯JSON

#### 4. **防止幻觉**
- 明确要求只引用已存在的角色/组织
- 提供已有实体列表
- 如果没有可引用的就留空数组

#### 5. **上下文感知**
- 提供完整的项目世界观
- 列出已有角色和组织
- 确保新生成内容与现有设定一致


### 5.2 提示词优化技巧

#### 1. **明确角色定位**
```
- protagonist（主角）：要有成长空间和目标动机
- supporting（配角）：要有独特性，不能是工具人
- antagonist（反派）：要有合理动机，不能脸谱化
```

#### 2. **关系类型参考**
提供常见关系类型列表，引导AI选择：
```
- 家族：父亲、母亲、兄弟、姐妹、子女、配偶、恋人
- 社交：师父、徒弟、朋友、同学、同事、邻居、知己
- 职业：上司、下属、合作伙伴
- 敌对：敌人、仇人、竞争对手、宿敌
```

#### 3. **数值范围约束**
```
- intimacy_level: -100到100（负值表示敌对）
- loyalty: 0到100
- power_level: 0到100
- rank: 整数，表示等级
```

#### 4. **示例引导**
在提示词中提供JSON格式示例，让AI理解期望的输出结构。

#### 5. **重复强调**
关键要求在提示词末尾再次强调：
```
再次强调：
1. 只返回纯JSON对象，不要有```json```这样的标记
2. 文本中不要使用中文引号（""），改用【】或《》
3. 不要有任何额外的文字说明
```

### 5.3 常见问题与解决方案

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| JSON解析失败 | AI返回了markdown标记 | 清理```json```等标记 |
| 中文引号导致解析错误 | AI使用了""或'' | 提示词中明确禁止，使用【】替代 |
| 引用不存在的角色 | AI产生幻觉 | 提供已有实体列表，明确约束 |
| 内容过于简短 | 没有字数要求 | 明确每个字段的字数范围 |
| 格式不统一 | 提示词不够明确 | 提供详细的JSON schema |

---

## 六、使用示例

### 6.1 生成角色示例

#### 请求
```bash
POST /api/characters/generate
Content-Type: application/json

{
  "project_id": "proj_武侠世界_001",
  "name": "李明轩",
  "role_type": "protagonist",
  "background": "出身武林世家，但不喜欢打打杀杀，更喜欢读书",
  "requirements": "性格温和但有原则，关键时刻能挺身而出"
}
```

#### 响应
```json
{
  "id": "char_001",
  "project_id": "proj_武侠世界_001",
  "name": "李明轩",
  "age": "25",
  "gender": "男",
  "is_organization": false,
  "role_type": "protagonist",
  "personality": "性格温和内敛，待人谦逊有礼。内心坚韧，有自己的原则和底线...",
  "background": "出身【天剑门】世家，自幼习武。但他更喜欢读书，常与父亲理念不合...",
  "appearance": "身高一米八，体型修长匀称。面容清秀，眉目间带着书卷气...",
  "relationships": "与【天剑门】掌门李天行为父子关系，但理念不合。与师妹林婉儿青梅竹马...",
  "traits": "[\"剑法精湛\", \"博览群书\", \"医术略通\"]",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### 6.2 生成组织示例

#### 请求
```bash
POST /api/organizations/generate
Content-Type: application/json

{
  "project_id": "proj_武侠世界_001",
  "name": "天剑门",
  "organization_type": "武林门派",
  "background": "江湖第一大派，以剑道闻名",
  "requirements": "正派但有内部矛盾，改革派与保守派之争"
}
```

#### 响应
```json
{
  "id": "char_002",
  "project_id": "proj_武侠世界_001",
  "name": "天剑门",
  "is_organization": true,
  "role_type": "supporting",
  "organization_type": "武林门派",
  "personality": "【天剑门】以剑道为宗，讲究正气凛然、行侠仗义...",
  "background": "【天剑门】创立于三百年前，由剑圣【李无极】所建...",
  "appearance": "总部位于【青云山】之巅，建有【剑阁】【演武场】...",
  "organization_purpose": "以剑道匡扶正义，维护武林秩序，铲除邪魔外道",
  "traits": "[\"剑法精湛\", \"门规森严\", \"正派领袖\"]",
  "created_at": "2024-01-15T10:35:00Z"
}
```

同时在`organizations`表中创建详情记录：
```json
{
  "id": "org_001",
  "character_id": "char_002",
  "project_id": "proj_武侠世界_001",
  "member_count": 0,
  "power_level": 85,
  "location": "青云山脉，势力范围覆盖江南三省",
  "motto": "剑指苍穹，正气长存",
  "color": "青色"
}
```

### 6.3 流式生成示例

#### 请求
```bash
POST /api/characters/generate-stream
Content-Type: application/json

{
  "project_id": "proj_武侠世界_001",
  "name": "林婉儿",
  "role_type": "supporting"
}
```

#### SSE响应流
```
data: {"type":"progress","message":"开始生成角色...","progress":0}

data: {"type":"progress","message":"获取项目上下文...","progress":10}

data: {"type":"progress","message":"构建AI提示词...","progress":20}

data: {"type":"progress","message":"调用AI服务...","progress":30}

data: {"type":"progress","message":"解析AI响应...","progress":60}

data: {"type":"progress","message":"创建角色记录...","progress":75}

data: {"type":"progress","message":"处理关系网络...","progress":90}

data: {"type":"progress","message":"角色生成完成！","progress":100,"status":"success"}

data: {"type":"result","data":{"character":{"id":"char_003","name":"林婉儿",...}}}

data: {"type":"done"}
```

---

## 七、最佳实践

### 7.1 提示词编写建议

1. **明确输出格式**：提供完整的JSON schema
2. **字数约束**：每个字段指定字数范围
3. **防止幻觉**：明确只能引用已存在的实体
4. **格式约束**：禁止markdown标记和中文引号
5. **重复强调**：关键要求在末尾再次强调

### 7.2 API调用建议

1. **启用MCP**：角色生成时启用MCP工具增强
2. **流式生成**：长时间任务使用流式接口
3. **错误处理**：捕获JSON解析错误，提供友好提示
4. **日志记录**：记录AI响应和解析过程，便于调试

### 7.3 数据处理建议

1. **关系验证**：确保引用的角色/组织存在
2. **去重检查**：避免创建重复的关系记录
3. **事务处理**：使用数据库事务确保数据一致性
4. **自动创建**：组织角色自动创建Organization详情

### 7.4 性能优化建议

1. **批量查询**：一次性获取所有已有角色/组织
2. **异步处理**：使用async/await提高并发性能
3. **缓存上下文**：项目世界观可以缓存
4. **限制数量**：上下文中只显示最近10个角色/组织

---

## 八、技术亮点

### 8.1 统一的角色/组织模型

角色和组织使用同一个`Character`表存储，通过`is_organization`字段区分：

**优点**：
- 简化数据模型
- 统一查询接口
- 便于建立关系网络
- 减少表关联复杂度

**实现**：
```python
# 创建角色
character = Character(
    project_id=project_id,
    name="李明轩",
    is_organization=False,  # 标记为角色
    role_type="protagonist"
)

# 创建组织
organization_char = Character(
    project_id=project_id,
    name="天剑门",
    is_organization=True,   # 标记为组织
    organization_type="武林门派"
)
```

### 8.2 MCP工具增强

角色生成支持MCP工具调用，可以搜索参考资料：

```python
result = await user_ai_service.generate_text_with_mcp(
    prompt=prompt,
    enable_mcp=True,
    max_tool_rounds=2
)
```

**应用场景**：
- 搜索历史人物原型
- 查找性格特征参考
- 获取背景设定灵感
- 丰富角色细节

### 8.3 自动关系网络

AI生成时自动建立角色关系和组织成员关系：

```python
# AI返回的关系数据
"relationships": [
  {
    "target_character_name": "李天行",
    "relationship_type": "父亲",
    "intimacy_level": 40
  }
]

# 自动创建CharacterRelationship记录
# 自动创建OrganizationMember记录
```

### 8.4 流式进度反馈

使用SSE提供实时进度反馈，提升用户体验：

```
0%   → 开始生成角色
10%  → 获取项目上下文
20%  → 构建AI提示词
30%  → 调用AI服务
60%  → 解析AI响应
75%  → 创建角色记录
90%  → 处理关系网络
100% → 角色生成完成
```

---

## 九、总结

### 9.1 核心特性

1. **提示词工程精细**：详细的格式要求和内容指导
2. **关系网络自动化**：AI生成时自动建立关系
3. **MCP工具增强**：搜索参考资料丰富内容
4. **上下文一致性**：基于项目世界观生成
5. **流式进度反馈**：实时显示生成进度
6. **统一数据模型**：角色和组织使用同一表

### 9.2 技术优势

- **结构化输出**：明确的JSON schema减少解析错误
- **防止幻觉**：只引用已存在的实体
- **字数控制**：确保内容质量和详细度
- **格式约束**：禁止干扰项，提高解析成功率
- **关系验证**：自动验证和创建关系记录

### 9.3 应用价值

这套AI生成系统为小说创作提供了强大的辅助功能：

1. **快速构建角色**：几秒钟生成完整角色卡
2. **自动关系网络**：AI自动建立角色间关系
3. **世界观一致**：基于项目设定生成内容
4. **组织势力管理**：完整的组织/势力系统
5. **可扩展性强**：支持MCP工具扩展

---

## 附录

### A. 相关文件清单

```
backend/app/
├── api/
│   ├── characters.py              # 角色生成API（约800行）
│   └── organizations.py           # 组织生成API（约600行）
├── services/
│   ├── prompt_service.py          # 提示词服务（约1300行）
│   └── ai_service.py              # AI调用服务
├── models/
│   ├── character.py               # 角色模型
│   └── relationship.py            # 关系/组织模型
└── schemas/
    ├── character.py               # 角色Schema
    └── relationship.py            # 关系Schema
```

### B. 关键常量

```python
# 角色定位
ROLE_TYPES = ["protagonist", "supporting", "antagonist"]

# 关系类型
RELATIONSHIP_TYPES = [
    "父亲", "母亲", "兄弟", "姐妹", "子女", "配偶", "恋人",
    "师父", "徒弟", "朋友", "同学", "同事", "邻居", "知己",
    "上司", "下属", "合作伙伴",
    "敌人", "仇人", "竞争对手", "宿敌"
]

# 数值范围
INTIMACY_LEVEL_RANGE = (-100, 100)  # 亲密度
LOYALTY_RANGE = (0, 100)            # 忠诚度
POWER_LEVEL_RANGE = (0, 100)        # 势力等级
```

### C. 参考资源

- [提示词工程最佳实践](https://platform.openai.com/docs/guides/prompt-engineering)
- [JSON Schema规范](https://json-schema.org/)
- [Server-Sent Events规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [MCP协议文档](https://modelcontextprotocol.io/)

---

**文档版本**: v1.0  
**最后更新**: 2024-01-15  
**维护者**: MuMuAINovel开发团队
