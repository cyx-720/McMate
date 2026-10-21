"""AA 分摊计算。

原则：金额精确到分；除不尽的余数统一并给第一个人（东道主兜底），
避免出现「0.3333333 元」这种让微信群吵起来的数据。

四种模式：
  ordered —— 各付各的：优惠金额按各人原价占比分摊（谁买得多谁享受得多）
  equal   —— 人均均摊：实付总额 / 人数
  host    —— 东道主请客：第一个人全额，其余 0
  weighted—— 自定义权重：按 {姓名: 权重} 分摊（如领导 1.5 倍）
"""

from __future__ import annotations

from .models import OrderLine, Person


def split_bill(
    lines: list[OrderLine],
    people: list[Person],
    mode: str = "ordered",
    discount_fen: int = 0,
    weights: dict[str, float] | None = None,
) -> dict[str, int]:
    """计算每位参与者应付金额（分）。

    lines      : 订单行（谁买了什么）
    people     : 参与者列表（决定分摊名单与顺序）
    mode       : ordered / equal / host / weighted
    discount_fen: 优惠总金额（分），按模式分摊
    weights    : mode=weighted 时的权重表，缺失者默认 1.0
    """
    names = [p.name for p in people]
    if not names:
        return {}

    gross_fen = sum(l.subtotal_fen for l in lines)
    payable_fen = max(gross_fen - discount_fen, 0)

    if mode == "equal":
        base = payable_fen // len(names)
        result = {n: base for n in names}
        result[names[0]] += payable_fen - base * len(names)
        return result

    if mode == "host":
        return {n: (payable_fen if n == names[0] else 0) for n in names}

    if mode == "weighted":
        weights = weights or {}
        total_w = sum(weights.get(n, 1.0) for n in names)
        result = {n: int(payable_fen * weights.get(n, 1.0) / total_w) for n in names}
        result[names[0]] += payable_fen - sum(result.values())
        return result

    if mode != "ordered":
        raise ValueError(f"未知 AA 模式: {mode}（可选 ordered/equal/host/weighted）")

    # ordered：先按原价归集，再把优惠按原价比例分摊
    per_person = {n: 0 for n in names}
    for line in lines:
        if line.person in per_person:
            per_person[line.person] += line.subtotal_fen
    if gross_fen == 0:
        return per_person
    for n in names:
        share = round(discount_fen * per_person[n] / gross_fen)
        per_person[n] = max(per_person[n] - share, 0)
    # 补齐舍入误差，保证分毫不差
    per_person[names[0]] += payable_fen - sum(per_person.values())
    return per_person
