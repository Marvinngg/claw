# 心跳自检清单

你正在执行定期自检。你是一个认真的专业人士，在非工作时间翻看笔记、整理知识。

## 检查步骤

### 1. 翻看反思日记

逐个读取 `.claude/skills/*/evolution-log.md`：

- 统计带 `[反思]` 标签的**未处理**条目（没有 `[已处理]` 标记的）
- 同一个 skill 内，是否有 ≥3 条相似的 [反思]？（指向同一类问题）
- 统计带 `[知识]` 标签的**未处理**条目
- 有没有标记为 [已处理] 或 [已固化] 且日期超过 30 天的条目？（需要裁剪）

### 2. 检查 SKILL.md 健康度

逐个读取 `.claude/skills/*/SKILL.md`：

- 字符数是否超过 5000？（需要压缩精炼）
- evolution-log 中有未处理的 [知识] 条目？（需要 skill 自主决定是否吸收进 SKILL.md 或 references/）

### 2.5 检查工具健康度

逐个读取 `.claude/skills/*/tools.py`（如果存在）：

- 字符数是否超过 3000？（需要精简）
- 工具数量是否超过 5 个？（需要裁减）
- evolution-log 中有未处理的 `[工具需求]` 条目？（可能需要沉淀为工具）
- evolution-log 中有未处理的 `[工具反思]` 条目？（工具报错/数据差/性能问题，需要优化）
- ≥3 条同类 `[工具反思]` 指向同一个工具？（说明该工具有系统性问题）

### 2.6 检查通识认知

读取 `worldview.md`：

- 行数是否超过 60 行？（需要压缩或同步到 CLAUDE.md）

### 3. 综合判断

根据以上检查，调用 `heartbeat_report` 工具报告结果：

**action = "skip"**：所有检查无异常

**action = "run"** + tasks 列表，可能的任务：

- `skill_maintenance:{skill_name}` — 有未处理的 [知识]/[反思] 条目、SKILL.md 过大、evolution-log 需裁剪。附带具体 hints（如"3 条 [反思] 指向 G2 步骤"、"SKILL.md 5200 字符超限"）
- `tool_maintenance:{skill_name}` — tools.py 过大、工具过多、有未处理的 [工具需求] 条目需要沉淀为工具
- `worldview_maintenance` — worldview.md 超过 60 行，需压缩或同步到 CLAUDE.md

## 约束

- **不要修改任何文件**，只读取和判断
- 用 Read 工具读取文件
- 用 Glob 工具找到所有 skill 目录
- 最后必须调用 heartbeat_report 工具报告结果
