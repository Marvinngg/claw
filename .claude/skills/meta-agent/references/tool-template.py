"""[Skill名] - 工具集

遵循 tool-methodology.md 设计原则。
"""
from claude_agent_sdk import tool


@tool(
    "skill_action_resource",          # 命名：skill_动作_资源
    "Tool to <action>. Use when <context>. Do NOT use when <anti-context>.",
    {
        "param_name": str,            # 参数扁平，语义化命名
        # "status": Literal["active", "closed"],  # 枚举用 Literal
    },
)
async def skill_action_resource(args: dict):
    """实现说明（心跳审查时读）"""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.example.com/data",
                params={"q": args["param_name"]},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return {
                        "content": [{"type": "text", "text":
                            f"请求失败 HTTP {resp.status}。请检查参数 param_name='{args['param_name']}' 是否正确。"
                        }],
                        "isError": True,
                    }
                data = await resp.json()
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"网络错误: {e}。请稍后重试。"}],
            "isError": True,
        }

    # 返回语义化字段，只返回 agent 下一步需要的信息
    return {"content": [{"type": "text", "text": f"结果: {data}"}]}


# 注册表：tool_loader 只读这个列表
TOOLS = [skill_action_resource]
