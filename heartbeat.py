#!/usr/bin/env python3
"""心跳引擎 — 定期自检和学习

用法:
  python3 heartbeat.py          # 运行一次心跳（含 RSS 学习）
  python3 heartbeat.py --dry    # 只跑 Phase 1（不执行任务）
  python3 heartbeat.py --feeds  # 只跑 RSS 学习（跳过自检）
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 清理 CC 嵌套检测环境变量（允许从 CC 会话内启动 CAS 子进程）
for key in [k for k in os.environ if k.startswith("CLAUDE")]:
    del os.environ[key]

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    tool,
)
from tool_loader import load_skill_tools, get_tool_names

# ── 路径 ──

CLAW_DIR = Path(__file__).parent
SKILLS_DIR = CLAW_DIR / ".claude" / "skills"
HEARTBEAT_MD = CLAW_DIR / "heartbeat.md"
WORLDVIEW_MD = CLAW_DIR / "worldview.md"
PROJECT_CLAUDE_MD = CLAW_DIR / "CLAUDE.md"
SESSION_FILE = CLAW_DIR / ".heartbeat-session"
NEW_ARTICLES_FILE = CLAW_DIR / ".feeds-new-articles.json"
LAST_CHECK_FILE = CLAW_DIR / ".feeds-last-check"

FEED_CHECK_INTERVAL_HOURS = 4


# ── Phase 1 结果收集（MCP 工具） ──

_phase1_result: dict = {"action": "skip", "tasks": ""}


@tool(
    "heartbeat_report",
    "报告心跳自检结果",
    {
        "action": str,      # "skip" 或 "run"
        "tasks": str,        # 任务列表，每行一个（所有 skill 相关的 hints 统一放这里）
    },
)
async def heartbeat_report(args: dict):
    global _phase1_result
    _phase1_result = {
        "action": args.get("action", "skip"),
        "tasks": args.get("tasks", ""),
    }
    return {"content": [{"type": "text", "text": f"已报告: {args['action']}"}]}


# ── 工具函数 ──

_log_callback = None

def set_log_callback(cb):
    global _log_callback
    _log_callback = cb

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[heartbeat {ts}] {msg}"
    print(line)
    if _log_callback:
        _log_callback(line)


def load_session_id() -> str | None:
    if SESSION_FILE.exists():
        sid = SESSION_FILE.read_text().strip()
        return sid if sid else None
    return None


def save_session_id(sid: str):
    SESSION_FILE.write_text(sid)


async def run_cas(client: ClaudeSDKClient, prompt: str) -> tuple[str, str | None]:
    """发送 prompt 并收集响应，返回 (文本, session_id)"""
    texts: list[str] = []
    session_id = None

    await client.query(prompt)
    async for msg in client.receive_response():
        if msg is None:
            continue
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    texts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    log(f"  工具: {block.name}")
        elif isinstance(msg, ResultMessage):
            session_id = msg.session_id
            log(f"  轮次={msg.num_turns} 费用=${msg.total_cost_usd:.4f}")

    return "\n".join(texts), session_id


def needs_feed_check() -> bool:
    """是否需要采集 RSS"""
    if not LAST_CHECK_FILE.exists():
        return True
    try:
        last_ts = float(LAST_CHECK_FILE.read_text().strip())
        hours_since = (time.time() - last_ts) / 3600
        return hours_since >= FEED_CHECK_INTERVAL_HOURS
    except ValueError:
        return True


# ── Phase 1：自检 ──

async def phase1() -> dict:
    """轻量自检（haiku），读取文件判断，不改任何东西"""
    global _phase1_result
    _phase1_result = {"action": "skip", "tasks": ""}

    checklist = HEARTBEAT_MD.read_text(encoding="utf-8")
    session_id = load_session_id()

    heartbeat_mcp = create_sdk_mcp_server(
        name="heartbeat",
        version="1.0.0",
        tools=[heartbeat_report],
    )

    options = ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": checklist,
        },
        setting_sources=["project", "user"],
        cwd=str(CLAW_DIR),
        model="haiku",
        max_turns=10,
        mcp_servers={"heartbeat": heartbeat_mcp},
        disallowed_tools=[
            "Bash", "Write", "Edit", "MultiEdit", "NotebookEdit",
            "WebFetch", "WebSearch", "Agent",
        ],
        permission_mode="bypassPermissions",
    )
    if session_id:
        options.resume = session_id

    log("Phase 1 开始（haiku）")
    async with ClaudeSDKClient(options=options) as client:
        text, new_sid = await run_cas(client, "执行心跳自检。")

    if new_sid:
        save_session_id(new_sid)

    log(f"Phase 1 结果: {_phase1_result['action']}")
    if _phase1_result["tasks"]:
        log(f"  任务: {_phase1_result['tasks'][:200]}")

    return _phase1_result


# ── Phase 2：执行任务 ──

async def phase2(tasks: str) -> str:
    """执行心跳任务（opus）：skill 自维护 + 通用维护"""
    session_id = load_session_id()

    # 解析任务，区分 skill 自维护和通用维护
    skill_tasks: dict[str, list[str]] = {}  # skill_name -> [hints]
    generic_tasks: list[str] = []

    tool_tasks: dict[str, list[str]] = {}  # skill_name -> [hints]

    for line in tasks.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("tool_maintenance:"):
            _, skill_name = line.split(":", 1)
            tool_tasks.setdefault(skill_name.strip(), []).append(line)
        elif ":" in line and not line.startswith("cleanup_memory") and not line.startswith("worldview_maintenance"):
            # skill 相关任务: "consolidate_knowledge:investment" 等
            task_type, skill_name = line.split(":", 1)
            skill_tasks.setdefault(skill_name.strip(), []).append(task_type.strip())
        else:
            generic_tasks.append(line)

    prompts: list[str] = []

    # Skill 自维护 prompt
    for skill_name, hints in skill_tasks.items():
        hints_text = "\n".join(f"- {h}" for h in hints)
        prompts.append(f"""你是 {skill_name}，维护和进化你的知识体系。

