#!/usr/bin/env python3
"""Claw Telegram Bot — 入口 + 自动心跳调度

用法:
  python3 bot.py              # 启动 bot（含自动心跳）
  python3 bot.py --no-auto    # 启动 bot（不自动心跳）

命令:
  /start      — 显示帮助 + 你的 user id
  /heartbeat  — 完整心跳（Phase 1 + Phase 2 + RSS）
  /dry        — Phase 1 诊断（只读）
  /feeds      — RSS 学习
  /status     — 系统状态
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from functools import wraps
from pathlib import Path

# 清理 CC 嵌套检测环境变量
for key in [k for k in os.environ if k.startswith("CLAUDE")]:
    del os.environ[key]

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

CLAW_DIR = Path(__file__).parent
BOT_SESSION_FILE = CLAW_DIR / ".bot-session"
sys.path.insert(0, str(CLAW_DIR))
import heartbeat as hb
from tool_loader import load_skill_tools

# ── 配置 ──

def _load_env() -> dict:
    env = {}
    env_file = CLAW_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

_env = _load_env()
BOT_TOKEN = _env.get("TELEGRAM_BOT_TOKEN", "")
OWNER_ID = int(_env.get("TELEGRAM_OWNER_ID", "0"))
HEARTBEAT_INTERVAL_HOURS = float(_env.get("HEARTBEAT_INTERVAL_HOURS", "6"))

logging.basicConfig(format="%(asctime)s [%(name)s] %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("bot")

# ── 日志捕获 ──

_logs: list[str] = []
hb.set_log_callback(lambda msg: _logs.append(msg))

# ── 并发锁 ──

_lock = asyncio.Lock()

# ── 权限 ──

def owner_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if OWNER_ID and uid != OWNER_ID:
            await update.message.reply_text(f"无权限 (your id: {uid})")
            return
        return await func(update, context)
    return wrapper

# ── 工具 ──

def _truncate(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n...(truncated)"

def _format_logs(n: int = 30) -> str:
    return "\n".join(_logs[-n:])

# ── 命令 ──

@owner_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        f"Claw 已就绪\n"
        f"your id: {uid}\n\n"
        f"直接发消息 — 对话（CAS opus）\n"
        f"/heartbeat — 完整心跳\n"
        f"/dry — Phase 1 诊断（只读）\n"
        f"/feeds — RSS 学习\n"
        f"/status — 系统状态\n"
        f"/reset — 重置对话"
    )


@owner_only
async def cmd_heartbeat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _lock.locked():
        await update.message.reply_text("有任务执行中，请稍候")
        return
    msg = await update.message.reply_text("心跳执行中...")
    _logs.clear()
    async with _lock:
        try:
            await hb.heartbeat()
            await msg.edit_text(_truncate(f"心跳完成\n\n{_format_logs()}"))
        except Exception as e:
            await msg.edit_text(_truncate(f"心跳失败: {e}\n\n{_format_logs(20)}"))


@owner_only
async def cmd_dry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _lock.locked():
        await update.message.reply_text("有任务执行中，请稍候")
        return
    msg = await update.message.reply_text("Phase 1 诊断中...")
    _logs.clear()
    async with _lock:
        try:
            result = await hb.phase1()
            action = result.get("action", "skip")
            tasks = result.get("tasks", "")
            reply = f"Phase 1: {action}\n"
            if tasks:
                reply += f"tasks:\n{tasks}\n"
            reply += f"\n{_format_logs()}"
            await msg.edit_text(_truncate(reply))
        except Exception as e:
            await msg.edit_text(_truncate(f"Phase 1 失败: {e}\n\n{_format_logs(20)}"))


@owner_only
async def cmd_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _lock.locked():
        await update.message.reply_text("有任务执行中，请稍候")
        return
    msg = await update.message.reply_text("RSS 学习中...")
    _logs.clear()
    async with _lock:
        try:
            await hb.feed_cycle()
            await msg.edit_text(_truncate(f"RSS 学习完成\n\n{_format_logs()}"))
        except Exception as e:
            await msg.edit_text(_truncate(f"RSS 学习失败: {e}\n\n{_format_logs(20)}"))


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Skills
    skills_dir = CLAW_DIR / ".claude" / "skills"
    skills = []
    if skills_dir.exists():
        for d in sorted(skills_dir.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                skills.append(d.name)

    # Last heartbeat
    session_file = CLAW_DIR / ".heartbeat-session"
    last_hb = "未运行"
    if session_file.exists():
        mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
        last_hb = mtime.strftime("%m-%d %H:%M")

    # Last RSS
    last_check = CLAW_DIR / ".feeds-last-check"
    last_rss = "未采集"
    if last_check.exists():
        try:
            ts = float(last_check.read_text().strip())
            last_rss = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
        except ValueError:
            pass

    await update.message.reply_text(
        f"Skills: {', '.join(skills) or '无'}\n"
        f"上次心跳: {last_hb}\n"
        f"上次 RSS: {last_rss}\n"
        f"自动心跳: 每 {HEARTBEAT_INTERVAL_HOURS}h\n"
        f"Owner: {OWNER_ID or '未设置'}"
    )


# ── 对话（CAS agent）──

def _load_bot_session() -> str | None:
    if BOT_SESSION_FILE.exists():
        sid = BOT_SESSION_FILE.read_text().strip()
        return sid if sid else None
    return None

def _save_bot_session(sid: str):
    BOT_SESSION_FILE.write_text(sid)


@owner_only
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if BOT_SESSION_FILE.exists():
        BOT_SESSION_FILE.unlink()
    await update.message.reply_text("对话已重置")


@owner_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    if _lock.locked():
        await update.message.reply_text("有任务执行中，请稍候")
        return

    msg = await update.message.reply_text("...")
    _logs.clear()

    async with _lock:
        try:
            session_id = _load_bot_session()

            skill_tools = load_skill_tools()
            options = ClaudeAgentOptions(
                system_prompt={"type": "preset", "preset": "claude_code"},
                setting_sources=["project", "user"],
                cwd=str(CLAW_DIR),
                model="opus",
                max_turns=30,
                permission_mode="bypassPermissions",
                mcp_servers=skill_tools if skill_tools else None,
            )
            if session_id:
                options.resume = session_id

            async with ClaudeSDKClient(options=options) as client:
                response, new_sid = await hb.run_cas(client, text)

            if new_sid:
                _save_bot_session(new_sid)

            response = response or "（无文本响应）"
            logs_text = _format_logs(10)
            if logs_text:
                response += f"\n\n--- log ---\n{logs_text}"

            # 分段发送（Telegram 单条 4096 字符限制）
            if len(response) <= 4000:
                await msg.edit_text(response)
            else:
                await msg.edit_text(response[:4000])
                for i in range(4000, len(response), 4000):
                    chunk = response[i:i + 4000]
                    if chunk.strip():
                        await update.message.reply_text(chunk)

        except Exception as e:
            logger.error(f"对话失败: {e}")
            # resume 失败时清除 session 重试
            if "resume" in str(e).lower() or "session" in str(e).lower():
                if BOT_SESSION_FILE.exists():
                    BOT_SESSION_FILE.unlink()
                await msg.edit_text(f"会话异常已重置，请重新发送")
            else:
                await msg.edit_text(f"错误: {e}")


# ── 自动心跳 ──

async def _auto_heartbeat_loop(bot):
    """后台循环，每 N 小时执行一次心跳"""
    await asyncio.sleep(60)  # 启动 60 秒后首次
    while True:
        if not _lock.locked():
            logger.info("自动心跳触发")
            _logs.clear()
            async with _lock:
                try:
                    await hb.heartbeat()
                    if OWNER_ID:
                        text = f"自动心跳完成\n\n{_format_logs(15)}"
                        await bot.send_message(OWNER_ID, _truncate(text))
                except Exception as e:
                    logger.error(f"自动心跳失败: {e}")
                    if OWNER_ID:
                        await bot.send_message(OWNER_ID, f"自动心跳失败: {e}")
        else:
            logger.info("自动心跳跳过（有任务执行中）")
        await asyncio.sleep(HEARTBEAT_INTERVAL_HOURS * 3600)


async def _post_init(app: Application):
    if "--no-auto" not in sys.argv and HEARTBEAT_INTERVAL_HOURS > 0:
        asyncio.create_task(_auto_heartbeat_loop(app.bot))
        logger.info(f"自动心跳已启动: 每 {HEARTBEAT_INTERVAL_HOURS}h")


# ── 入口 ──

def main():
    if not BOT_TOKEN:
        print("错误: .env 中未配置 TELEGRAM_BOT_TOKEN")
        return

    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("heartbeat", cmd_heartbeat))
    app.add_handler(CommandHandler("dry", cmd_dry))
    app.add_handler(CommandHandler("feeds", cmd_feeds))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot 启动")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
