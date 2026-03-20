# Claw 运行机制

> beta v0.3 | 2026-03-17 | 以代码为准，上下文精确到文件路径

---

## 一、设计逻辑

### 核心隐喻：类人认知

```
人类专家工作时——
  脑子里随时有的：基本原则、世界观           → CLAUDE.md（灵魂，100% 自动加载）
  对搭档的了解：偏好、习惯、踩过的坑        → MEMORY.md（协作记忆，100% 自动加载）
  被叫到某个专业场景时激活的：专业能力全貌    → SKILL.md（触发时 100% 自动加载）
  手边的工具箱：随专业能力配套的专用工具      → tools.py（session 创建时全量注册）
  专业能力的参考书架，需要时翻：             → references/（不自动加载，Read 翻阅）
  下班后写的工作日记，周末整理：             → evolution-log.md（不自动加载，心跳处理）
  跨领域的零散感悟，验证后变成原则：         → worldview.md（不自动加载，心跳提升到灵魂）
```

**「自动加载」是这套系统的核心设计支点**——一切设计围绕「什么在上下文里」展开：

| 可见性 | 文件 | 含义 |
|--------|------|------|
| **始终可见** | `CLAUDE.md` | CC 启动时自动注入，灵魂（身份、原则、通识认知、工具能力指针） |
| **始终可见** | `MEMORY.md` | CC auto memory 索引，协作记忆（用户画像、行为纠正、项目动态） |
| **Session 注册** | `tools.py` | tool_loader 每次 session 创建时扫描注册为 MCP 工具（可选，Skill 不一定有） |
| **触发可见** | `SKILL.md` | 用户输入匹配触发词时，CC 自动将全文注入上下文 |
| **主动翻阅** | `references/` | Agent 执行中通过 Read 工具读取，需被指示或自主决定 |
| **不可见** | `evolution-log.md` | 日常对话时 agent 不知其存在，仅心跳时被指示读取 |
| **不可见** | `worldview.md` | 同上，仅心跳和 RSS 深读时被指示读取 |

前两行是"始终在场"的记忆——CLAUDE.md 是认知层面的（我是谁、我信什么），MEMORY.md 是协作层面的（搭档是谁、怎么配合）。两者共同构成 agent 每次醒来时的"底色"。

### 两层记忆、三条路径

记忆分两层，由 CLAUDE.md 中的判定规则引导 CC 分流：

```
认知记忆（claw/ 内）          ← 删掉后做事的方法/知识变差
  SKILL.md, worldview.md, evolution-log.md, references/
  由心跳维护，CAS prompt 显式指示读写

协作记忆（~/.claude/.../memory/）  ← 删掉后协作方式/自我感知变差
  CC auto memory 系统管理
  MEMORY.md 索引每次会话自动加载，CC 自主判断何时读写

可从代码推导的                → 不存
```

四条进化路径分别沉淀到不同终点：

```
领域学习：外部 → SKILL.md / references/ → evolution-log → 心跳折叠回 SKILL.md
                 改变「怎么做事」                        终点：SKILL.md

工具进化：使用 → [工具反思]/[工具需求] → agent 直接修/造 或 心跳沉淀 → tools.py
                 改变「用什么做事」                      终点：tools.py
                 造/改前必须 Read tool-methodology.md

通识学习：外部 → worldview.md → 心跳验证（≥2来源） → CLAUDE.md ## 通识认知
                 改变「怎么看世界」                   终点：CLAUDE.md

协作学习：对话/心跳 → CC 自主判断 → MEMORY.md
                 改变「怎么协作」                     终点：memory/
```

领域知识归 SKILL.md，不归 memory。心跳和 RSS 学习期间，AI 在维护认知记忆的同时，也自主判断是否需要更新协作记忆（如信息源质量变化、自身状态观察等）。

### 进化哲学