心跳发现的问题提示：
{hints_text}

你有完全自主权决定如何改造自己的 SKILL.md、references/、evolution-log.md。

操作步骤：
1. 先 Read 你的所有文件了解自己当前状态（{SKILLS_DIR}/{skill_name}/）
2. 处理 evolution-log 中未处理的条目：
   - [知识] 条目：值得改变方法的 → 吸收进 SKILL.md；参考性的 → 放 references/；不重要的 → 丢弃
   - [反思] 条目（≥3 条同类说明方法有缺陷）：分析共同模式，修改 SKILL.md
     优先级：γ 元认知（改思考方式）> δ 规则（增删步骤）> α 数据（更新参数）
3. SKILL.md 过大时：删旧腾新，压缩精炼，信息密度单调递增
4. 处理完成后将对应 evolution-log 条目标记 [已处理] 或 [已固化]

约束：
- SKILL.md ≤ 5000 字符，修改后 ≤ 原长 120%
- references/ 每文件 ≤ 200 行
- evolution-log.md 中 [已处理]/[已固化] 且 >30 天的条目可删除
""")

    # 工具维护 prompt
    for skill_name, hints in tool_tasks.items():
        hints_text = "\n".join(f"- {h}" for h in hints)
        prompts.append(f"""你是 {skill_name}，审查和维护你的工具集。

心跳发现的问题提示：
{hints_text}

操作步骤：
1. Read {SKILLS_DIR}/{skill_name}/tools.py 了解当前工具
2. Read {SKILLS_DIR}/{skill_name}/evolution-log.md 中 [工具需求] 和 [工具反思] 条目
3. Read {SKILLS_DIR}/meta-agent/references/tool-methodology.md 了解工具设计方法论
4. 自主决定：
   - 沉淀：[工具需求] → 按方法论创建/追加 tools.py
   - 优化：[工具反思] → 修复报错、改进错误消息、参数防呆、提升数据质量
     ≥3 条同类 [工具反思] 指向同一工具 = 系统性问题，优先级最高
   - 淘汰：长期未使用或 CC 原生工具已可替代的 → 删除
5. 标记 evolution-log 条目为 [已处理]

约束：
- tools.py ≤ 3000 字符，≤ 5 个工具
- 参数扁平，禁止 dict 类型，枚举用 Literal
- 每个工具必须有 docstring
- 必须有 TOOLS = [...] 注册表
- 修改后确保 Python 语法正确
""")

    # 通用维护 prompt
    for task in generic_tasks:
        if task.startswith("worldview_maintenance"):
            prompts.append(f"""维护通识认知：
