# MCP_INTEGRATION.md — 麦搭子的麦当劳 MCP 接入说明

## 1. 接入的 MCP Server

| 项 | 值 |
| --- | --- |
| 服务 | 麦当劳中国 MCP Server（McDonald's China MCP Server） |
| 官方仓库 | https://github.com/M-China/mcd-mcp-server |
| 开放平台 | https://open.mcd.cn/mcp |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP（POST，JSON-RPC 2.0） |
| 鉴权 | 请求头 `Authorization: Bearer <MCD_MCP_TOKEN>` |
| Token 获取 | 开放平台手机号登录 → 控制台 → 「激活」，免费领取 |
| 限流 | 每 Token 每分钟最多 600 次请求，超限返回 429 |
| 客户端 | 本仓库 `mcd_mate/client.py`（仅依赖 Python 标准库） |

配置示例见 [mcp-config.example.json](mcp-config.example.json)：仅含环境变量占位符
`${MCD_MCP_TOKEN}`，仓库中不出现任何真实 Token。

## 2. 实际使用的 Tool 清单

麦搭子用到 9 个工具，全部来自麦当劳中国官方 MCP Server：

| Tool | 用途 | 调用时机 |
| --- | --- | --- |
| `now-time-info` | 获取当前时间，判断早餐 / 正餐 / 夜宵时段 | 流程第 1 步（过滤在售菜单） |
| `query-nearby-stores` | 按经纬度查询附近可用门店 | 流程第 2 步（锁定取餐门店） |
| `query-meals` | 查询门店当前可售菜单（分类 / 餐品编码 / 标签） | 流程第 3 步（构建求解输入） |
| `query-meal-detail` | 查询餐品详情与套餐组成、替换选项 | 生成"套餐替换"建议时 |
| `list-nutrition-foods` | 餐品营养数据（**返回 TOON 文本而非 JSON**） | 流程第 4 步（热量约束匹配） |
| `query-my-coupons` | 查询账户可用优惠券 | 券匹配阶段 |
| `query-store-coupons` | 查询当前门店可用优惠券 | 券匹配阶段 |
| `auto-bind-coupons` | 麦麦省一键领券（自动领取名下所有可领券） | 精算前一步 |
| `calculate-price` | 含券金额、配送费、应付总价精算 | 对本地求解的 Top-1 方案精算 |

写操作工具（`create-order` / `cancel-order` / `mall-create-order` / `draw-lottery` /
`party-order-create` 等）**默认不调用**；仅在用户追加 `--order` 开关并人工输入确认后，
才调用 `create-order` 创建订单并返回支付链接，扫码付款由用户本人完成。

## 3. 调用流程

```text
用户输入（人数/预算/忌口/偏好/取餐方式）
   │
   ▼
① now-time-info ────────────► 时段感知（早餐菜单 vs 正餐菜单）
   │
   ▼
② query-nearby-stores ──────► 附近门店列表，取第一家（或用户指定）
   │
   ▼
③ query-meals ──────────────► 门店菜单：编码/名称/分类/价格(元→分)/标签
   │
   ▼
④ list-nutrition-foods ─────► TOON 文本 ──► toon_parser.py 解析 ──► {餐品: 热量}
   │                              （自由文本字段含逗号，不能按固定位置 split）
   ▼
⑤ 本地求解 combo_solver.py ─► 多目标组合：预算/热量/忌口硬约束 + 偏好/扎实度软目标
   │                              （纯本地枚举，零 MCP 调用）
   ▼
⑥ query-my-coupons / query-store-coupons / auto-bind-coupons ──► 可用券 + 一键领券
   │
   ▼
⑦ calculate-price ──────────► 仅对 Top-1 方案精算：含券金额、配送费、应付总价
   │
   ▼
⑧ aa_splitter.py ──────────► 各付各的/均摊/请客/权重，精确到分
   │
   ▼
⑨ invite_card.py ──────────► 文本邀请卡 + HTML 邀请卡（截图发群）
   │
   ▼
（可选，需 --order 且人工确认）create-order ──► 订单 + 支付链接，人工扫码付款
```

## 4. 关键实现细节与踩坑记录

1. **价格单位不一致**：`query-meals` 返回「元」且通常是字符串，`calculate-price`
   返回「分」。展示层必须除以 100，否则用户会看到一个贵一百倍的价格。
   本仓库内部一律以「分」（int）存储，仅在展示层格式化（见 `models.py`）。
2. **营养数据是 TOON 不是 JSON**：`list-nutrition-foods` 首行是字段定义头
   `{productName,nutritionDescription,energyKj,energyKcal,...}:`，数据行中
   `nutritionDescription` 可能为 null、也可能自身含逗号。`toon_parser.py`
   采用"定义头定序 + 逗号溢出合并进自由文本字段"的策略，并对坏行静默跳过。
3. **限流优先的架构取舍**：套餐组合空间是「主食 × 小食 × 饮品」的笛卡尔积，
   若交给模型反复试错，600 次/分钟的额度很快见底。因此求解器在本地完成枚举，
   只把 Top-1 方案交给 `calculate-price` 精算——限流约束直接塑造了架构。
4. **429 退避**：`client.py` 内置最小调用间隔（50ms）与指数退避重试（最多 3 次）。
5. **SSE 响应兼容**：Streamable HTTP 的响应既可能是 `application/json`，
   也可能是 `text/event-stream`，客户端两种都解析。

## 5. 业务价值

- 对**拼单组织者**：把"统计谁点什么 + 算账 + 催回复"三件事压缩到 30 秒；
- 对**参团者**：忌口 / 控卡 / 预算被真正尊重，而不是"你随便点"；
- 对**麦当劳用户**：`auto-bind-coupons` 让卡包里躺着过期的券被用起来，
  `calculate-price` 让"凑单凑到最优"从经验变成计算；
- 对**MCP 生态**：示范了"消费品牌开放接口 → 个人 Agent 组合决策 →
  人工确认后写操作"的完整责任切分：单是 Agent 建的，钱是人扫的。