- 进化 = 压缩，不是堆积。信息密度单调递增。
- Skill 是自主体。约束替代编排：只设边界（≤5000字符），不写「先做A再做B」。
- 进化优先级：γ 元认知（怎么想）> δ 规则（怎么做）> α 数据（看什么）
- 认知和工具共同进化：SKILL.md 改变怎么想，tools.py 改变用什么做。造工具的驱动力是输出质量，不是频次。

---

## 二、上下文架构

### CC 上下文注入机制

CAS 创建 agent 时，上下文从**五个独立管道**注入（在 agent 收到 prompt 之前）：

```
管道                        控制方式                    内容
──────────────────────────────────────────────────────────────────
① preset                    system_prompt.preset        CC 基础系统提示（工具、权限、行为规范）
② setting_sources           ["project","user"] / []     CLAUDE.md + Skill 描述 + settings
③ auto memory               CC CLI 自动（独立于②）     MEMORY.md 索引 + 记忆文件
④ append                    system_prompt.append        应用层追加内容（如 heartbeat.md）
⑤ resume                    session_id                  历史对话
```

**关键**：③ auto memory 的加载**不受** `setting_sources` 控制。只要项目路径匹配（`cwd` → `~/.claude/projects/{encoded-path}/memory/`），CC CLI 就自动加载 MEMORY.md。这意味着即使 `setting_sources=[]`（完全隔离），协作记忆仍可能被加载。

### setting_sources 详解

`setting_sources` 决定 CC 自动注入哪些配置和上下文：

```
setting_sources=["project","user"]        → 加载项目级 + 用户级
setting_sources=["project"]               → 仅项目级
setting_sources=[]                        → 完全隔离，仅 system_prompt（但 auto memory 独立）
```

**项目级**（由 cwd 决定，claw 场景下 cwd=`/Users/marvin/antigravity/claw`）：

| 加载项 | 实际路径 | 加载内容 |
|--------|---------|---------|
| 项目 CLAUDE.md | `claw/CLAUDE.md` | 全文（当前内容：身份定义 + `## 通识认知`） |
| 项目 Skill 目录 | `claw/.claude/skills/*/SKILL.md` | **仅 frontmatter 的 description 字段**（非全文！） |

**用户级**（`~/.claude/`）：

| 加载项 | 实际路径 | 加载内容 |
|--------|---------|---------|
| 用户 CLAUDE.md | `~/.claude/CLAUDE.md` | 全文（当前内容：`请一直用中文回复我`） |
| 用户 Skill 目录 | `~/.claude/skills/*/SKILL.md` | **仅 frontmatter 的 description 字段** |

**auto memory**（独立于 setting_sources）：

| 加载项 | 实际路径 | 加载内容 |
|--------|---------|---------|
| 项目 Memory 索引 | `~/.claude/projects/-Users-marvin-antigravity-claw/memory/MEMORY.md` | 全文索引（存在时自动加载） |

**当前实际加载的 Skill 目录**：
```
项目级 skills:  meta-agent, a-stock-agent
用户级 skills:  new-sdk-app, apple-sa-ambient-voice
```
仅描述可见（用于匹配触发词）。命中后 CC 追加该 SKILL.md 全文。同名 skill 优先级：用户级 > 项目级。

---

### 2.1 日常对话

