Arboris 前端 UI 规范（草案）
1. 品牌与颜色系统
主品牌色（Primary / Indigo）
主色：indigo-500 / 600 / 700
用途：主按钮、主操作（“开始创作”“保存设置”等）、高亮链接、选中状态。
Tailwind 建议：
默认：bg-indigo-500
Hover：hover:bg-indigo-600
强调：bg-gradient-to-r from-indigo-600 to-indigo-700
中性色（Neutral / Slate & Gray）
页面背景：bg-slate-50, 渐变背景：bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50
容器背景：bg-white, 半透明：bg-white/80 ~ bg-white/95 + backdrop-blur
文本：
主文本：text-slate-900 或 text-gray-800
次级文本：text-slate-500 / text-gray-600
说明 / meta 信息：text-slate-400 / text-gray-500
边框：border-slate-200/60、border-gray-200
状态色
成功：green-500/600
按钮：bg-green-500 hover:bg-green-600
Tag：type="success" / text-green-600 bg-green-50
警告：amber-500 或 Naive type="warning"
错误：red-500/600
按钮：bg-red-600 hover:bg-red-700
提示：bg-red-50 border-red-200 text-red-700
信息：blue-500 / Naive type="info"
Naive UI 主题映射（建议）
primaryColor: #4f46e5（indigo-600）
successColor: #16a34a（green-600）
warningColor: #f59e0b（amber-500）
errorColor: #dc2626（red-600）
卡片 / Layout 背景：接近 rgba(255,255,255,0.9) 搭配阴影。
2. 字体与文字体系
基础设定
字体：系统无衬线字体栈（system-ui、-apple-system、BlinkMacSystemFont 等）
行高：正文 leading-relaxed，标题 leading-tight
字号语义层级（对应 Tailwind）
H1：text-3xl font-bold
用于页面主标题（如“我的小说项目”）。
H2：text-2xl font-bold
用于重要分区标题、详情页主标题。
H3：text-xl font-semibold
用于卡片标题、对话框标题。
H4：text-lg font-semibold
用于列表分组、小模块标题。
正文：text-sm text-gray-700 或 text-base text-gray-700
次要信息 / Caption：text-xs text-gray-500
用法约定
页面级标题：统一左对齐，紧跟一行 text-sm text-slate-500 的副标题或说明。
列表 / 表格标题单元格：font-medium text-slate-700。
3. 布局与间距
页面容器
通用外框：min-h-screen p-4 sm:p-6 lg:p-8
居中内容：max-w-6xl（一般设置页）、max-w-7xl（小说列表）、max-w-[1800px]（详情 / 工作台）
内层容器 / 卡片
主内容容器（例如小说列表卡片包裹层）：
bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl p-6 md:p-8
侧边卡片（设置页侧边栏等）：
bg-white/70 rounded-2xl shadow-lg p-4
间距规范
区块与区块间：mt-6 或 space-y-6
卡片内部：
标题与内容：mb-4
行间距：space-y-2 ~ space-y-4
头部导航左右内边距：px-4 sm:px-6 lg:px-8，高度：h-16 或 py-4
4. 导航与头部（Header / Sidebar）
顶部导航（写作工作台、详情页）
背景：bg-white/80 ~ /90 backdrop-blur-lg border-b border-slate-200/60 shadow-sm
布局：flex items-center justify-between h-16
左侧：返回按钮 + 标题 + meta 信息（进度、章节数、更新时间等）
右侧：操作按钮组（查看详情、退出、切换侧栏等），统一 rounded-lg + hover:bg-gray-100。
侧边栏（Admin / 详情页）
Admin：
n-layout-sider，宽 240，collapse-mode="width"，手机端默认折叠。
详情页侧边导航：
固定：fixed left-0 top-[73px] bottom-0 w-72 bg-white/95 backdrop-blur-lg border-r shadow-2xl
菜单按钮：rounded-xl px-4 py-3.5 text-sm font-medium
选中：bg-gradient-to-r from-indigo-50 to-indigo-100/80 text-indigo-700 ring-1 ring-indigo-200/50
未选中：text-slate-600 hover:bg-slate-50 hover:text-slate-900
5. 卡片（Card / Panel）
基础卡片
外观：bg-white rounded-xl shadow-sm border border-slate-200/60
内边距：p-4（小卡） / p-6（常规） / p-8（重要模块）
标题区：.card-header → 左侧标题，右侧操作按钮（刷新、过滤等）
高层级卡片
用于大场景容器（小说项目列表）：rounded-2xl shadow-2xl bg-white/95
移动端卡片（Admin 小说管理）
size="small" embedded + 内部 meta 行：标签 + 值两列。
6. 按钮规范（Button）
Primary 主按钮
Tailwind 版：
类：px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors
重要 CTA（如“开始创作”）：bg-indigo-500 hover:bg-indigo-600 transition-all duration-300 transform hover:scale-105
Naive 版：
type="primary"，必要时 ghost / tertiary 用于弱化。
Secondary 次按钮
Text / Ghost 按钮：
text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg px-3 py-2
用于返回、取消、查看更多等。
Danger 危险按钮
Tailwind：bg-red-600 text-white hover:bg-red-700 rounded-lg
Naive：type="error" 搭配 quaternary 或 tertiary 用于“删除”确认。
Icon Button（仅图标）
方形：p-2 rounded-lg text-gray-600 hover:bg-gray-100
统一图标大小：w-4 h-4（Naive 中为 size="small"）
尺寸
大按钮：px-6 py-3 text-base（着重行动，如“开始创作”）
中按钮：px-4 py-2 text-sm
小按钮：px-3 py-1.5 text-xs~sm（Admin 操作区）
7. 表单与输入（Forms）
布局
默认 label-placement="top"（Naive），单列表单。
一般间距：space-y-4，分区间：space-y-6。
输入控件
数字输入（限高 / 步长）：n-input-number :min :max :step，用于系统配置。
文本输入 / 文本域：
Tailwind：border-gray-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500
Naive：使用默认样式并统一主题色。
错误提示
表单级错误：n-alert type="error" closable 顶部展示。
字段级错误：优先用 Naive 的 rule；纯 Tailwind 场景下用 text-xs text-red-600 mt-1。
8. 列表 & 表格
卡片列表（小说项目网格）
容器：grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6
卡片：rounded-xl shadow-sm hover:shadow-md transition-colors
“创建新项目”卡片为统一占位样式：虚线边框 border-dashed border-gray-300，hover 变 hover:border-indigo-400 hover:bg-gray-50。
数据表格（Admin 区域）
基于 n-data-table：
size="small" :bordered="false"
分页：固定 pageSize: 8，不提供 pageSize 切换。
列设计：
主列：标题 + 子标题（ID）组合，使用自定义 render。
状态列：统一使用 n-tag size="small" round bordered={false}。
9. 状态反馈（加载 / 空 / 错误）
加载
大场景：中心 loading spinner + 文案
Tailwind：自绘 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin
Naive 场景：n-spin :show="loading" 包裹卡片或列表。
错误
卡片内错误：n-alert type="error" closable
全屏错误：类似 WritingDesk：
bg-red-50 border-red-200 rounded-xl p-8 max-w-md mx-auto
空状态
Tailwind 场景（小说列表）：文案 + CTA 按钮。
Admin：n-empty description="暂无数据" 或 n-result status="info"。
10. 模态框（Modal / Dialog）
基础规范
宽度：
大：880px（工具列表、测试报告等）
中：720px（编辑配置）
小：560px（确认 / 导入结果）
配合 maxWidth: '92vw' 保证移动端适配。
内部：
顶部：标题 H3（text-xl font-semibold）
内容：space-y-4
底部：右对齐按钮组（取消 + 主操作）。
确认对话框（删除等）
遮罩：fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center
内容卡片：bg-white rounded-2xl shadow-2xl max-w-md w-full p-6
标题 + Icon（圆形红底图标） + 补充说明 + 行为按钮。
11. 动效与交互细节
Hover 与过渡
统一使用：transition-colors duration-200
对重要按钮 / 卡片再加：transition-all duration-300 transform hover:scale-105
图标旋转（加载 / 测试中）：icon-spin 自定义 class → animate-spin 或 keyframes。
滚动与 Sticky
顶部导航：sticky top-0 z-40
详情页布局：左右分栏 + overflow-hidden + 内部 overflow-y-auto 滚动。
12. 响应式适配
断点策略
sm:：平板开始增加左右 padding、显示更多 meta 信息。
md:：容器从单列切为双列（如列表中 grid）。
lg:：显示桌面专用元素（如侧边栏常显、更多文案）。
常见模式
头部文案：
大屏：text-lg / 完整文案。
小屏：text-base / 简短文案，如“返回列表”→“返回”。
Admin 表格：
<768px：切换为卡片列表展示（isMobile），避免横向滚动。
侧边栏：
大屏：常驻。
小屏：通过按钮切换显示，配合遮罩层。