# Claw

**A self-evolving cognitive system, not a chatbot.**

Claw is a living cognitive architecture built on [Claude Code](https://claude.ai/claude-code) and the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk). It doesn't just respond to prompts — it learns from RSS feeds, reflects on its own performance, evolves its knowledge through compression, and builds its own tools when existing ones aren't good enough.

Most AI agent frameworks ask: *"How do I orchestrate LLM calls?"*
Claw asks: **"How does an AI system grow?"**

---

## Core Philosophy

### Intelligence = Compression, Not Accumulation

Every piece of knowledge Claw acquires must earn its place. Skills don't grow by appending — they evolve by compressing. When SKILL.md hits its 5000-character limit, new knowledge must displace old knowledge. Information density monotonically increases.

This mirrors how human expertise works: a master chess player doesn't remember more positions — they see fewer, more powerful patterns.

### Rank Reduction (降秩)

Borrowed from linear algebra: find the minimum set of independent generators that can reconstruct all observed behaviors in a domain. Remove redundancy. What remains is the irreducible cognitive structure.

Every skill in Claw is defined by its "rank" — the minimum number of independent thinking operations needed to cover the domain. A stock investment skill has rank 3: Market Context Reading × Signal Synthesis × Cognitive Gatekeeping. Remove any one and the system degrades.

### Autonomy Through Constraints

Claw doesn't use orchestration loops ("first do A, then do B"). Instead, it uses constraint declarations ("must not exceed X", "can use tools Y"). The LLM decides execution order. Orchestration is a ceiling (limits capability); constraints are a floor (enables emergence).

---

## Architecture

```
                    External World
                 /                \
       RSS Feeds                  Conversations
       (97 sources)               (Telegram)
            |                         |
            v                         v
  +-------------------+    +-------------------+
  | Feed Pipeline     |    | Daily Dialogue    |
  | Stage 1: Fetch    |    | CAS opus          |
  | Stage 2: Filter   |    | Full tool access  |
  | Stage 3: Learn    |    +-------------------+
  +-------------------+              |
            |                         |
            v                         v
  +------------------------------------------------+
  |              SKILL.md (Domain Knowledge)         |
  |  Wiring diagram + core knowledge  <=5000 chars   |
  |  Auto-loaded when triggered                      |
  +------------------------+-----------------------+
                           |
       +-------------------+-------------------+
       |                   |                   |
       v                   v                   v
  tools.py           evolution-log.md     worldview.md
  (Domain Tools)     (Reflection Buffer)  (Cross-domain)
  <=3000 chars       [反思] [知识]         <=80 lines
  <=5 tools          [工具需求] [工具反思]
       |                   |                   |
       +-------------------+-------------------+
                           |
                      Heartbeat
                    (every 6 hours)
                           |
              +------------+------------+
              |            |            |
              v            v            v
         Skill          Tool        Worldview
         Maintenance    Maintenance  Maintenance
         (compress)     (evolve)    (promote to
                                    CLAUDE.md)
```

### Four Evolution Paths

| Path | What Evolves | Mechanism | Destination |
|------|-------------|-----------|-------------|
| **Domain Learning** | How to think about a field | RSS/conversations → evolution-log → heartbeat folds back | SKILL.md |
| **Tool Evolution** | What instruments to use | Usage → [工具反思] → agent fixes or heartbeat crystallizes | tools.py |
| **General Knowledge** | How to see the world | Cross-domain insights → heartbeat validates (>=2 sources) | CLAUDE.md |
| **Collaboration** | How to work with humans | CC auto memory, AI judges autonomously | memory/ |

### Dual Memory Architecture

```
Cognitive Memory (claw/)              Collaborative Memory (memory/)
  SKILL.md, tools.py,                  CC auto memory system
  worldview.md, evolution-log.md        User preferences, feedback,
  Maintained by heartbeat               project context

  Delete it → knowledge degrades        Delete it → collaboration degrades

  Derivable from code → don't store
```

---

## The Heartbeat

Every 6 hours, Claw performs autonomous self-maintenance:

**Phase 1 — Diagnosis (haiku, read-only)**
- Scans all evolution logs for unprocessed entries
- Checks SKILL.md size limits
- Checks tools.py health (size, count, import whitelist)
- Checks worldview.md line count
- Reports: skip or run + task list

**Phase 2 — Execution (opus)**
- `skill_maintenance`: Compresses reflections into SKILL.md. Priority: metacognition > rules > data
- `tool_maintenance`: Reads methodology, then crystallizes/optimizes/deprecates tools
- `worldview_maintenance`: Promotes validated insights to CLAUDE.md (the "soul")

---

## Tool Evolution

Tools aren't pre-designed — they grow from practice.

**Creation trigger**: Not frequency, but quality. If CC's native tools (Bash, WebFetch) can't achieve the output quality a skill demands, a tool gets built. A stock analysis skill needs first-hand market data, not third-hand web scrapes.

**Methodology**: Before creating or modifying any tool, the agent must read `tool-methodology.md` — 7 principles distilled from Anthropic's ACI guidelines, Block's MCP Playbook, and academic research on 856+ tool descriptions.

**Lifecycle**:
```
Need discovered → Read methodology → Write tools.py
                                         |
  Next message: tool_loader auto-discovers, registers as MCP
                                         |
  Usage → works fine → no action
        → problems → [工具反思] in evolution-log
                         |
                    Agent fixes immediately
                         or
                    Heartbeat reviews systematically
                         |
                    >= 3 similar reflections = systemic issue, highest priority
```

---

## RSS Learning Pipeline

A three-stage funnel that converts the internet into compressed knowledge:

| Stage | Model | Purpose | Cost |
|-------|-------|---------|------|
| **Fetch** | Python only | Pull 97 RSS sources, deduplicate | Zero LLM cost |
| **Filter** | Sonnet | Select articles worth deep reading | ~1 API call |
| **Learn** | Opus | Read full articles, update skills/worldview | Varies |

The filter is strict: methodology papers and architecture analyses over news, product launches, and weekly roundups. Quality over quantity.

---

## Included Example: A-Stock Investment Agent

`a-stock-agent/` demonstrates a complete skill with rank=3:

- **G1 Market Context**: Decode the policy-capital-sentiment-cycle state of China's A-share market
- **G2 Signal Synthesis**: Cross-validate multiple data dimensions into actionable signals
- **G3 Cognitive Gatekeeping** (soul generator): Counter emotional market narratives, maintain independent judgment

Remove G3 and it degrades to a generic stock screener — it can read data but can't resist the crowd.

---

## Quick Start

```bash
# Clone
git clone https://github.com/anthropics/claw.git  # adjust URL
cd claw

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: add your Telegram bot token

# Authenticate Claude
claude login

# Start
python3 bot.py

# In Telegram, send /whoami to get your user ID
# Add it to .env as TELEGRAM_OWNER_ID, restart bot
```

### Commands

| Command | What it does |
|---------|-------------|
| (any message) | Conversation with Claw (opus) |
| `/heartbeat` | Run full heartbeat (diagnosis + maintenance + RSS) |
| `/dry` | Phase 1 only (read-only diagnosis) |
| `/feeds` | RSS learning only |
| `/status` | System status |
| `/reset` | Reset conversation |

---

## Creating New Skills

Tell Claw: *"Create a skill for [domain]"* — this triggers the meta-agent, which:

1. Collects domain behaviors (>=10)
2. Discovers independent dimensions
3. Reduces rank — finds irreducible generators
4. Validates: can generators reconstruct all behaviors?
5. Evaluates tool needs (read methodology first)
6. Outputs: SKILL.md + evolution-log.md + references/ + tools.py (optional)

---

## Project Structure

```
claw/
├── CLAUDE.md                 Soul: identity, principles, tool capability pointer
├── bot.py                    Telegram bot + auto heartbeat scheduler
├── heartbeat.py              Heartbeat engine (Phase 1 + Phase 2 + RSS)
├── heartbeat.md              Phase 1 diagnostic checklist
├── feed_fetcher.py           RSS fetcher (pure Python, zero LLM)
├── feeds.json                RSS source configuration (97 feeds)
├── tool_loader.py            Dynamic skill tool scanner + MCP registrar
├── worldview.md              Cross-domain insight buffer
├── .claude/skills/
│   ├── meta-agent/           The agent that builds agents
│   │   ├── SKILL.md          Rank reduction methodology
│   │   └── references/
│   │       ├── tool-methodology.md    7 tool design principles
│   │       ├── tool-template.py       tools.py coding skeleton
│   │       └── tool-spec-template.md  Tool requirements template
│   └── a-stock-agent/        Example: A-share investment skill
│       ├── SKILL.md          Rank=3 cognitive wiring diagram
│       ├── tools.py          Market data tools (optional)
│       └── evolution-log.md  Reflection buffer
├── .env.example              Configuration template
└── requirements.txt          Python dependencies
```

---

## Design Document

For the complete technical architecture — context injection mechanisms, CAS parameters, session management, model allocation, and all three tool strategy options (MCP pre-registration / Subagent on-demand / CLI-first) — see [`claw运行机制-03.17.md`](claw运行机制-03.17.md).

---

## Requirements

- Python 3.11+
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) >= 0.1.44
- Claude Max/Team subscription or API key
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

---

## License

MIT
