# workbuddy.md — WorkBuddy 开发上下文

> 本文件记录「麦搭子 McMate」使用腾讯 WorkBuddy 智能体进行开发的真实对话上下文，
> 用于核验本项目符合 2026 麦当劳程序员创意开发大赛 WorkBuddy 专项奖励条件
> （参赛项目须真实使用腾讯 WorkBuddy 智能体开发）。

## 会话目标

2026-10-20，开发者（本项目 Owner）在 WorkBuddy 中提出：
"我参加麦当劳 MCP 开发大赛，基于麦当劳中国 MCP 能力给我生成一个参赛 Skill"，
并提供了赛事 PDF 与公众号推文链接。目标是在 10-25 23:59 报名截止前，
交付一个**差异化、可运行、文件齐全**的开源参赛项目。

## 关键对话与决策记录

### 1. 需求澄清与规则抓取

- 指令："先看比赛资料，确认参赛要求再动手。"
- WorkBuddy 读取了赛事 PDF（README 打印件），并抓取了 GitHub 官方活动仓库的
  `README.md` 与 `activityGuidelines.md`，确认硬性要求：
  - 仓库须含 README.md / CONTEST_DECLARATION.md（原文不可改）/ MCP_INTEGRATION.md /
    mcp-config.example.json（仅环境变量占位符）/ 源代码；
  - 仓库创建时间须在 2025-12-25 至 2026-10-25 之间；
  - 报名 Issue 正文三行格式，标题与正文间不能换行，地址不能用 Markdown 链接；
  - 排名按 GitHub 公开 Star 数，2026-10-26 00:00 定榜。

### 2. 竞品调研与差异化定位

- 指令："看看现在榜上都是什么项目，别撞车。"
- 调研结论（RANKING.md 快照 + 社区复盘文章）：104 个进榜项目中，
  前三名（611 / 512 / 491 stars）全是"优惠券省钱"方向，营养卡路里类也已扎堆，
  亲子活动地图有一个。**"多人拼单决策"场景空缺**。
- 决策：做「麦搭子」——办公室/宿舍拼单的决策助手。
  差异化理由：① 场景高频且未被占据；② 天然带分享裂变（拼单邀请卡截图发群，
  卡片页脚带回仓库链接）；③ 能用上更长的 MCP 工具链（门店/菜单/营养/券/
  计价/团餐），MCP_INTEGRATION.md 更有说服力。

### 3. 架构设计

- 指令："先想清楚架构再写码。"
- WorkBuddy 提出并解释了关键取舍：**本地求解 + MCP 精算的两段式架构**。
  理由来自官方限流条款（每 Token 600 次/分钟）："主食 × 小食 × 饮品"的组合枚举
  放在本地（combo_solver.py，束搜索，确定性输出），只把 Top-1 方案交给
  `calculate-price` 精算。该决策记录在 MCP_INTEGRATION.md 第 4 节。
- 数据模型约定：金额内部一律用「分」（int），因为 MCP 的 query-meals 返回「元」
  字符串而 calculate-price 返回「分」，单位混用是社区复盘里点名的坑。

### 4. 编码与联调

- 指令："把项目骨架和核心代码写出来，跑通 demo。"
- WorkBuddy 生成了 `mcd_mate` 包：models / toon_parser / combo_solver /
  aa_splitter / invite_card / client / sample_data / cli，共 8 个模块，
  以及 19 个 unittest 用例。
- 联调记录：
  - 首轮 demo 输出偏"素"（全员单品）→ WorkBuddy 定位到评分函数过度惩罚价格
    （`- price // 100` 让最便宜的单品永远得分最高），改为
    "偏好命中 + 热量/25 - 超预算 80% 部分/50"，并为演示菜单补充 6 个套餐项
    （真实 query-meals 本就会返回套餐）。复跑后方案恢复正常。
  - `python -m mcd_mate` 报 "No module named mcd_mate.__main__" →
    补 `__main__.py` 入口后跑通。
- 19 个单测全部通过；demo 全流程（求解 → 满100减20 演示券 → ordered AA →
  文本卡 + HTML 邀请卡）零配置可复现。

### 5. 参赛文件生成

- 指令："按官方要求把参赛文件备齐，CONTEST_DECLARATION 用原文。"
- WorkBuddy 从官方仓库抓取 CONTEST_DECLARATION.md 原文并原样落入仓库；
  MCP_INTEGRATION.md 中逐个工具对照官方 mcd-mcp-server README 的工具表核对，
  未使用的工具如实标注"默认不调用"。

## 产出文件清单

| 文件 | 说明 |
| --- | --- |
| `mcd_mate/models.py` | 数据模型（金额以「分」存储） |
| `mcd_mate/toon_parser.py` | TOON 营养数据解析（含逗号溢出容错） |
| `mcd_mate/combo_solver.py` | 多目标组合求解（束搜索，确定性） |
| `mcd_mate/aa_splitter.py` | 四种 AA 模式，精确到分 |
| `mcd_mate/invite_card.py` | 文本卡 + HTML 邀请卡 |
| `mcd_mate/client.py` | MCP Streamable HTTP 客户端（标准库） |
| `mcd_mate/sample_data.py` | 演示菜单与演示用户 |
| `mcd_mate/cli.py` / `__main__.py` | 命令行入口（demo / plan / tools） |
| `tests/test_solver.py` | 19 个单元测试（stdlib unittest） |
| `SKILL.md` | WorkBuddy Skill 编排指令 |
| `README.md` / `MCP_INTEGRATION.md` / `CONTEST_DECLARATION.md` | 参赛必需文件 |
| `mcp-config.example.json` | 脱敏配置（仅 `${MCD_MCP_TOKEN}` 占位符） |

## 开发环境

- 智能体：腾讯 WorkBuddy（本项目在 WorkBuddy 会话中完成需求分析、竞品调研、
  架构设计、编码、测试与文档撰写的全流程）
- 运行时：Python 3.13（零第三方依赖）
- MCP Server：麦当劳中国官方（https://mcp.mcd.cn）
