# 工具设计方法论

> 来源：Anthropic ACI 指南、Block MCP Playbook、Arcade 54 Patterns、学术论文（856 工具描述分析）
> 沉淀日期：2026-03-17

## 核心心智模型

工具定义就是 prompt。AI 永远看不到代码实现，只看到名称、描述、参数名、错误消息。
造工具的本质是写一段精准的自然语言说明书，碰巧背后有代码执行。

## 七条原则

### 1. 围绕结果设计，不围绕 API 包装

```
✗ get_user(id) + list_orders(user_id) + get_status(order_id)
✓ track_latest_order(email)
```

判断：agent 需要完成任务的能力，不是访问数据的能力。

### 2. 少即是多

| 工具数 | 效果 |
|--------|------|
| ≤10 | 100% 准确率 |
| ~30 | 开始混淆 |
| 100+ | 必然崩溃 |

每个 skill ≤ 5 个工具。每多一个工具就多一份认知负担。

### 3. 参数扁平 + 枚举约束

```
✗ def search(filters: dict)
✓ def search(status: Literal["active","closed"], limit: int = 10)
```

禁止嵌套 dict。枚举用 Literal。自由度越大，出错概率越高。
poka-yoke（防呆）：让 agent 很难犯错，比教它不犯错更可靠。

### 4. 返回值语义化，给 AI 消费

```
✗ uuid, 256px_image_url, mime_type     ← 技术标识符
✓ name, description, status            ← 语义字段
```

只返回 agent 下一步需要的信息。分页默认 20-50 条。

### 5. 错误消息是教学机会

```
✗ "HTTP 429"
✓ "日期范围超过 90 天。请用更短范围：start='2024-01-01', end='2024-03-31'"
```

告诉 agent 怎么改，不只是哪里错。

### 6. 描述像给新员工解释

1-2 句话，关键信息放开头。必须回答：
- 什么时候该用（when）
- 什么时候不该用（when not）
- 需要什么前提（prerequisites）

模板：`"Tool to <action>. Use when <context>. Do NOT use when <anti-context>."`

### 7. 多步操作用代码执行，不逐步调用

单次简单操作 → 工具调用
多步链式操作 → Bash 执行代码（token 节省 98.7%）

## 何时造工具

核心问题：**用当前手段能不能达到这个 skill 应有的输出质量？**

造工具的驱动力是效果，不是频次。一个工具哪怕只用一次，如果能让 agent 从三手信息变成一手信息，就值得造。

造工具的情况：
- **数据质量不够**：CC 原生能获取数据，但信源层级、时效性、结构化程度不达标
  例：投资 skill 用 WebFetch 抓到的是三手转载 → 造工具直连一手数据源 API
- **执行精度不够**：Bash 脚本能跑但不够稳定/精确/防呆
- **需要特定协议/认证**：OAuth、WebSocket、特定 API 格式

不造工具的情况：
- CC 原生工具（Bash/WebFetch/Read）已能达到所需输出质量
- 纯文本处理、文件操作 → CC 原生工具天然擅长
- 需要复杂认证且没有明确数据源 → 先写 tool-spec.md 明确需求再造

判断辅助信号（非决定性）：
- 同一模式 Bash 执行过 ≥2 次 → 说明需求真实存在
- evolution-log 中有 [工具需求] 标签 → 说明 agent 自己意识到了缺口

## tools.py 编码约束

- 文件 ≤ 3000 字符，≤ 5 个工具
- 参数扁平，禁止 dict 类型
- 枚举值用 Literal
- 每个工具必须有 docstring
- 错误消息包含修正建议
- 返回值用语义化字段名
- 网络请求必须有 timeout（≤15s）
- import 白名单：标准库 + aiohttp + claude_agent_sdk
- 必须有 TOOLS = [...] 注册表