```
用户 Telegram 消息
  │
  ▼
bot.py handle_message()
  │
  ├─ CAS 参数 ─────────────────────────────────────┐
  │  model: opus                                    │
  │  system_prompt: preset claude_code              │
  │  setting_sources: ["project", "user"]           │
  │  permission_mode: bypassPermissions             │
  │  max_turns: 30                                  │
  │  resume: .bot-session                           │
  │  mcp_servers: load_skill_tools()               │
  └─────────────────────────────────────────────────┘
  │
  ├─ CC 自动注入上下文 ────────────────────────────────┐
  │                                                    │
  │  ① claw/CLAUDE.md              身份 + 通识认知      │
  │  ② ~/.claude/CLAUDE.md         "请一直用中文回复我"  │
  │  ③ Skill 目录（仅描述）                             │
  │     meta-agent, a-stock-agent（项目级）             │
  │     new-sdk-app, apple-sa-ambient-voice（用户级）   │
  │  ④ MEMORY.md（auto memory）    协作记忆索引         │
  │  ⑤ resume 历史对话              上一轮对话记忆       │
  └────────────────────────────────────────────────────┘
  │
  │ 用户输入匹配 skill 触发词？
  │ ┌─ YES ──────────────────────────────────────────┐
  │ │  CC 追加该 SKILL.md 全文到上下文                  │
  │ │  Agent 按接线图执行                               │
  │ │  需要时 Read references/*                        │
  │ └──────────────────────────────────────────────────┘
  │ ┌─ NO ───────────────────────────────────────────┐
  │ │  通用对话（基于 CLAUDE.md + resume 历史）         │
  │ └──────────────────────────────────────────────────┘
  │
  │ Agent 执行期间可写入（claw/ 内）：
  │   .claude/skills/{domain}/evolution-log.md  ← [反思]/[知识]/[工具需求]/[工具反思]
  │   .claude/skills/{domain}/SKILL.md          ← 方法修改
  │   .claude/skills/{domain}/tools.py          ← 造/改工具（Read 方法论后）
  │   .claude/skills/{domain}/references/*      ← 参考资料
  │   worldview.md                              ← 跨域洞察
  │
  │ 工具进化（CLAUDE.md 中指示）：
  │   CC 原生不够 → Read tool-methodology.md → 造/改 tools.py
  │   工具出问题 → [工具反思] 写入 evo-log + 可直接修复
  │   下条消息自动生效（tool_loader 重新扫描）
  │
  ▼
bot.py 保存 session_id → .bot-session
分段返回文本给 Telegram（每段 ≤4000 字符）
```

---

### 2.2 心跳

**触发**：bot 自动每 6h / Telegram `/heartbeat` / `python3 heartbeat.py`

```
心跳入口 heartbeat()
  │
  ├──────────────────────┐
  │                      │
  ▼                      ▼
Phase 1: 自检         RSS 学习（独立，见 2.3）
  │                    条件：距上次采集 ≥4h
  │
  action="skip" → 结束
  action="run"  → Phase 2
  │
  ▼
Phase 2: 执行
```

#### Phase 1：自检（只读）

```
heartbeat.py phase1()
  │
  ├─ CAS 参数 ─────────────────────────────────────┐
  │  model: haiku                                   │
  │  system_prompt: preset + APPEND(heartbeat.md)   │
  │  setting_sources: ["project", "user"]           │
  │  disallowed_tools: [Bash,Write,Edit,MultiEdit,  │
  │                     NotebookEdit,WebFetch,       │
  │                     WebSearch,Agent]             │
  │  mcp_servers: {heartbeat: heartbeat_report}     │
  │  permission_mode: bypassPermissions             │
  │  resume: .heartbeat-session                     │
  └─────────────────────────────────────────────────┘
  │
  ├─ CC 自动注入上下文 ────────────────────────────────┐
  │                                                    │
  │  ① claw/CLAUDE.md                                  │
  │  ② ~/.claude/CLAUDE.md                             │
  │  ③ Skill 目录（仅描述）                             │
  │  ④ MEMORY.md（auto memory）                        │
  │  ⑤ heartbeat.md 全文（作为系统提示的一部分）         │
  │  ⑥ resume 历史（若有）                              │
  └────────────────────────────────────────────────────┘
  │
  │ Agent 执行（所有写工具已禁用）：
  │
  │   Glob .claude/skills/*/
  │     │
  │     ├─ Read evolution-log.md
  │     │    统计未处理 [反思] 条目（无 [已处理] 标记）
  │     │    ≥3 条同类 [反思]？
  │     │    统计未处理 [知识] 条目
  │     │    >30天 [已处理] 条目？
  │     │
  │     └─ Read SKILL.md
  │          字符数 >5000？
  │
  │   Read worldview.md
  │     行数 >60？
  │
  │ 综合判断 → 调用 heartbeat_report MCP 工具
  │
  ▼
输出: {
  action: "skip" | "run",
  tasks: "skill_maintenance:meta-agent\nworldview_maintenance"
}
```

