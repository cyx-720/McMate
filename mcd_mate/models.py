"""共享数据模型。

金额单位约定（重要）：
  内部一律以「分」（int）存储与计算，避免浮点误差；
  仅在最终展示层格式化为「元」。
这与麦当劳 MCP 的实际行为一致：query-meals 返回「元」（通常是字符串），
calculate-price 返回「分」，展示层必须除以 100。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    """菜单中的单个餐品。

    code     : MCP query-meals 返回的餐品编码，下单时原样回传
    name     : 餐品名称
    category : main=主食 / snack=小食 / drink=饮品 / dessert=甜品
    price_fen: 标价（分）
    kcal     : 热量（千卡），来自 list-nutrition-foods；缺失时为 None
    tags     : 标签集合，如 {"辣", "新品"}，来自 query-meals
    """

    code: str
    name: str
    category: str
    price_fen: int
    kcal: int | None = None
    tags: frozenset[str] = frozenset()

    @property
    def price_yuan(self) -> str:
        """展示层：分 -> 元 字符串。"""
        return f"{self.price_fen / 100:.2f}"


@dataclass
class Person:
    """一位拼单参与者的约束与偏好。"""

    name: str
    budget_fen: int                       # 个人预算（分）
    max_kcal: int | None = None           # 单餐热量上限（千卡），None 表示不限
    avoid_keywords: tuple[str, ...] = ()  # 名称关键词黑名单，如 ("辣",)
    avoid_tags: frozenset[str] = frozenset()  # 标签黑名单，如 {"辣"}
    prefer_keywords: tuple[str, ...] = ()     # 偏好关键词，命中加分


@dataclass
class OrderLine:
    """订单行：某位参与者点了某个餐品 N 份。"""

    person: str
    item: MenuItem
    qty: int = 1

    @property
    def subtotal_fen(self) -> int:
        return self.item.price_fen * self.qty
