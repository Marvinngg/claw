"""a-stock-agent 工具集 — 一手 A 股数据

数据源: 腾讯行情(实时) + 新浪K线(akshare) + 同花顺财务(akshare) + 乐咕(akshare)
遵循 tool-methodology.md: 面向结果、≤5工具、参数扁平、返回语义化。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
from datetime import datetime, timedelta
from claude_agent_sdk import tool

import _cache as cache
import _data as data


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _validate_symbol(s: str) -> str | None:
    s = s.strip()
    if len(s) == 6 and s.isdigit():
        return s
    return None


# ========== 工具 1: 风险分诊 ==========

@tool(
    "astock_risk_scan",
    "对个股执行风险分诊（STEP 1 一票否决）。返回 RED/ORANGE/GREEN 风险等级。"
    "Use when: 用户提到任何个股时第一步调用。Do NOT use when: 纯市场/板块分析。",
    {"symbol": str},
)
async def astock_risk_scan(args: dict):
    """ST/亏损/流动性/停牌检查。质押数据当前不可用，已标注。"""
    sym = _validate_symbol(args["symbol"])
    if not sym:
        return _err("代码格式错误。请提供6位数字如 '000001'(深市) 或 '600519'(沪市)。")

    ck = cache.get(f"risk:{sym}")
    if ck:
        return _ok(ck)

    quote = await data.fetch_quote_tencent(data.symbol_to_tencent(sym))
    if not quote or not quote.get("name"):
        return _err(f"未找到代码 {sym}。请确认代码正确，北交所以8/4开头。")

    risks = []
    level = "GREEN"

    # ST 检查
    st, st_desc = data.is_st(quote["name"])
    if st:
        risks.append(f"⚠️ {st_desc}")
        level = "RED" if "*ST" in quote["name"] else "ORANGE"

    # 流动性检查
    turnover = quote.get("turnover_pct")
    if turnover is not None and turnover < 0.1:
        risks.append(f"流动性极低：换手率 {turnover}% < 0.1%")
        level = max(level, "ORANGE", key=["GREEN", "ORANGE", "RED"].index)

    # 财务检查（连续亏损）
    fin = await data.fetch_financial(sym)
    loss_years = 0
    if fin is not None and "净利润" in fin.columns:
        annual = fin[fin["报告期"].str.contains("-12-")].sort_values("报告期", ascending=False).head(3)
        for _, row in annual.iterrows():
            try:
                if float(row["净利润"]) < 0:
                    loss_years += 1
                else:
                    break
            except (ValueError, TypeError):
                break
    if loss_years >= 2:
        risks.append(f"连续 {loss_years} 年亏损")
        level = "RED" if loss_years >= 3 else max(level, "ORANGE", key=["GREEN", "ORANGE", "RED"].index)

    verdict_map = {
        "RED": "发现致命风险。建议立即中止分析并发出最高级别警报。",
        "ORANGE": "存在风险因素，标注后可继续分析，结论需含风险权重。",
        "GREEN": "无重大风险，可正常推进分析。",
    }

    result = json.dumps({
        "symbol": sym, "name": quote["name"],
        "risk_level": level, "risks": risks,
        "checks": {
            "is_st": st, "turnover_pct": turnover, "loss_years": loss_years,
            "pledge_ratio": "数据暂不可用（东方财富接口不通），建议通过公告确认",
        },
        "verdict": verdict_map[level],
        "data_date": datetime.now().strftime("%Y-%m-%d"),
    }, ensure_ascii=False)

    cache.put(f"risk:{sym}", result, cache.TTL_STATIC)
    return _ok(result)


# ========== 工具 2: 个股快照 ==========

@tool(
    "astock_snapshot",
    "获取个股快照：价格、涨跌、PE/PB、市值、52周位置。"
    "Use when: risk_scan 通过后需要快速了解个股。Do NOT use when: 只需K线或深度财务。"
    "Prerequisites: 先调用 astock_risk_scan。",
    {"symbol": str},
)
async def astock_snapshot(args: dict):
    """腾讯行情 + 新浪K线(52周)"""
    sym = _validate_symbol(args["symbol"])
    if not sym:
        return _err("代码格式错误。请提供6位数字。")

    ck = cache.get(f"snap:{sym}")
    if ck:
        return _ok(ck)

    quote = await data.fetch_quote_tencent(data.symbol_to_tencent(sym))
    if not quote:
        return _err(f"无法获取 {sym} 行情数据。")

    # 52周高低
    kline = await data.fetch_kline(sym, "daily")
    w52 = {}
    if kline is not None and len(kline) >= 20:
        year_data = kline.tail(250)
        h = year_data["high"].max()
        l = year_data["low"].min()
        cur = quote["price"] or 0
        pos = round((cur - l) / (h - l) * 100, 1) if h > l else 50
        w52 = {"high_52w": round(h, 2), "low_52w": round(l, 2), "position_52w_pct": pos}

    result = json.dumps({
        "symbol": sym, "name": quote["name"],
        "price": quote["price"], "change_pct": quote["change_pct"],
        "open": quote["open"], "high": quote["high"], "low": quote["low"],
        "pe_ttm": quote["pe_ttm"], "pb": quote["pb"],
        "total_cap_yi": quote["total_cap_yi"],
        "turnover_pct": quote["turnover_pct"],
        "volume_ratio": quote["volume_ratio"],
        **w52,
        "data_date": datetime.now().strftime("%Y-%m-%d"),
    }, ensure_ascii=False)

    cache.put(f"snap:{sym}", result, cache.ttl_quote())
    return _ok(result)


# ========== 工具 3: 基本面深度 ==========

@tool(
    "astock_fundamentals",
    "获取个股基本面：ROE/利润增速/营收增速/毛利率/现金流趋势 + 分红。"
    "Use when: 综合决策(路径B)或持仓复盘(路径C)。Do NOT use when: 只做短线技术分析。"
    "Prerequisites: 先调用 astock_risk_scan。",
    {"symbol": str, "years": int},
)
async def astock_fundamentals(args: dict):
    """同花顺财务摘要 + 腾讯估值"""
    sym = _validate_symbol(args["symbol"])
    if not sym:
        return _err("代码格式错误。请提供6位数字。")
    years = min(max(args.get("years", 3), 1), 5)

    ck = cache.get(f"fund:{sym}:{years}")
    if ck:
        return _ok(ck)

    fin = await data.fetch_financial(sym)
    if fin is None:
        return _err(f"无法获取 {sym} 财务数据。可能是新股或数据源异常。")

    quote = await data.fetch_quote_tencent(data.symbol_to_tencent(sym))

    # 提取年报数据（报告期格式: 2024-12-31）
    annual = fin[fin["报告期"].str.contains("-12-")].sort_values("报告期", ascending=False).head(years)
    periods = annual["报告期"].tolist()

    def _col(col):
        if col not in annual.columns:
            return []
        result = []
        for v in annual[col].tolist():
            s = str(v).strip().rstrip("%")
            if s in ("", "nan", "None", "-") or not s:
                result.append(None)
            else:
                try:
                    result.append(round(float(s), 2))
                except (ValueError, TypeError):
                    result.append(None)
        return result

    # 最新一期（可能是季报，数据时间正序，最新在末尾）
    latest = fin.iloc[-1] if len(fin) > 0 else None
    latest_period = latest["报告期"] if latest is not None else None

    result = json.dumps({
        "symbol": sym, "name": quote["name"] if quote else sym,
        "report_periods": periods,
        "latest_period": latest_period,
        "profitability": {
            "roe_pct": _col("净资产收益率"),
            "net_profit_growth_pct": _col("净利润同比增长率"),
            "revenue_growth_pct": _col("营业总收入同比增长率"),
            "gross_margin_pct": _col("销售毛利率"),
        },
        "per_share": {
            "eps": _col("基本每股收益"),
            "bvps": _col("每股净资产"),
            "ocfps": _col("每股经营现金流"),
        },
        "current_valuation": {
            "pe_ttm": quote["pe_ttm"] if quote else None,
            "pb": quote["pb"] if quote else None,
        },
        "data_date": datetime.now().strftime("%Y-%m-%d"),
    }, ensure_ascii=False)

    cache.put(f"fund:{sym}:{years}", result, cache.TTL_FUNDAMENTAL)
    return _ok(result)


# ========== 工具 4: K线技术面 ==========

@tool(
    "astock_kline",
    "获取个股K线及技术指标：MA排列、MACD信号、量价分析、支撑阻力位。"
    "不返回全量K线，返回计算好的指标和信号判断。"
    "Use when: 技术分析(路径A)或综合决策中的技术面。Do NOT use when: 只需估值/财务数据。"
    "Prerequisites: 先调用 astock_risk_scan。",
    {"symbol": str, "period": str, "days": int},
)
async def astock_kline(args: dict):
    """新浪K线 + 技术指标计算"""
    sym = _validate_symbol(args["symbol"])
    if not sym:
        return _err("代码格式错误。请提供6位数字。")
    period = args.get("period", "daily")
    if period not in ("daily", "weekly"):
        return _err("period 仅支持 'daily' 或 'weekly'。")
    days = min(max(args.get("days", 120), 30), 250)

    ck = cache.get(f"kline:{sym}:{period}:{days}")
    if ck:
        return _ok(ck)

    df = await data.fetch_kline(sym, period)
    if df is None or len(df) < 10:
        return _err(f"K线数据不足。可能该股停牌或上市时间过短。")

    df = df.tail(days).copy()
    c = df["close"].astype(float)
    v = df["volume"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)

    # MA
    ma5 = round(c.rolling(5).mean().iloc[-1], 2) if len(c) >= 5 else None
    ma10 = round(c.rolling(10).mean().iloc[-1], 2) if len(c) >= 10 else None
    ma20 = round(c.rolling(20).mean().iloc[-1], 2) if len(c) >= 20 else None
    ma60 = round(c.rolling(60).mean().iloc[-1], 2) if len(c) >= 60 else None

    # MA 排列判断
    mas = [(5, ma5), (10, ma10), (20, ma20), (60, ma60)]
    valid_mas = [(n, v) for n, v in mas if v is not None]
    arrangement = ""
    if len(valid_mas) >= 3:
        sorted_mas = sorted(valid_mas, key=lambda x: x[1], reverse=True)
        labels = [f"MA{n}" for n, _ in sorted_mas]
        arrangement = ">".join(labels)
        if sorted_mas[0][0] < sorted_mas[-1][0]:
            arrangement += "，短期多头排列"
        elif sorted_mas[0][0] > sorted_mas[-1][0]:
            arrangement += "，短期空头排列"

    # MACD (12, 26, 9)
    macd_sig = ""
    if len(c) >= 26:
        ema12 = c.ewm(span=12).mean()
        ema26 = c.ewm(span=26).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9).mean()
        hist = (dif - dea) * 2
        d, e, hv = round(dif.iloc[-1], 3), round(dea.iloc[-1], 3), round(hist.iloc[-1], 3)
        if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
            macd_sig = "MACD 金叉"
        elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
            macd_sig = "MACD 死叉"
        elif hv > 0:
            macd_sig = "MACD 多头运行"
        else:
            macd_sig = "MACD 空头运行"
    else:
        d, e, hv = None, None, None

    # 量价
    avg_v20 = round(v.tail(20).mean()) if len(v) >= 20 else None
    latest_v = v.iloc[-1]
    vol_ratio = round(latest_v / avg_v20, 2) if avg_v20 and avg_v20 > 0 else None

    # 支撑阻力（近20日高低点 + MA）
    recent = df.tail(20)
    sup1 = round(recent["low"].astype(float).min(), 2)
    res1 = round(recent["high"].astype(float).max(), 2)

    last = df.iloc[-1]
    result = json.dumps({
        "symbol": sym, "period": period,
        "bars": len(df),
        "date_range": f"{df.iloc[0]['date']} ~ {last['date']}",
        "latest": {
            "date": str(last["date"]),
            "open": round(float(last["open"]), 2),
            "high": round(float(last["high"]), 2),
            "low": round(float(last["low"]), 2),
            "close": round(float(last["close"]), 2),
            "volume": int(latest_v),
        },
        "ma": {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60,
               "arrangement": arrangement},
        "macd": {"dif": d, "dea": e, "histogram": hv, "signal": macd_sig},
        "volume": {
            "avg_20d": avg_v20,
            "latest_vs_avg": vol_ratio,
        },
        "support_resistance": {"support": sup1, "resistance": res1},
        "data_date": datetime.now().strftime("%Y-%m-%d"),
    }, ensure_ascii=False)

    cache.put(f"kline:{sym}:{period}:{days}", result, cache.ttl_quote())
    return _ok(result)


# ========== 工具 5: 市场全景 ==========

@tool(
    "astock_market_overview",
    "获取A股市场全景：指数、涨跌停统计、北向资金、两融。无需参数。"
    "Use when: 每次分析开始获取市场语境(G1)，或回答'市场怎么样'。"
    "Do NOT use when: 只需个股数据。",
    {},
)
async def astock_market_overview(args: dict):
    """腾讯指数 + 乐咕活跃度 + 北向 + 两融"""
    ck = cache.get("market")
    if ck:
        return _ok(ck)

    # 四大指数
    indices = await data.fetch_quote_batch_tencent([
        "sh000001", "sz399001", "sz399006", "sh000688"
    ])

    # 市场活跃度
    activity = await data.fetch_market_activity()

    # 北向资金
    north = await data.fetch_northbound_summary()

    # 两融
    margin = await data.fetch_margin_sse(5)

    # 组装
    idx_list = []
    for code, name in [("000001", "上证指数"), ("399001", "深证成指"),
                       ("399006", "创业板指"), ("000688", "科创50")]:
        d = indices.get(code, {})
        idx_list.append({"name": name, "price": d.get("price"),
                         "change_pct": d.get("change_pct")})

    # 两融简报
    margin_info = None
    if margin and len(margin) > 0:
        latest = margin[-1]
        balance = latest.get("融资融券余额")
        if balance:
            margin_info = {"balance_yi": round(balance / 1e8, 1)}
            if len(margin) >= 2:
                prev = margin[-2].get("融资融券余额")
                if prev:
                    margin_info["change_yi"] = round((balance - prev) / 1e8, 1)

    result = json.dumps({
        "indices": idx_list,
        "market_activity": activity,
        "northbound": north,
        "margin": margin_info,
        "data_date": datetime.now().strftime("%Y-%m-%d"),
    }, ensure_ascii=False, default=str)

    cache.put("market", result, cache.ttl_flow())
    return _ok(result)


# 注册表
TOOLS = [
    astock_risk_scan,
    astock_snapshot,
    astock_fundamentals,
    astock_kline,
    astock_market_overview,
]