#### Phase 2：执行（仅当 action="run"）

```
heartbeat.py phase2(tasks)
  │
  ├─ CAS 参数 ─────────────────────────────────────┐
  │  model: opus                                    │
  │  system_prompt: preset                          │
  │  setting_sources: ["project", "user"]           │
  │  permission_mode: acceptEdits                   │
  │  max_turns: 15                                  │
  │  resume: .heartbeat-session                     │
  │  mcp_servers: load_skill_tools()               │
  │  （共享 Phase 1 的 session → 知道诊断了什么）     │
  └─────────────────────────────────────────────────┘
  │
  ├─ CC 自动注入上下文 ────────────────────────────────┐
  │                                                    │
  │  ① claw/CLAUDE.md                                  │
  │  ② ~/.claude/CLAUDE.md                             │
  │  ③ Skill 目录（仅描述）                             │
  │  ④ MEMORY.md（auto memory）                        │
  │  ⑤ resume 历史（含 Phase 1 完整对话）               │
  └────────────────────────────────────────────────────┘
  │
  │ Prompt（Python 解析 tasks 后构造）：
  │
  │ ┌─ skill_maintenance:{name} ──────────────────────┐
  │ │                                                  │
  │ │  Prompt 注入：                                    │
  │ │    "你是 {name}，维护你的知识体系"                 │
  │ │    Phase 1 的 hints                              │
  │ │                                                  │
  │ │  Agent 自主 Read：                                │
  │ │    .claude/skills/{name}/SKILL.md                │
  │ │    .claude/skills/{name}/evolution-log.md        │
  │ │    .claude/skills/{name}/references/*            │
  │ │                                                  │
  │ │  Agent 自主决定写入：                             │
  │ │    SKILL.md         ← 吸收知识/修改方法/压缩      │
  │ │    references/*     ← 新增参考资料                │
  │ │    evolution-log.md ← 标记[已处理]、裁剪>30天    │
  │ │                                                  │
  │ │  约束：SKILL.md ≤5000字符 且 ≤原长120%           │
  │ └──────────────────────────────────────────────────┘
  │
  │ ┌─ worldview_maintenance ─────────────────────────┐
  │ │                                                  │
  │ │  Agent Read：worldview.md, claw/CLAUDE.md        │
  │ │                                                  │
  │ │  Agent 写入：                                    │
  │ │    worldview.md    ← 压缩到 ≤80 行              │
  │ │    claw/CLAUDE.md  ← ≥2来源印证 → ## 通识认知    │
  │ └──────────────────────────────────────────────────┘
  │
  │ ┌─ tool_maintenance:{name} ─────────────────────────┐
  │ │                                                    │
  │ │  Prompt："你是{name}，审查你的工具集"               │
  │ │  Read tools.py + evolution-log [工具需求]/[工具反思]│
  │ │  Read tool-methodology.md                         │
  │ │  → 沉淀 / 优化 / 淘汰                             │
  │ │  ≥3 同类 [工具反思] = 系统性问题，优先级最高        │
  │ └────────────────────────────────────────────────────┘
  │
  │ ┌─ 协作记忆（AI 自主判断）──────────────────────────┐
  │ │                                                    │
  │ │  心跳期间 AI 可自主更新 auto memory：              │
  │ │    信息源质量变化、自身状态观察等                    │
  │ │  判定依据：CLAUDE.md 中的双层记忆规则              │
  │ └────────────────────────────────────────────────────┘
  │
  ▼
保存 session_id → .heartbeat-session
```

