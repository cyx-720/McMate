"""麦搭子命令行入口。

子命令：
  demo  —— 零配置演示：内置仿真菜单跑通「求解 → AA → 邀请卡」全流程
  plan  —— 接入真实麦当劳 MCP 的完整拼单流程（需要 MCD_MCP_TOKEN）
  tools —— 列出 MCP Server 当前可用工具

用法示例：
  python -m mcd_mate demo --html invite.html
  python -m mcd_mate plan --config examples/party.json --aa ordered
  python -m mcd_mate plan --config examples/party.json --order   # 显式开下单
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .aa_splitter import split_bill
from .combo_solver import solve
from .invite_card import render_html_card, render_text_card
from .models import MenuItem, OrderLine, Person
from .sample_data import DEMO_COUPON, DEMO_MENU, DEMO_PEOPLE
from .toon_parser import build_kcal_map, parse_toon


# --------------------------------------------------------------------- #
# 展示辅助
# --------------------------------------------------------------------- #
def _yuan(fen: int) -> str:
    return f"{fen / 100:.2f}"


def _print_plan(plan, people: list[Person]) -> list[OrderLine]:
    print("\n🍔 麦搭子 · 拼单方案")
    print("-" * 56)
    lines: list[OrderLine] = []
    for p in people:
        bundle = plan.assignments[p.name]
        print(f"  {p.name:<6} {bundle.label():<34} ¥{_yuan(bundle.price_fen)}")
        for item in bundle.items:
            lines.append(OrderLine(person=p.name, item=item, qty=1))
    if plan.shared:
        names = "、".join(i.name for i in plan.shared)
        print(f"  {'共享':<6} {names:<34} ¥{_yuan(sum(i.price_fen for i in plan.shared))}")
        for item in plan.shared:
            lines.append(OrderLine(person="共享", item=item, qty=1))
    for note in plan.notes:
        print(f"  {note}")
    return lines


def _apply_demo_coupon(lines: list[OrderLine], people: list[Person]) -> tuple[int, int, int]:
    gross = sum(l.subtotal_fen for l in lines)
    c = DEMO_COUPON
    discount = c["discount_fen"] if gross >= c["threshold_fen"] else 0
    payable = gross - discount
    amounts = split_bill(lines, people, mode="ordered", discount_fen=discount)
    print(f"\n🧾 原价 ¥{_yuan(gross)}｜券后 ¥{_yuan(payable)}｜省 ¥{_yuan(discount)}")
    print("-" * 56)
    for p in people:
        print(f"  {p.name:<6} 应付 ¥{_yuan(amounts.get(p.name, 0))}")
    return gross, payable, amounts


# --------------------------------------------------------------------- #
# 子命令：demo
# --------------------------------------------------------------------- #
def cmd_demo(args: argparse.Namespace) -> int:
    people = DEMO_PEOPLE
    print("📋 演示模式（内置仿真菜单，非实时数据）")
    print(f"   {len(people)} 人拼单：")
    for p in people:
        limit = f"，热量≤{p.max_kcal}kcal" if p.max_kcal else ""
        avoid = f"，忌 {'/'.join(p.avoid_tags)}" if p.avoid_tags else ""
        print(f"   - {p.name}：预算 ¥{_yuan(p.budget_fen)}{limit}{avoid}")

    plans = solve(DEMO_MENU, people, shared_budget_fen=1200, top_k=1)
    if not plans:
        print("无可行方案，请放宽约束。")
        return 1
    plan = plans[0]

    lines = _print_plan(plan, people)
    gross, payable, amounts = _apply_demo_coupon(lines, people)

    text = render_text_card(
        lines, people, amounts,
        store_name="麦当劳（科技园店）· 到店自取",
        deadline="今天 11:20 前",
        gross_fen=gross, payable_fen=payable,
    )
    print("\n" + text)

    if args.html:
        html = render_html_card(
            lines, people, amounts,
            store_name="麦当劳（科技园店）· 到店自取",
            deadline="今天 11:20 前回复 +1",
            gross_fen=gross, payable_fen=payable,
        )
        Path(args.html).write_text(html, encoding="utf-8")
        print(f"\n✅ HTML 邀请卡已生成：{args.html}（浏览器打开 → 截图即可发群）")
    return 0


# --------------------------------------------------------------------- #
# 子命令：plan（真实 MCP）
# --------------------------------------------------------------------- #
def _load_party_config(path: str) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    people = [
        Person(
            name=p["name"],
            budget_fen=int(p["budget_fen"]),
            max_kcal=p.get("max_kcal"),
            avoid_keywords=tuple(p.get("avoid_keywords", [])),
            avoid_tags=frozenset(p.get("avoid_tags", [])),
            prefer_keywords=tuple(p.get("prefer_keywords", [])),
        )
        for p in cfg["people"]
    ]
    return {"cfg": cfg, "people": people}


def _menu_from_mcp(raw: dict | list) -> list[MenuItem]:
    """把 MCP query-meals 的返回转成 MenuItem 列表。

    官方返回结构以 tools/list 与实时数据为准，这里做宽容解析：
    能认出 itemCode/code、itemName/name、price、category/tags 即可。
    """
    items: list[MenuItem] = []
    rows = raw if isinstance(raw, list) else raw.get("meals") or raw.get("items") or []
    for r in rows:
        if not isinstance(r, dict):
            continue
        code = r.get("itemCode") or r.get("code") or r.get("mealCode")
        name = r.get("itemName") or r.get("name") or r.get("mealName")
        price = r.get("price") or r.get("salePrice") or r.get("curPrice")
        if not (code and name and price):
            continue
        try:
            price_fen = int(round(float(price) * 100))  # MCP 返回「元」
        except (TypeError, ValueError):
            continue
        category = r.get("category") or "main"
        tags = frozenset(r.get("tags") or [])
        items.append(MenuItem(str(code), str(name), str(category), price_fen, None, tags))
    return items


def cmd_plan(args: argparse.Namespace) -> int:
    from .client import MCPError, McdClient  # 延迟导入，demo 模式不依赖

    party = _load_party_config(args.config)
    people = party["people"]
    cfg = party["cfg"]

    try:
        client = McdClient()
        print("🔌 正在连接麦当劳 MCP Server …")
        client.initialize()

        # 1) 时段感知：过滤在售菜单
        try:
            now = client.now_time_info()
            print(f"🕐 当前时间信息：{now if isinstance(now, str) else json.dumps(now, ensure_ascii=False)[:120]}")
        except MCPError as exc:
            print(f"⚠️ now-time-info 调用失败（不影响主流程）：{exc}")

        # 2) 附近门店
        lat, lng = cfg["latitude"], cfg["longitude"]
        stores = client.nearby_stores(lat, lng)
        store_name = "麦当劳（就近门店）"
        store_list = stores if isinstance(stores, list) else stores.get("stores", [])
        if store_list:
            first = store_list[0]
            store_name = first.get("storeName") or first.get("name") or store_name
        print(f"📍 已锁定门店：{store_name}")

        # 3) 菜单
        menu = _menu_from_mcp(client.meals())
        if not menu:
            print("⚠️ 未能从 query-meals 解析出菜单，请检查返回结构。")
            return 1
        print(f"📖 菜单载入：{len(menu)} 个餐品")

        # 4) 营养数据（TOON 文本）
        try:
            _, rows = parse_toon(client.nutrition_foods())
            kcal_map = build_kcal_map(rows)
            menu = [
                MenuItem(m.code, m.name, m.category, m.price_fen,
                         kcal_map.get(m.name, m.kcal), m.tags)
                for m in menu
            ]
            print(f"🥦 营养数据匹配：{sum(1 for m in menu if m.kcal)}/{len(menu)} 个餐品")
        except MCPError as exc:
            print(f"⚠️ 营养数据获取失败（热量约束将被跳过）：{exc}")

        # 5) 一键领券 + 本地求解
        try:
            client.auto_bind_coupons()
            print("🎫 已执行麦麦省一键领券")
        except MCPError as exc:
            print(f"⚠️ 一键领券失败：{exc}")

        plans = solve(menu, people, shared_budget_fen=cfg.get("shared_budget_fen"), top_k=1)
        if not plans:
            print("无可行方案，请放宽约束。")
            return 1
        lines = _print_plan(plans[0], people)

        # 6) 含券精算（只精算这一个方案，省限流额度）
        gross = sum(l.subtotal_fen for l in lines)
        try:
            price_result = client.calculate_price(
                [{"code": l.item.code, "quantity": l.qty} for l in lines]
            )
            print(f"💰 calculate-price 返回：{json.dumps(price_result, ensure_ascii=False)[:300]}")
        except MCPError as exc:
            print(f"⚠️ calculate-price 调用失败，退回标价估算：{exc}")
        payable = gross  # 精算成功后可由上层解析 price_result 覆盖
        amounts = split_bill(lines, people, mode=args.aa)
        for p in people:
            print(f"  {p.name:<6} 应付 ¥{_yuan(amounts.get(p.name, 0))}")

        text = render_text_card(lines, people, amounts, store_name=store_name,
                                gross_fen=gross, payable_fen=payable)
        print("\n" + text)
        if args.html:
            Path(args.html).write_text(
                render_html_card(lines, people, amounts, store_name=store_name,
                                 gross_fen=gross, payable_fen=payable),
                encoding="utf-8",
            )
            print(f"✅ HTML 邀请卡已生成：{args.html}")

        # 7) 下单：必须显式 --order 且人工输入确认
        if args.order:
            print("\n⚠️ 即将创建真实订单（create-order）。")
            answer = input("确认下单？输入 yes 继续，其他任意键取消：").strip().lower()
            if answer == "yes":
                result = client.create_order()
                print(f"🧾 订单已创建：{json.dumps(result, ensure_ascii=False)[:500]}")
                print("💳 请打开支付链接扫码完成付款（Agent 不代付）。")
            else:
                print("已取消，未创建任何订单。")
        else:
            print("\nℹ️ 当前为「只算单、不下单」模式。确认方案后追加 --order 才会创建订单。")
        return 0
    except MCPError as exc:
        print(f"❌ MCP 调用失败：{exc}")
        return 1


# --------------------------------------------------------------------- #
# 子命令：tools
# --------------------------------------------------------------------- #
def cmd_tools(_args: argparse.Namespace) -> int:
    from .client import MCPError, McdClient

    try:
        tools = McdClient().list_tools()
    except MCPError as exc:
        print(f"❌ {exc}")
        return 1
    print(f"🔧 MCP Server 共 {len(tools)} 个工具：")
    for t in tools:
        print(f"  - {t.get('name')}: {t.get('description', '')[:60]}")
    return 0


# --------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcd_mate", description="麦搭子 · 麦当劳拼单决策助手"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="零配置演示（内置仿真菜单）")
    p_demo.add_argument("--html", help="输出 HTML 邀请卡路径")
    p_demo.set_defaults(func=cmd_demo)

    p_plan = sub.add_parser("plan", help="接入真实麦当劳 MCP 的拼单流程")
    p_plan.add_argument("--config", required=True, help="拼单配置 JSON，见 examples/party.json")
    p_plan.add_argument("--aa", default="ordered",
                        choices=["ordered", "equal", "host", "weighted"], help="AA 模式")
    p_plan.add_argument("--html", help="输出 HTML 邀请卡路径")
    p_plan.add_argument("--order", action="store_true",
                        help="允许调用 create-order（仍需人工确认，Agent 不代付）")
    p_plan.set_defaults(func=cmd_plan)

    p_tools = sub.add_parser("tools", help="列出 MCP Server 可用工具")
    p_tools.set_defaults(func=cmd_tools)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