1. 读取 {WORLDVIEW_MD}
2. 压缩"活跃洞察"部分，合并相似条目，控制总长 ≤ 80 行
3. 将有 ≥2 个独立来源印证的洞察提升到 {PROJECT_CLAUDE_MD} 的"## 通识认知" section（≤ 20 行）
4. 已提升的洞察从"活跃洞察"移到"已提升到 CLAUDE.md"部分
""")

    combined_prompt = "\n\n---\n\n".join(prompts)

    skill_tools = load_skill_tools()
    options = ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
        },
        setting_sources=["project", "user"],
        cwd=str(CLAW_DIR),
        model="opus",
        max_turns=15,
        permission_mode="acceptEdits",
        mcp_servers=skill_tools if skill_tools else None,
    )
    if session_id:
        options.resume = session_id

    log(f"Phase 2 开始（opus）工具: {list(skill_tools.keys()) if skill_tools else '无'}")
    async with ClaudeSDKClient(options=options) as client:
        text, new_sid = await run_cas(client, combined_prompt)

    if new_sid:
        save_session_id(new_sid)

    log("Phase 2 完成")
    return text


# ── RSS 学习：三阶段漏斗 ──

async def feed_cycle():
    """RSS 学习周期：采集 → 筛选 → 深读"""

    # ── Stage 1：采集（Python，不用 LLM）──
    log("RSS Stage 1: 采集")
    from feed_fetcher import run as fetch_feeds, mark_as_read
    articles = await fetch_feeds()

    if not articles:
        log("RSS Stage 1: 无新文章")
        return

    log(f"RSS Stage 1: {len(articles)} 篇新文章")
    for i, a in enumerate(articles):
        log(f"  [{i}] [{a['source']}] {a['title'][:80]}")

    # ── Stage 2：筛选（sonnet）──
    log("RSS Stage 2: 筛选")

    # 构造文章列表（title + 完整摘要 + source）
    article_list = "\n".join(
        f"[{i}] [{a['source']}] {a['title']}\n    {a['summary'] or '（无摘要）'}"
        for i, a in enumerate(articles)
    )

    # 获取现有 skill 信息
    skill_names = []
    if SKILLS_DIR.exists():
        for d in SKILLS_DIR.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                skill_names.append(d.name)

    max_deep_read = 10 if not load_session_id() else 5  # 首次多读点，后续控制成本

    triage_prompt = f"""以下是最新的技术博客文章列表。请筛选出最值得深入阅读的文章。

筛选标准（严格执行，宁缺毋滥）：
- 包含方法论、架构设计、深度技术分析（不是新闻快讯、产品发布、周报）
- 与以下领域相关优先：{', '.join(skill_names) if skill_names else '通用技术'}
- 可能改变或补充现有认知的新观点

当前 skill 领域：{', '.join(skill_names) if skill_names else '暂无领域 skill，选通用技术洞察'}

文章列表：
{article_list}

请只返回值得深读的文章编号（有几篇选几篇，不凑数，上限 {max_deep_read} 篇）：
SELECTED: 0, 3, 7
（如果没有值得深读的，返回 SELECTED: NONE）
"""

    options = ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
        },
        setting_sources=["project", "user"],
        cwd=str(CLAW_DIR),
        model="sonnet",
        max_turns=1,
        permission_mode="bypassPermissions",
    )

    async with ClaudeSDKClient(options=options) as client:
        triage_text, _ = await run_cas(client, triage_prompt)

    # 解析筛选结果
    log(f"RSS Stage 2: sonnet 原始输出: {triage_text[:200]}")
    selected_indices = _parse_selected(triage_text, len(articles), limit=max_deep_read)
    if not selected_indices:
        log("RSS Stage 2: 无值得深读的文章")
        # 没有值得深读的，但采集到的文章不需要下次再看
        mark_as_read(articles)
        return

    selected = [articles[i] for i in selected_indices]
    log(f"RSS Stage 2: 选中 {len(selected)} 篇:")
    for a in selected:
        log(f"  - [{a['source']}] {a['title'][:60]}")

    # ── Stage 3：深读（opus，提取知识）──
    log("RSS Stage 3: 深读")

    articles_for_read = "\n\n".join(
        f"## 文章 {i+1}: {a['title']}\n来源: {a['source']}\nURL: {a['url']}\n标签: {', '.join(a.get('tags', []))}\n摘要: {a['summary'] or '（无摘要，需 WebFetch 全文）'}"
        for i, a in enumerate(selected)
    )

    today = datetime.now().strftime("%Y-%m-%d")

    # 构造 skill 自述（让 agent "成为"最相关的 skill）
    skill_context = ""
    for sn in skill_names:
        skill_md = SKILLS_DIR / sn / "SKILL.md"
        if skill_md.exists():
            skill_context += f"\n### {sn}\n已有 SKILL.md、references/\n"

    deep_read_prompt = f"""你是一个自主学习的 skill 系统。先了解自己，再处理文章。