---

### 2.3 RSS 学习管线

**触发**：心跳内自动（距上次 ≥4h）/ Telegram `/feeds` / `python3 heartbeat.py --feeds`

```
heartbeat.py feed_cycle()
  │
  ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Stage 1：采集                                     ┃
┃  执行者：Python（feed_fetcher.py），零 LLM 成本     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  │
  │ 输入文件（Python 直接读取）：
  │   feeds.json          ← RSS 源配置（URL+名称+标签）
  │   .feeds-read-urls    ← 已读 URL 集合
  │   .feeds-fail-counts  ← 连续失败计数
  │
  │ aiohttp 并发拉取 → feedparser 解析
  │ 过滤：URL 去重 + 7天回看 + ≥3次失败跳过
  │
  │ 输出：articles[] 内存对象
  │   每篇: {title, url, summary, source, tags, date}
  │ 副产物：.feeds-new-articles.json, .feeds-last-check, .feeds-fail-counts
  │
  │ 无文章 → 结束
  ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Stage 2：筛选                                     ┃
┃  执行者：CAS sonnet                                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  │
  ├─ CAS 参数 ─────────────────────────────────────┐
  │  model: sonnet                                  │
  │  system_prompt: preset                          │
  │  setting_sources: ["project", "user"]           │
  │  max_turns: 1                                   │
  │  permission_mode: bypassPermissions             │
  │  无 resume（每次独立）                           │
  └─────────────────────────────────────────────────┘
  │
  ├─ Prompt（Python 构造注入）───────────────────────┐
  │                                                    │
  │  文章列表：                                        │
  │    "[0] [Simon Willison] Building LLM apps          │
  │         摘要前 300 字..."                           │
  │  现有 skill 名称列表（Python 扫描目录名）           │
  │  筛选标准 + 返回格式要求                            │
  └────────────────────────────────────────────────────┘
  │
  │ Agent 不读不写任何文件，只返回文本
  │ 输出: "SELECTED: 0, 3, 7" 或 "SELECTED: NONE"
  │ Python 解析索引（上限：首次 10 篇，后续 5 篇）
  │
  │ NONE → mark_as_read(全部) → 结束
  ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Stage 3：深读                                     ┃
┃  执行者：CAS opus                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  │
  ├─ CAS 参数 ─────────────────────────────────────┐
  │  model: opus                                    │
  │  system_prompt: preset                          │
  │  setting_sources: ["project", "user"]           │
  │  allowed_tools: [WebFetch,Read,Write,Edit,      │
  │                  Glob,Grep] + skill 工具名      │
  │  mcp_servers: load_skill_tools()               │
  │  max_turns: 15                                  │
  │  permission_mode: bypassPermissions             │
  │  无 resume（每次独立）                           │
  └─────────────────────────────────────────────────┘
  │
  ├─ CC 自动注入上下文 ────────────────────────────────┐
  │                                                    │
  │  ① claw/CLAUDE.md              身份 + 通识认知      │
  │  ② ~/.claude/CLAUDE.md         "请一直用中文回复我"  │
  │  ③ Skill 目录（仅描述）                             │
  │  ④ MEMORY.md（auto memory）    协作记忆索引         │
  └────────────────────────────────────────────────────┘
  │
  │ Prompt（Python 构造）包含：
  │   选中文章的 {title, source, URL, tags}
  │   现有 skill 列表 + 目录路径
  │   处置选项 + 约束声明
  │
  │ Agent 执行：
  │
  │   1. 先了解自己（Read）：
  │      .claude/skills/*/SKILL.md       ← 各领域当前认知
  │      .claude/skills/*/references/*   ← 已有参考资料
  │      worldview.md                    ← 跨域通识认知
  │
  │   2. 获取文章（WebFetch）：
  │      每篇 URL → HTTP 抓取全文
  │
  │   3. 对每篇文章自主决定（Write/Edit）：
  │      ┌──────────────────────────────────────────┐
  │      │ 改变方法 → Write SKILL.md                 │
  │      │ 参考资料 → Write references/{filename}.md │
  │      │ 跨域洞察 → Write worldview.md "活跃洞察"  │
  │      │ 丢弃     → 不写入                        │
  │      └──────────────────────────────────────────┘
  │
  │ 约束：
  │   SKILL.md ≤5000 字符，≤原长 120%
  │   references/ 每文件 ≤200 行
  │   worldview.md 总长 ≤80 行
  │
  ▼
正常完成 → Python mark_as_read(全部文章) → .feeds-read-urls
异常 → 不标记已读，下次重试
```

