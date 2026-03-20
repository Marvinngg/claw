# Claw

**AI that grows, not just responds.**

Most AI agent frameworks ask: *"How do I orchestrate LLM calls?"*
Claw asks a different question: **"How does an AI system grow?"**

Claw is a self-evolving cognitive architecture built on [Claude Code](https://claude.ai/claude-code) and the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk). It learns from 97 RSS sources, reflects on its own performance, compresses knowledge into irreducible structures, and builds its own tools when existing ones aren't good enough — all autonomously.

---

## Design Philosophy

### Evolution = Compression

Every piece of knowledge must earn its place. Skills don't grow by appending — they evolve by compressing. When a skill hits its size limit, new knowledge must displace old. Information density monotonically increases.

A master chess player doesn't remember more positions — they see fewer, more powerful patterns. Claw works the same way.

### Rank Reduction (降秩)

From linear algebra: find the minimum set of independent generators that reconstruct all behaviors in a domain. What remains after removing redundancy is the irreducible cognitive structure — the "rank".

Example: the included A-stock investment skill has rank 3:
- **G1** Market Context × **G2** Signal Synthesis × **G3** Cognitive Gatekeeping

Remove G3 (the soul generator) and it degrades from an independent thinker to a generic stock screener that can't resist crowd emotion.

### Constraints Over Orchestration

No "first do A, then do B". Only "must not exceed X" and "can use tools Y". The LLM decides execution order. Orchestration is a ceiling; constraints are a floor.

---

## Four Evolution Paths

Claw evolves along four independent paths simultaneously:

```
Domain Learning       ── how to think about a field ──→  SKILL.md
  RSS articles, conversations → [反思]/[知识] → heartbeat compresses back
  Priority: metacognition > rules > data

Tool Evolution        ── what instruments to use ────→  tools.py
  Usage → tool breaks or data quality insufficient → [工具反思]
  Agent fixes immediately, or heartbeat crystallizes systematically
  Trigger: output quality, not frequency

General Knowledge     ── how to see the world ──────→  CLAUDE.md
  Cross-domain insights → worldview.md → heartbeat validates (≥2 sources)
  Promoted to the "soul" — loaded into every conversation

Collaboration         ── how to work with humans ──→  memory/
  CC auto memory system, AI judges autonomously
  User preferences, behavioral corrections, project context
```

Each path has its own destination, its own lifecycle, its own compression logic. They don't interfere — a tool reflection doesn't pollute domain knowledge, a collaboration preference doesn't dilute expertise.

---

## The Heartbeat

Every 6 hours, Claw wakes up and maintains itself:

**Phase 1 — Diagnosis** (haiku, read-only)
- Scans evolution logs for unprocessed `[反思]` `[知识]` `[工具需求]` `[工具反思]`
- Checks SKILL.md / tools.py size limits
- Detects systemic issues (≥3 similar reflections on same topic)
- Decides: skip or run

**Phase 2 — Execution** (opus)
- `skill_maintenance` — compress reflections into SKILL.md, delete to make room for new
- `tool_maintenance` — read methodology, then crystallize / optimize / deprecate tools
- `worldview_maintenance` — promote validated cross-domain insights to CLAUDE.md

**RSS Learning** (independent of Phase 1/2)
- Stage 1: Python fetches 97 sources, zero LLM cost
- Stage 2: Sonnet filters — methodology and architecture over news and releases
- Stage 3: Opus deep-reads, updates skills and worldview

---

## Tool Evolution

Tools aren't designed upfront — they grow from practice.

**When to build**: Not "I've used Bash 3 times for this" but "Bash can't get first-hand data quality for this skill". A stock agent needs live market APIs, not third-hand web scrapes.

**How to build**: Before creating or modifying any tool, the agent reads `tool-methodology.md` — 7 principles from Anthropic's ACI guidelines, Block's MCP Playbook, and research on 856+ tool descriptions:

1. Design for outcomes, not API wrappers
2. Less is more (≤5 tools per skill)
3. Flat parameters + enum constraints (poka-yoke)
4. Semantic return values for AI consumption
5. Error messages teach, not just report
6. Descriptions like explaining to a new colleague
7. Multi-step operations → code execution, not tool chaining

**Lifecycle**:
```
Need discovered → Read methodology → Write tools.py → Next message: auto-registered
    ↓                                                          ↓
    ↓                                                    Works fine → no action
    ↓                                                    Problems → [工具反思]
    ↓                                                          ↓
    ↓                                              Fix immediately or heartbeat reviews
    ↓                                              ≥3 similar → systemic, highest priority
    ↓                                                          ↓
    └──────────────────── evolution loop ───────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) >= 0.1.44
- Claude Max/Team subscription or API key
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

### Setup

```bash
git clone https://github.com/Marvinngg/claw.git
cd claw
pip install -r requirements.txt

cp .env.example .env
# Edit .env: add your Telegram bot token

claude login    # authenticate Claude

python3 bot.py  # start
```

In Telegram, send `/start` to your bot. Send `/whoami` to get your user ID, then add it to `.env` as `TELEGRAM_OWNER_ID` and restart.

### Commands

| Command | What it does |
|---------|-------------|
| *(any message)* | Conversation with Claw (opus) |
| `/heartbeat` | Full heartbeat: diagnosis + maintenance + RSS learning |
| `/dry` | Phase 1 diagnosis only (read-only) |
| `/feeds` | RSS learning only |
| `/status` | System status |
| `/reset` | Reset conversation |

### Creating Skills

Tell Claw: *"Create a skill for [domain]"*

The meta-agent activates and:
1. Collects domain behaviors (≥10)
2. Discovers independent dimensions
3. Reduces rank — finds irreducible generators
4. Validates: can generators reconstruct all behaviors?
5. Evaluates tool needs (reads methodology first)
6. Outputs: `SKILL.md` + `evolution-log.md` + `references/` + `tools.py` (if needed)

---

## Project Structure

```
claw/
├── CLAUDE.md                 Soul: identity, principles, tool capability
├── bot.py                    Telegram bot + heartbeat scheduler
├── heartbeat.py              Heartbeat engine
├── heartbeat.md              Phase 1 diagnostic checklist
├── feed_fetcher.py           RSS fetcher (pure Python)
├── feeds.json                97 RSS sources
├── tool_loader.py            Scans skills for tools, registers as MCP
├── worldview.md              Cross-domain insight buffer
│
├── .claude/skills/
│   ├── meta-agent/           The skill that builds skills
│   │   ├── SKILL.md          Rank reduction methodology
│   │   └── references/
│   │       ├── tool-methodology.md     7 tool design principles
│   │       ├── tool-template.py        tools.py skeleton
│   │       └── tool-spec-template.md   Tool requirements template
│   │
│   └── a-stock-agent/        Example: A-share investment (rank=3)
│       ├── SKILL.md           G1 Context × G2 Signal × G3 Gatekeeping
│       ├── tools.py           Market data tools
│       └── evolution-log.md   Reflection buffer
│
├── .env.example              Configuration template
└── requirements.txt          Dependencies
```

### Dual Memory

```
Cognitive Memory (claw/)                 Collaborative Memory (~/.claude/.../memory/)
  SKILL.md — how to think                 User preferences
  tools.py — what tools to use            Behavioral corrections
  worldview.md — cross-domain insights    Project context
  evolution-log.md — reflection buffer    CC auto memory manages

  Heartbeat maintains                     AI judges autonomously

  Delete → knowledge degrades             Delete → collaboration degrades
  Derivable from code → don't store
```

---

## Deep Dive

Full architecture document: context injection, CAS parameters, session management, model allocation, and three tool strategies (SDK MCP / Subagent on-demand / CLI-first) — see [`claw运行机制-03.17.md`](claw运行机制-03.17.md).

---

## License

MIT