## 第一步：了解自己

读取以下文件了解你当前的知识状态：
- 每个 skill 的 SKILL.md（你的方法论和知识，**唯一保证被加载的文件**）
- 每个 skill 的 references/（参考资料）
- {WORLDVIEW_MD}（跨域通识认知）

现有 skill：{', '.join(skill_names) if skill_names else '无'}
skill 目录: {SKILLS_DIR}

## 第二步：逐篇处理文章

用 WebFetch 获取每篇文章全文，然后**自主决定**每篇文章的处置：

1. **改变方法** → 直接修改 SKILL.md（改进接线图、增删规则、更新认知框架）
   这是最高价值的学习——改变"怎么做事"。

2. **参考资料**（代码示例、详细教程、数据表、案例）→ 写入 references/{{filename}}.md
   SKILL.md 中可索引引用。

3. **跨域洞察**（不属于任何现有 skill 但有价值的通识认知）→ 写入 {WORLDVIEW_MD} 的"活跃洞察"部分

4. **丢弃** — 内容浅薄、重复已知、或不值得保留

## 约束

- SKILL.md ≤ 5000 字符，修改后 ≤ 原长 120%（要加新的就删旧的，信息密度单调递增）
- references/ 每文件 ≤ 200 行
- worldview.md 总长 ≤ 80 行（写入前先检查行数）
- 无匹配 skill 的洞察归 meta-agent 或 worldview.md

## 文章列表

{articles_for_read}
"""

    skill_tools = load_skill_tools()
    options = ClaudeAgentOptions(
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
        },
        setting_sources=["project", "user"],
        cwd=str(CLAW_DIR),
        model="opus",
        max_turns=15,
        allowed_tools=[
            "WebFetch", "Read", "Write", "Edit", "Glob", "Grep",
        ] + get_tool_names(),
        permission_mode="bypassPermissions",
        mcp_servers=skill_tools if skill_tools else None,
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            result, _ = await run_cas(client, deep_read_prompt)

        log(f"RSS Stage 3: opus 输出: {result[:300]}")
        mark_as_read(articles)
        log("RSS Stage 3: 深读完成，已标记已读")
    except Exception as e:
        log(f"RSS Stage 3: 异常 - {e}，不标记已读，下次重试")


def _parse_selected(text: str, max_idx: int, limit: int = 10) -> list[int]:
    """从 LLM 输出中解析 SELECTED: 0, 3, 7 格式"""
    for line in text.splitlines():
        if "SELECTED:" in line.upper():
            part = line.split(":", 1)[1].strip()
            if "NONE" in part.upper():
                return []
            indices = []
            for token in part.replace(",", " ").split():
                try:
                    idx = int(token.strip())
                    if 0 <= idx < max_idx:
                        indices.append(idx)
                except ValueError:
                    continue
            return indices[:limit]
    return []


# ── 主流程 ──

async def heartbeat():
    """执行一次完整心跳"""
    log("=== 心跳开始 ===")

    # Phase 1: 自检
    try:
        result = await phase1()
    except Exception as e:
        log(f"Phase 1 失败: {e}")
        return

    # Phase 2: 执行自检任务（skill 自维护含进化）
    if result["action"] != "skip" and result["tasks"].strip():
        try:
            await phase2(result["tasks"])
        except Exception as e:
            log(f"Phase 2 失败: {e}")

    # RSS 学习（独立于 Phase 1/2）
    if needs_feed_check():
        try:
            await feed_cycle()
        except Exception as e:
            log(f"RSS 学习失败: {e}")
    else:
        log("RSS: 距上次采集不足 4 小时，跳过")

    log("=== 心跳结束 ===")


async def main():
    if "--dry" in sys.argv:
        log("dry run 模式，只执行 Phase 1")
        result = await phase1()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif "--feeds" in sys.argv:
        log("仅执行 RSS 学习")
        await feed_cycle()
    else:
        await heartbeat()


if __name__ == "__main__":
    asyncio.run(main())
