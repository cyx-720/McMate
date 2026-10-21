# 麦搭子 McMate

> 一个人吃是快餐，一群人才是麦门。
>
> 基于麦当劳中国 MCP（Model Context Protocol）能力开发的**拼单决策助手**：
> 一群人要点麦当劳时，谁吃什么、怎么凑套餐最划算、优惠券怎么用、钱怎么 AA——
> 一个 Skill 全流程搞定，还能一键生成可以截图发微信群的拼单邀请卡。

[![MCP](https://img.shields.io/badge/MCP-McDonald's%20China-DA291C)](https://github.com/M-China/mcd-mcp-server)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![ Contest](https://img.shields.io/badge/2026%20麦当劳程序员创意开发大赛-参赛作品-FFC72C)](https://github.com/M-China/mcd-developer-innovation-challenge)

## 它解决什么问题

每天中午，办公室 / 宿舍 / 课题组里都会上演同一幕：

- **"今天吃啥？"** 讨论 15 分钟，无疾而终；
- **谁点、点什么** 全靠吼，统计全靠截图爬楼；
- **套餐凑单** 永远凑不到最优，优惠券躺在卡包里过期；
- **AA 算账** 脸红到需要建一个 Excel。

麦搭子把这一切压缩成 30 秒：输入人数和约束，输出**推荐方案 + 每人金额 + 可分享的拼单邀请卡**，
愿意的话，最后一步才把订单创建权交回给你（支付始终由人完成）。

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 🧮 多目标组合求解 | 本地枚举「主食 × 小食 × 饮品」组合，在预算 / 热量 / 忌口硬约束下求整体最优 |
| 🎫 券后精算 | 先用本地求解锁定 Top-K 候选，再调 MCP `calculate-price` 精排，省限流额度 |
| 🧾 四种 AA 模式 | 各付各的（券按原价比例分摊）/ 人均均摊 / 东道主请客 / 自定义权重 |
| 💳 邀请卡生成 | 文本卡直接发群，HTML 卡截图分享，自带项目链接 |
| 🛡️ 安全边界 | Agent 只建单不付款；`create-order` 必须显式 `--order` 且人工确认 |

## 30 秒上手（零配置 Demo）

无需 MCP Token，内置仿真菜单即可体验完整流程：

```bash
git clone https://github.com/<你的用户名>/mcd-mate.git
cd mcd-mate
pip install -r requirements.txt

# 一键演示：5 人拼单 → 方案 → AA → 邀请卡
python -m mcd_mate demo --html invite.html
```

输出示例：

```text
🍔 麦搭子 · 拼单方案（人均 ¥31.60，原价 ¥43.20，已省 26.8%）
——————————————————————————————
1. 阿伟   板烧鸡腿堡套餐（中薯+中可乐）        ¥33.00
2. 小林   双层吉士堡 + 麦乐鸡(4块)             ¥30.00
3. 大敏   麦香鱼 + 无糖可乐（控卡）             ¥24.50
4. 老周   巨无霸套餐（中薯+中可乐）             ¥34.50
5. 实习生  香芋派 + 玉米杯                      ¥15.00
———— 共享加餐：大薯条 ×1（富余预算自动凑单） ————
🎫 已匹配优惠券：满 100 减 20 → 实付 ¥158.00
```

## 接入真实麦当劳 MCP

前置条件：到 [麦当劳 MCP 开放平台](https://open.mcd.cn/mcp) 用手机号登录，
控制台点「激活」领取 MCP Token（免费）。

```bash
export MCD_MCP_TOKEN="你的Token"   # Windows PowerShell: $env:MCD_MCP_TOKEN="..."
python -m mcd_mate plan --config examples/party.json --aa ordered
```

流程：`now-time-info` → `query-nearby-stores` → `query-meals` → `list-nutrition-foods`
→ 本地求解 → `query-my-coupons` / `auto-bind-coupons` → `calculate-price` 精算 → 输出方案。
**默认只算单、不下单**；确认无误后追加 `--order` 才会调用 `create-order` 并返回支付链接，扫码付款仍由你完成。

也可以直接在 WorkBuddy 里当 Skill 用：把 `SKILL.md` 与 `mcd_mate/` 放入技能目录，
在【连接器】中按 `mcp-config.example.json` 配置 `mcd-mcp`，然后对麦搭子说：
"我们 4 个人拼麦当劳，预算人均 35，有人不吃辣"。

## 架构

```text
┌────────────────────────────────────────────────────┐
│  你（微信群 / WorkBuddy 对话框 / CLI）                  │
└───────────────┬────────────────────────────────────┘
                │ 自然语言需求
┌───────────────▼────────────────────────────────────┐
│  麦搭子 Skill（SKILL.md 编排）                        │
│   ├─ 约束解析：人数 / 预算 / 忌口 / 偏好 / 取餐方式      │
│   ├─ combo_solver.py   多目标组合求解（纯本地）         │
│   ├─ toon_parser.py    营养 TOON 数据解析             │
│   ├─ aa_splitter.py    AA 分摊，精确到分               │
│   └─ invite_card.py    邀请卡（文本 + HTML）           │
└───────────────┬────────────────────────────────────┘
                │ 少量精选调用
┌───────────────▼────────────────────────────────────┐
│  麦当劳中国 MCP Server（https://mcp.mcd.cn）          │
│   33 个工具：门店 / 菜单 / 营养 / 券 / 计价 / 下单      │
└────────────────────────────────────────────────────┘
```

**为什么本地先求解？** MCP 每 Token 限流 600 次/分钟。把「主食 × 小食 × 饮品」的
枚举放在本地，只对 Top-K 候选调用 `calculate-price`，既快又省额度——这是从
限流约束出发的设计，不是偷懒。

## 使用的 MCP 工具

| 工具 | 用途 |
| --- | --- |
| `now-time-info` | 判断当前时段（早餐/正餐/夜宵），过滤在售菜单 |
| `query-nearby-stores` | 按坐标找附近可用门店 |
| `query-meals` | 拉取门店在售菜单（分类 / 编码 / 标签） |
| `query-meal-detail` | 套餐组成与替换选项 |
| `list-nutrition-foods` | 餐品营养数据（TOON 格式，`toon_parser` 解析） |
| `query-my-coupons` / `query-store-coupons` / `auto-bind-coupons` | 券查询与一键领取 |
| `calculate-price` | 含券金额、配送费、应付总价精算 |
| `create-order` | 仅 `--order` 且人工确认后调用，返回支付链接 |

详见 [MCP_INTEGRATION.md](MCP_INTEGRATION.md)。

## 目录结构

```text
mcd-mate/
├── SKILL.md                  # WorkBuddy Skill 定义（编排指令）
├── README.md
├── CONTEST_DECLARATION.md    # 参赛声明（官方原文）
├── MCP_INTEGRATION.md        # MCP 接入说明
├── mcp-config.example.json   # 脱敏配置示例（仅环境变量占位符）
├── workbuddy.md              # WorkBuddy 开发上下文
├── mcd_mate/                 # 项目主体代码
│   ├── client.py             #   MCP Streamable HTTP 客户端
│   ├── models.py             #   数据模型（金额一律用「分」）
│   ├── toon_parser.py        #   TOON 营养数据解析
│   ├── combo_solver.py       #   多目标组合求解器
│   ├── aa_splitter.py        #   AA 分摊
│   ├── invite_card.py        #   邀请卡生成
│   ├── sample_data.py        #   演示菜单
│   └── cli.py                #   命令行入口
├── examples/                 # 使用示例
└── tests/                    # 单元测试（不依赖网络）
```

## 安全与合规

- 🔐 Token 只从环境变量 `MCD_MCP_TOKEN` 读取，配置示例仅含占位符；
- 💰 任何写操作（`create-order`）都需要显式开关 + 人工确认，Agent 不自动花钱；
- 📊 营养与价格数据以麦当劳官方实时接口为准，输出仅供参考，不构成医疗/营养建议；
- 🏷️ 本项目为独立开发的参赛作品，非麦当劳官方产品。

## Roadmap

- [ ] 邀请卡在线版（GitHub Pages，扫码即填）
- [ ] 麦乐送配送费感知的凑单优化
- [ ] 群投票模式（接龙统计谁还没回复）
- [ ] 历史拼单复盘："你们组上周人均超支 12%"

## 参赛信息

2026 麦当劳程序员创意开发大赛参赛作品，开发中真实使用腾讯 WorkBuddy 智能体
（见 [workbuddy.md](workbuddy.md)）。赛事规则：
[M-China/mcd-developer-innovation-challenge](https://github.com/M-China/mcd-developer-innovation-challenge)

## License

[MIT](LICENSE) © 2026 mcd-mate contributors