---

### 2.4 降秩（造新 skill）

```
日常对话中用户说"造XX智能体"/"降秩"
  │
  ▼
同 2.1 日常对话流程（CAS opus）
  │
  │ 用户输入匹配 meta-agent/SKILL.md description 中的触发词
  │   → CC 自动追加 meta-agent/SKILL.md 全文到上下文
  │
  │ Agent 按 SKILL.md 接线图执行降秩四步：
  │   需要时 Read references/skill-template.md
  │   需要时 Read references/evolution-log-template.md
  │
  │ M3 工具评估：
  │   "CC 原生能否达到这个 skill 应有的输出质量？"
  │   能 → 不造 tools.py
  │   不能 → Read tool-methodology.md → 造 tools.py + tool-spec.md
  │
  │ 产出：
  │   .claude/skills/{name}/SKILL.md          ← 接线图
  │   .claude/skills/{name}/evolution-log.md  ← 空模板
  │   .claude/skills/{name}/references/       ← 空目录
  │   .claude/skills/{name}/tools.py          ← 可选（工具评估判定需要时）
  │   .claude/skills/{name}/references/tool-spec.md  ← 可选（工具需求声明）
  │
  ▼
下条消息 CC 自动发现新 skill + tool_loader 注册新工具
```

---

## 三、知识流向总图

