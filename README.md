
## 现在有什么

- **Companion chat runtime**
  - 面向日常对话的轻聊天核
  - 负责最终对用户说话
  - 支持最近上下文保留

- **Memory system**
  - SQLite 存储
  - FTS 检索
  - 长期记忆 / 活跃记忆 / 日志分层
  - 检索记忆与固定注入记忆去重

- **Action / tool runtime**
  - 网页读取
  - 搜索上下文
  - 图片分析
  - 记忆检索
  - 提醒创建
  - MCP 扩展入口

- **Scheduler**
  - 定时提醒
  - 主动消息调度
  - 提醒先进 AI，再由 AI 发给用户

- **Channel integrations**
  - Feishu
  - QQ Bot official channel
  - Web panel

## 项目结构

```text
Aelios/
├─ saki-gateway/        # Python gateway backend
│  ├─ src/saki_gateway/
│  └─ data/config.example.json
├─ saki-phone/web/      # Web dashboard frontend
├─ README.md
└─ ARCHITECTURE.md
```

## 设计思路

Aelios 的核心思路很简单：

1. **聊天核**负责自然对话，不默认背重型 agent 心智
2. **行动核**只在需要工具时介入
3. **记忆核**负责长期连续性，而不是把所有记忆永远硬塞进 prompt
4. **渠道层**统一把 Feishu、QQ、Web 等入口接进来

这样做的目标是：

- 日常聊天更自然
- prompt 更轻
- 工具调用更稳定
- 记忆更容易维护
- 项目更适合开源和二次开发

更多背景见：[`ARCHITECTURE.md`](./ARCHITECTURE.md)

## 快速开始

### 1. 安装后端依赖

```bash
cd saki-gateway
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e .
python3 -m pip install lark-oapi
```

### 2. 准备配置

```bash
cp data/config.example.json data/config.json
```

然后填写你自己的：

- chat provider
- action provider
- search provider
- image provider
- Feishu / QQ Bot credentials
- dashboard password

### 3. 启动网关

```bash
PYTHONPATH=src python3 -m saki_gateway
```

默认监听：

- `http://127.0.0.1:3457`
- `http://0.0.0.0:3457`

### 4. 打开面板

浏览器访问：

- `http://127.0.0.1:3457`

## 当前后端能力

### Memory

- SQLite memory store
- FTS-based keyword recall
- active memory + core profile files
- daily log generation
- broader retrieval candidate recall
- dedupe between fixed injected memories and retrieved memories

### Chat / session

- recent session context retention
- separate action runtime and companion runtime
- tool-augmented reply synthesis

### Tools

- `fetch_url`
- `read_file`
- `search_web`
- `analyze_image`
- `search_memory`
- `create_reminder`
- `call_mcp`

### Channels

- Feishu inbound / outbound
- QQ Bot inbound / outbound
- Web dashboard hosted by gateway


### Study workspace refinement (B5 + workspace layout slice)

`saki-phone/web` now uses a calmer workspace-style study surface layered on top of the existing B1/B2/B3/B4/B5/B6 backend APIs. The goal of this slice is frontend redistribution and hierarchy cleanup: chat still remains the main continuous interaction flow, but the study page now reads more like a lightweight Claude-inspired workbench and less like a stack of admin forms.

What changed in this UI refinement slice:
- a two-column workspace shell inside the existing dashboard navigation, with the conversation/work area centered and study tools grouped into a quieter side workbench
- a compact quick-tools strip for Start Focus, Resume Session, Pomodoro, Check-in, Plan Tracker, and Progress / Review
- a higher-priority Current Session card that surfaces title, mode, planned minutes, elapsed/remaining state, lifecycle controls, and the latest companion nudge without adding a new timer system
- an integrated Plan Tracker card that keeps current goal, current task, next small step, and blocker visible before the edit fields
- a shorter, lighter check-in interaction that keeps the same backend model but feels more approachable on web/mobile surfaces
- a concise Progress Snapshot card for completion rate, focus/review/recovery balance, momentum summary, and friction patterns
- a cleaner recent study feed that separates recent responses from recent activity so user-facing support stays readable while raw-ish detail remains secondary

What did not change:
- no backend rewrite
- no replacement of the existing B1-B6 flows
- no chat architecture replacement
- no heavy analytics dashboard
- no full planner / productivity suite

Intentional limitations:
- no timer animation system
- no nested tasks, projects, or calendar planning
- no desktop-only layout assumptions; the workspace collapses responsively for narrow screens
- the Plan Tracker is intentionally a single-current-plan helper, not a productivity suite

Backend support reused by this slice:
- `GET /api/study-plan`
- `POST /api/study-plan`
- `POST /api/study-plan/complete`
- `POST /api/study-plan/clear`
- existing learning-session, progress, response, event, and check-in endpoints

Reused data from earlier slices:
- B1 learning sessions remain the source of focus/review/recovery session state
- B2 event-triggered responses remain the source of session support messages
- B3 wellbeing check-ins and recovery-aware response logic are unchanged and only promoted in UI
- B4 progress summaries remain read-only computed summaries, now shown in a cleaner snapshot card
- B5 study UI remains the base surface, now refined into a workspace shell
- B6 layered persona injection remains backend-side and continues to shape study companion responses

Known limitations / TODO:
- the quick tools currently scroll to the relevant workspace cards instead of opening a separate command palette
- the feed still shows backend-derived event names directly; future polish can map more of them to friendlier labels without changing the underlying data model
- the study page is intentionally still one page inside the dashboard, not a separate full-screen app shell

## 配置文件

主配置示例：

- [`saki-gateway/data/config.example.json`](./saki-gateway/data/config.example.json)

运行时本地配置：

- `saki-gateway/data/config.json`

仓库不会包含真实：

- API keys
- app secrets
- personal memories
- local runtime databases
- private logs

## 开源说明

这个仓库当前提交的是 **脱敏版本**，适合公开展示与二次开发。

已去除：

- 私人记忆与对话数据
- 实际渠道 token / secret
- 本地部署细节与私有运行数据

如果你要基于它自部署，需要自己提供：

- 模型 API
- 渠道配置
- persona / memory 初始内容

## 适合用来做什么

- 做自己的 AI companion backend
- 改造成多渠道聊天网关
- 研究 companion-style memory architecture
- 继续接 MCP / tools / custom channels

## License

MIT
