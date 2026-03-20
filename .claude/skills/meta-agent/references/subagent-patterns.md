# Subagent 模式参考

> 来源：Simon Willison — Agentic Engineering Patterns / Subagents（2026）
> URL: https://simonwillison.net/guides/agentic-engineering-patterns/subagents/

## 核心问题

LLM 上下文窗口是硬约束。Subagent = 生成全新上下文窗口执行子任务，结果返回父 agent。
本质：用"进程隔离"思路管理认知资源，不是能力扩展而是资源管理。

## 模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **上下文保护** | 父 agent 委派 token 密集型任务给子 agent | 代码库探索、大量文件搜索 |
| **并行执行** | 多个子 agent 同时运行独立任务 | 独立文件编辑、多路搜索 |
| **专业化子 agent** | 自定义系统提示/工具集的角色分工 | Code reviewer / Test runner / Debugger |
| **模型分层** | 子 agent 可用更快更便宜的模型（如 Haiku） | 简单搜索/格式化任务 |

## 设计要点

1. **主要价值是保护根上下文**，不是能力增强——子 agent 能做的事父 agent 也能做，差别在于 token 消耗
2. **避免过度专业化**——每多一个角色就多一层协调开销
3. **并行优先**——独立任务同时派发，不要串行等待
4. **子 agent 返回值应精简**——只返回父 agent 需要的结论，不返回全部中间过程

## 与 meta-agent M3 的关系

设计 agent 的 M3（能力接口）时，需评估：
- 该 agent 的典型任务是否会溢出单轮上下文？
- 如果会 → SKILL.md 中应声明子 agent 委派策略，而非试图在单一上下文中完成
- 子 agent 是 M3 的第三种能力层级：CC 原生工具 < Skill 专属工具 < 子 agent 委派
