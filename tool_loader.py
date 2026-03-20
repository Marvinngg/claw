"""工具加载器 — 扫描 skill 目录，动态创建 MCP server"""
import importlib.util
from pathlib import Path
from claude_agent_sdk import create_sdk_mcp_server

SKILLS_DIR = Path(__file__).parent / ".claude" / "skills"

# 缓存：上次加载的工具名列表
_last_tool_names: list[str] = []


def load_skill_tools() -> dict:
    """扫描所有 skill，返回 {name: McpServerConfig}"""
    global _last_tool_names
    servers = {}
    tool_names = []
    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue
        tools_py = skill_dir / "tools.py"
        if not tools_py.exists():
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"skill_{skill_dir.name}", tools_py
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            tools = getattr(module, "TOOLS", [])
            if tools:
                servers[skill_dir.name] = create_sdk_mcp_server(
                    name=skill_dir.name,
                    version="1.0.0",
                    tools=tools,
                )
                for t in tools:
                    tool_names.append(t.name)
        except Exception as e:
            print(f"[tool_loader] {skill_dir.name} 加载失败: {e}")
    _last_tool_names = tool_names
    return servers


def get_tool_names() -> list[str]:
    """返回上次 load_skill_tools 加载的工具名列表"""
    return _last_tool_names
