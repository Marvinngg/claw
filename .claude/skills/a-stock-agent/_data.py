"""AKShare + 直接 API 数据层 — 隔离上游变更"""
import asyncio
import json
import re
from datetime import datetime, timedelta

import aiohttp
import akshare as ak
import pandas as pd

TIMEOUT = aiohttp.ClientTimeout(total=15)
_SINA_HEADERS = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}


# ========== 腾讯实时行情 ==========

async def fetch_quote_tencent(symbol: str) -> dict | None:
    """腾讯行情: 价格/PE/PB/市值/换手/量比。symbol 如 sh600519 或 sz000001"""
    url = f"https://qt.gtimg.cn/q={symbol}"
    async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
        async with s.get(url) as r:
            if r.status != 200:
                return None
            text = await r.text()
    parts = text.split("~")
    if len(parts) < 55:
        return None
    return {
        "name": parts[1],
        "code": parts[2],
        "price": _f(parts[3]),
        "prev_close": _f(parts[4]),
        "open": _f(parts[5]),
        "volume_lot": _f(parts[6]),
        "change": _f(parts[31]),
        "change_pct": _f(parts[32]),
        "high": _f(parts[33]),
        "low": _f(parts[34]),
        "turnover_pct": _f(parts[38]),
        "pe_ttm": _f(parts[39]),
        "circ_cap_yi": _f(parts[44]),
        "total_cap_yi": _f(parts[45]),
        "pb": _f(parts[46]),
        "volume_ratio": _f(parts[49]),
        "pe_dynamic": _f(parts[52]) if len(parts) > 52 else None,
    }


async def fetch_quote_batch_tencent(symbols: list[str]) -> dict[str, dict]:
    """批量腾讯行情"""
    url = f"https://qt.gtimg.cn/q={','.join(symbols)}"
    async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
        async with s.get(url) as r:
            text = await r.text()
    result = {}
    for line in text.strip().split("\n"):
        if "~" not in line:
            continue
        parts = line.split("~")
        if len(parts) < 10:
            continue
        code = parts[2]
        result[code] = {
            "name": parts[1], "code": code,
            "price": _f(parts[3]), "change_pct": _f(parts[32]),
        }
    return result


# ========== AKShare 包装（同步→异步） ==========

async def fetch_kline(symbol: str, period: str = "daily",
                      start: str = None, end: str = None) -> pd.DataFrame | None:
    """新浪K线（前复权）。symbol 纯数字如 '600519'"""
    if end is None:
        end = datetime.now().strftime("%Y%m%d")
    if start is None:
        days = 250 if period == "daily" else 120
        start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
    prefix = "sh" if symbol.startswith("6") or symbol.startswith("9") else "sz"
    try:
        df = await asyncio.to_thread(
            ak.stock_zh_a_daily, symbol=f"{prefix}{symbol}",
            start_date=start, end_date=end, adjust="qfq"
        )
        return df if df is not None and not df.empty else None
    except Exception:
        return None


async def fetch_financial(symbol: str) -> pd.DataFrame | None:
    """同花顺财务摘要"""
    try:
        df = await asyncio.to_thread(ak.stock_financial_abstract_ths, symbol=symbol)
        return df if df is not None and not df.empty else None
    except Exception:
        return None


async def fetch_market_activity() -> dict | None:
    """乐咕市场活跃度"""
    try:
        df = await asyncio.to_thread(ak.stock_market_activity_legu)
        if df is None or df.empty:
            return None
        d = dict(zip(df["item"], df["value"]))
        return d
    except Exception:
        return None


async def fetch_northbound_summary() -> dict | None:
    """北向资金当日汇总"""
    try:
        df = await asyncio.to_thread(ak.stock_hsgt_fund_flow_summary_em)
        if df is None or df.empty:
            return None
        rows = df.to_dict("records")
        return {"items": rows}
    except Exception:
        return None


async def fetch_margin_sse(days: int = 5) -> list[dict] | None:
    """沪市两融余额（最近N个交易日）"""
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days * 3)).strftime("%Y%m%d")
    try:
        df = await asyncio.to_thread(
            ak.stock_margin_sse, start_date=start, end_date=end
        )
        if df is None or df.empty:
            return None
        return df.tail(days).to_dict("records")
    except Exception:
        return None


async def fetch_index_pe(symbol: str = "沪深300") -> dict | None:
    """指数PE/PB（乐咕）"""
    try:
        df = await asyncio.to_thread(ak.stock_index_pe_lg, symbol=symbol)
        if df is None or df.empty:
            return None
        latest = df.iloc[-1].to_dict()
        # 计算分位
        pe_col = "滚动市盈率"
        if pe_col in df.columns:
            series = df[pe_col].dropna()
            current = series.iloc[-1]
            pct = (series < current).sum() / len(series) * 100
            latest["pe_percentile"] = round(pct, 1)
        return latest
    except Exception:
        return None


# ========== 辅助 ==========

def _f(s: str):
    """字符串转 float，失败返回 None"""
    try:
        v = float(s)
        return v if v == v else None  # NaN check
    except (ValueError, TypeError):
        return None


def symbol_to_tencent(symbol: str) -> str:
    """'600519' → 'sh600519', '000001' → 'sz000001'"""
    if symbol.startswith("6") or symbol.startswith("9"):
        return f"sh{symbol}"
    return f"sz{symbol}"


def is_st(name: str) -> tuple[bool, str | None]:
    """从股票名称判断 ST 状态"""
    if name.startswith("*ST"):
        return True, "*ST（退市风险警示）"
    if name.startswith("ST"):
        return True, "ST（其他风险警示）"
    return False, None