```
                    外部世界
                 ╱            ╲
       RSS feeds                对话/MCP
       (feeds.json)             (Telegram)
            │                       │
  ┌──────────┼───────────┐          │
  │ Stage 1 采集(Python)  │          │
  │ Stage 2 筛选(sonnet)  │          │
  │ Stage 3 深读(opus)    │          │
  └──────────┼───────────┘          │
            │                       │
            ▼                       ▼
  ┌──────────────────────────────────────────┐
  │            SKILL.md（领域知识终点）         │
  │  方法接线图 + 核心知识  ≤5000字符          │
  │  CC 触发时 100% 自动加载                   │
  └────────────┬─────────────────────────────┘
               │
               │ 日常工作时写入 [反思]/[知识]/[工具需求]/[工具反思]
               ▼
  ┌──────────────────────────────────────────┐
  │       evolution-log.md（缓冲区）           │
  │  不自动加载，心跳时被 Read                  │
  └────────────┬─────────────────────────────┘
               │ 心跳 Phase 2
               │
               ├─ skill_maintenance
               │    ≥3同类反思 → 修改方法
               │    知识 → 吸收/放references/丢弃
               │    → 回到 SKILL.md（认知闭环）
               │
               └─ tool_maintenance
                    [工具需求] → Read 方法论 → 造 tools.py
                    [工具反思] → Read 方法论 → 改 tools.py
                    ≥3同类工具反思 = 系统性问题，优先级最高
                    长期未用 → 淘汰
                    → 回到 tools.py（工具闭环）


  ┌──────────────────────────────────────────┐
  │          tools.py（Skill 专属工具）        │
  │  ≤3000字符 ≤5个  tool_loader 注册        │
  │  可选，Skill 不一定有                     │
  └────────────┬─────────────────────────────┘
               │
               │ 日常使用中：
               │   工具出问题 → [工具反思] → evo-log
               │   发现新需求 → [工具需求] → evo-log
               │   紧急修复 → Read 方法论 → 直接改 tools.py
               │   下条消息自动生效
               │
               │ 造/改工具前必须 Read tool-methodology.md
               │   七原则：结果导向、少即是多、参数防呆、
               │   语义化返回、错误即教学、描述清晰、多步用代码
               ▼
          回到 evolution-log（进化闭环）


  ┌──────────────────────────────────────────┐
  │       worldview.md（跨域洞察暂存）         │
  │  ≤80行  不自动加载                         │
  │  RSS 深读 + 日常对话写入                    │
  └────────────┬─────────────────────────────┘
               │ 心跳 worldview_maintenance
               │ ≥2 独立来源印证
               ▼
  ┌──────────────────────────────────────────┐
  │     CLAUDE.md ## 通识认知（灵魂终点）       │
  │  ≤20行  每次会话 100% 自动加载              │
  └──────────────────────────────────────────┘


  辅助存储：
    references/           SKILL.md 可索引引用，不自动加载
    evolution-log.md      中转缓冲，处理完即裁剪


  ┌──────────────────────────────────────────┐
  │    协作记忆（CC auto memory）              │
  │  ~/.claude/projects/.../memory/           │
  │  MEMORY.md 索引  每次会话自动加载          │
  │  CC 自主判断何时读写                       │
  └────────────┬─────────────────────────────┘
               │
               │ 写入来源（AI 自主判断）：
               │   日常对话 — 用户偏好、行为纠正、项目动态
               │   心跳/RSS — 信息源质量变化、自身状态观察
               │
               │ 判定规则（CLAUDE.md 定义）：
               │   删掉后做事变差 → 认知记忆（claw/）
               │   删掉后协作变差 → 协作记忆（memory/）
               │   可从代码推导   → 不存
               │
               │ 四种类型：
               │   user     — 用户画像（角色、偏好、知识背景）
               │   feedback — 行为纠正（用户对 AI 行为的修正）
               │   project  — 项目动态（进行中的工作、决策）
               │   reference — 外部资源指针
               ▼
          融入日常对话上下文（自动加载）
```

---

## 四、边界约束

| 文件 | 上限 | 策略 |
|------|------|------|
| SKILL.md | ≤5000 字符，≤原长 120% | 删旧腾新，信息密度单调递增 |
| tools.py | ≤3000 字符，≤5 个工具 | 参数扁平，枚举用 Literal，错误消息含修正建议 |
| evolution-log.md | 无硬上限 | [已处理] >30天可裁剪；标签：[反思]/[知识]/[工具需求]/[工具反思] |
| worldview.md | ≤80 行 | 心跳压缩 + 提升 |
| CLAUDE.md 通识 | ≤20 行 | ≥2 来源印证 |
| references/ | 每文件 ≤200 行 | 写入者自约束 |

**写入边界**：认知记忆写入 `claw/` 内，协作记忆写入 `~/.claude/projects/.../memory/`（CC auto memory 管理）。

---

## 五、模型分配

| 场景 | 模型 | 上下文隔离 | Skill 工具 |
|------|------|-----------|-----------|
| 日常对话 | **opus** | project+user | ✓ 全量注入 |
| Phase 1 自检 | haiku | project+user，写工具禁用 | ✗ |
| Phase 2 执行 | **opus** | project+user，acceptEdits | ✓ 全量注入 |
| RSS Stage 2 筛选 | **sonnet** | project+user | ✗ |
| RSS Stage 3 深读 | **opus** | project+user，白名单 | ✓ 追加到白名单 |
| 降秩 | opus（同日常对话） | project+user | ✓ 全量注入 |

---

## 六、Session 机制

