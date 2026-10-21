"""多目标拼单组合求解器。

问题建模：
  N 个人一起点麦当劳，每人有预算 / 热量上限 / 忌口 / 偏好；
  在满足所有人**硬约束**的前提下，让整体「吃得开心 + 花得聪明」。
  硬约束（不可破）：个人预算、热量上限、忌口关键词 / 标签；
  软目标（尽量优）：偏好命中数、标价节省、共享加餐凑单。

设计取舍（重要，写在这里是为了不重复踩坑）：
  套餐最终价依赖 MCP calculate-price（含券、含配送费），且每 Token
  限流 600 次/分钟。因此求解器只基于菜单标价做本地枚举，输出 Top-K
  候选方案，再由上层对少量候选调用 calculate-price 精排——
  绝不把限流额度烧在模型穷举上。

算法：候选生成（每人 Top-K bundle）-> 束搜索（beam search）组装全局方案
  -> 共享加餐补齐 -> 按得分排序输出。整个过程确定性（无随机种子依赖），
  可完整单测。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import MenuItem, Person

_BEAM_WIDTH = 12
_MAX_SNACK_OPTIONS = 6
_MAX_DRINK_OPTIONS = 4


@dataclass(frozen=True)
class Bundle:
    """一位参与者的一份餐：1 主食 + 0..1 小食 + 0..1 饮品。"""

    items: tuple[MenuItem, ...]
    score: int = 0
    relaxed: bool = False  # True 表示该 bundle 打破了个人预算（兜底方案）

    @property
    def price_fen(self) -> int:
        return sum(i.price_fen for i in self.items)

    @property
    def kcal(self) -> int:
        return sum(i.kcal or 0 for i in self.items)

    def label(self) -> str:
        return " + ".join(i.name for i in self.items)


@dataclass
class Plan:
    """一份全局拼单方案。"""

    assignments: dict[str, Bundle] = field(default_factory=dict)  # 姓名 -> Bundle
    shared: tuple[MenuItem, ...] = ()  # 共享加餐（如大薯条）
    notes: list[str] = field(default_factory=list)  # 人类可读的提示（如某人预算被突破）

    @property
    def total_fen(self) -> int:
        return sum(b.price_fen for b in self.assignments.values()) + sum(
            i.price_fen for i in self.shared
        )

    @property
    def per_capita_fen(self) -> int:
        n = len(self.assignments) or 1
        return self.total_fen // n


def _violates(item: MenuItem, person: Person) -> bool:
    """硬约束检查：热量 / 忌口关键词 / 忌口标签。"""
    if person.max_kcal and item.kcal and item.kcal > person.max_kcal:
        return True
    for kw in person.avoid_keywords:
        if kw and kw in item.name:
            return True
    if person.avoid_tags and (person.avoid_tags & set(item.tags)):
        return True
    return False


def _prefer_score(item: MenuItem, person: Person) -> int:
    """偏好命中加分：命中一个关键词 +100。"""
    return sum(100 for kw in person.prefer_keywords if kw and kw in item.name)


def candidate_bundles(menu: list[MenuItem], person: Person, top: int = 6) -> list[Bundle]:
    """为一位参与者生成候选餐组合。

    组合空间：主食 × (无 | 小食) × (无 | 饮品)，按预算 / 热量 / 忌口过滤后，
    每个主食只保留得分最高的一个组合（保证多样性），最终返回 Top-K。
    """
    mains = [i for i in menu if i.category == "main"]
    snacks = [i for i in menu if i.category == "snack"][:_MAX_SNACK_OPTIONS]
    drinks = [i for i in menu if i.category == "drink"][:_MAX_DRINK_OPTIONS]

    combos: list[Bundle] = []
    for main in mains:
        if _violates(main, person):
            continue
        snack_options: list[MenuItem | None] = [None]
        for s in snacks:
            if not _violates(s, person):
                snack_options.append(s)
        drink_options: list[MenuItem | None] = [None]
        for d in drinks:
            if not _violates(d, person):
                drink_options.append(d)
        for s in snack_options:
            for d in drink_options:
                items = tuple(x for x in (main, s, d) if x is not None)
                price = sum(x.price_fen for x in items)
                if price > person.budget_fen:
                    continue
                kcal = sum(x.kcal or 0 for x in items)
                if person.max_kcal and kcal > person.max_kcal:
                    continue
                # 评分：偏好命中为主（+100/个），餐的扎实程度为辅（热量/25），
                # 只有花掉预算的 80% 以上才开始温和惩罚浪费——
                # 预算是"上限"不是"目标"，吃开心比省小钱重要。
                overspend = max(0, price - person.budget_fen * 4 // 5)
                score = (
                    sum(_prefer_score(x, person) for x in items)
                    + kcal // 25
                    - overspend // 50
                )
                combos.append(Bundle(items=items, score=score))

    # 每个主食只保留最优组合，保证推荐多样性
    best_per_main: dict[str, Bundle] = {}
    for b in combos:
        key = b.items[0].code
        if key not in best_per_main or b.score > best_per_main[key].score:
            best_per_main[key] = b
    ranked = sorted(best_per_main.values(), key=lambda b: -b.score)

    if not ranked:
        # 兜底：某人约束太紧（预算/忌口）导致无可行解时，
        # 给出最便宜的主食单品，并标记 relaxed=True 让上层提示用户。
        affordable = [m for m in mains if not _violates(m, person)]
        pool = affordable or mains
        if pool:
            cheapest = min(pool, key=lambda m: m.price_fen)
            ranked = [Bundle(items=(cheapest,), score=-10**9, relaxed=True)]
    return ranked[:top]


def solve(
    menu: list[MenuItem],
    people: list[Person],
    shared_budget_fen: int | None = None,
    top_k: int = 3,
) -> list[Plan]:
    """求解拼单方案，返回按得分排序的前 top_k 个方案。"""
    if not people:
        return []

    cands = {p.name: candidate_bundles(menu, p) for p in people}

    # 束搜索：逐人扩展，每步只保留全局得分最高的 _BEAM_WIDTH 个部分方案
    partials: list[tuple[dict[str, Bundle], int]] = [({}, 0)]
    for p in people:
        nxt: list[tuple[dict[str, Bundle], int]] = []
        for assign, score in partials:
            for b in cands[p.name]:
                nxt.append(({**assign, p.name: b}, score + b.score))
        nxt.sort(key=lambda x: -x[1])
        partials = nxt[:_BEAM_WIDTH]

    plans: list[Plan] = []
    for assign, score in partials:
        notes: list[str] = []
        for p in people:
            if assign[p.name].relaxed:
                notes.append(
                    f"⚠️ {p.name} 的预算/忌口约束下无可行组合，"
                    f"已给出最便宜主食「{assign[p.name].label()}」，建议放宽预算"
                )
        plan = Plan(assignments=assign, notes=notes)
        # 共享加餐：若指定了共享预算，且最便宜的小食放得下，就凑一份
        if shared_budget_fen:
            snacks = sorted(
                (i for i in menu if i.category == "snack"), key=lambda i: i.price_fen
            )
            if snacks and snacks[0].price_fen <= shared_budget_fen:
                plan.shared = (snacks[0],)
        plans.append(plan)

    plans.sort(key=lambda p: -self_score(p))
    return plans[:top_k]


def self_score(plan: Plan) -> int:
    """全局得分：个人得分之和 + 多样性微调（共享加餐 +50）。"""
    base = sum(b.score for b in plan.assignments.values())
    return base + (50 if plan.shared else 0)