```
.bot-session        ← 日常对话 session_id，跨消息连续
                      每条消息 resume 上一条，提供对话记忆
                      /reset 删除此文件

.heartbeat-session  ← 心跳 session_id，Phase 1 和 Phase 2 共享
                      Phase 2 resume Phase 1 → 知道诊断了什么
                      跨心跳轮次保持记忆

RSS Stage 2/3       ← 无 session，每次独立执行
```

---

## 七、待解决问题

### 7.1 工具层（已实现方案 A，方案 B 备选）

**已实现（方案 A：SDK MCP 全量预注册）**：
- Skill 可在目录内放 `tools.py`，定义 `@tool` 装饰的函数 + `TOOLS` 注册表
- `tool_loader.py` 每次创建 CAS session 时扫描所有 skill 的 tools.py，动态 import 并注册为进程内 SDK MCP server
- 日常对话、Phase 2、RSS Stage 3 均注入所有 skill 工具
- 心跳 Phase 1 检查 tools.py 健康度，Phase 2 处理 `tool_maintenance` 任务
- 工具设计方法论见 `meta-agent/references/tool-methodology.md`
- 缺点：全量加载，工具多了浪费上下文（当前 ≤25 工具约 2000 token，可忽略）

**备选（方案 B：Skill → fork → Subagent + mcpServers）**：
- CC 原生支持：SKILL.md frontmatter `context: fork` + `agent: xxx` 指向 subagent
- Subagent frontmatter 支持 `mcpServers` 字段，声明 stdio/sse/http 类型的 MCP server
- 效果：skill 触发 → 启动子 agent → MCP 仅在子 agent 运行期间加载 → 完成后断开
- 真正的按需加载，零常驻成本
- 缺点：走 stdio 有 IPC 开销；子 agent 与主对话隔离（fork）；工具需作为独立进程运行
- 适合时机：当 skill 数量和工具数量增长到全量预注册成本不可忽略时迁移

**备选（方案 C：CLI-first，MCP 仅特殊场景）**：
- 核心思路：agent 通过 Bash 调用 CLI 工具和 `python -c` 一行脚本，替代自建 MCP
- 数据支撑（Scalekit 75 次基准测试）：CLI 比 MCP 省 20-32 倍 token，可靠性 100% vs 72%
- Anthropic 实测：代码执行模式比 MCP 工具调用省 98.7% token
- LLM 天然擅长写 shell 命令（训练数据中有数百万行真实 CLI 用法），不擅长 tool calling（仅有少量合成样本）
- 示例：`python -c "import akshare as ak; print(ak.stock_zh_a_hist(symbol='000001').to_csv())"`
- 优势：零上下文成本、本地执行 100% 可靠、Python 生态无限可用（pip install 即用）、Unix pipe 天然可组合
- MCP 仅保留用于：(a) 多租户 OAuth 认证 (b) 需要实时推送的有状态连接 (c) 无 CLI 无 Python 库的纯 SaaS 服务
- 落地方式：SKILL.md 中写清数据获取的 Bash/Python 命令模式，agent 自行组合执行
- 参考：Cloudflare Code Mode、Anthropic Code Execution with MCP、"Build CLIs First, Wrap as MCPs Second"

### 7.2 系统评估

如何评价认知系统效果？

核心假设：
- SKILL.md 是认知唯一可靠载体
- 进化通过压缩实现，信息密度单调递增
- skill 是自主体，约束替代编排

难点：
- 认知质量无法简单量化
- 进化效果需长周期观察
- 「信息密度」如何度量？
- 如何区分「学到有用的」和「过拟合 RSS 偏见」？

### 7.3 协作记忆（已确定方案）

设计已确定：协作记忆交给 CC auto memory 系统，路径 `~/.claude/projects/-Users-marvin-antigravity-claw/memory/`。CLAUDE.md 中定义了双层记忆的判定规则，引导 CC 自主分流。

当前状态：memory 目录尚未创建，随使用自然积累。CC 在对话和心跳中自主判断何时写入。
