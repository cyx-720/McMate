"""演示数据：一份仿真麦当劳菜单。

⚠️ 注意：本文件是**演示数据**，用于在没有 MCP Token 的情况下跑通
全流程（python -m mcd_mate demo）。餐品名 / 价格 / 热量贴近真实情况，
但不与任何实时菜单绑定；真实数据请始终以麦当劳 MCP 实时返回为准。

价格单位：分。热量单位：千卡。
"""

from __future__ import annotations

from .models import MenuItem, Person

DEMO_MENU: list[MenuItem] = [
    # ---- 主食 ----
    MenuItem("m_big-mac", "巨无霸", "main", 2550, 520),
    MenuItem("m_teriyaki", "板烧鸡腿堡", "main", 2100, 430),
    MenuItem("m_spicy", "麦辣鸡腿堡", "main", 2300, 560, tags=frozenset({"辣"})),
    MenuItem("m_fish", "麦香鱼", "main", 1950, 390),
    MenuItem("m_double-cheese", "双层吉士堡", "main", 1950, 480),
    MenuItem("m_mcchicken", "麦香鸡汉堡", "main", 1800, 470),
    MenuItem("m_egg-muffin", "吉士蛋麦满分", "main", 1600, 320, tags=frozenset({"早餐"})),
    MenuItem("m_sausage-muffin", "猪柳蛋麦满分", "main", 1700, 380, tags=frozenset({"早餐"})),
    # ---- 套餐（真实 query-meals 会一并返回，套餐价低于单品加总） ----
    MenuItem("set_big-mac", "巨无霸套餐(中薯中可乐)", "main", 3350, 930),
    MenuItem("set_teriyaki", "板烧鸡腿堡套餐(中薯中可乐)", "main", 2900, 930),
    MenuItem("set_spicy", "麦辣鸡腿堡套餐(中薯中可乐)", "main", 3150, 1060, tags=frozenset({"辣"})),
    MenuItem("set_fish", "麦香鱼套餐(中薯中可乐)", "main", 2750, 890),
    MenuItem("set_double-cheese", "双层吉士堡套餐(中薯中可乐)", "main", 2750, 980),
    MenuItem("set_mcchicken", "麦香鸡汉堡套餐(中薯中可乐)", "main", 2600, 890),
    # ---- 小食 ----
    MenuItem("s_fries-s", "薯条(小)", "snack", 750, 230),
    MenuItem("s_fries-m", "薯条(中)", "snack", 900, 320),
    MenuItem("s_fries-l", "薯条(大)", "snack", 1050, 420),
    MenuItem("s_mcnuggets-4", "麦乐鸡(4块)", "snack", 1100, 230),
    MenuItem("s_mcnuggets-6", "麦乐鸡(6块)", "snack", 1400, 340),
    MenuItem("s_corn-s", "玉米杯(小)", "snack", 850, 90),
    MenuItem("s_wings-2", "麦辣鸡翅(2块)", "snack", 1200, 260, tags=frozenset({"辣"})),
    # ---- 饮品 ----
    MenuItem("d_cola-m", "可口可乐(中)", "drink", 800, 180),
    MenuItem("d_cola-l", "可口可乐(大)", "drink", 950, 220),
    MenuItem("d_cola-zero-m", "无糖可乐(中)", "drink", 800, 10),
    MenuItem("d_cola-zero-l", "无糖可乐(大)", "drink", 950, 15),
    MenuItem("d_sprite-m", "雪碧(中)", "drink", 800, 170),
    MenuItem("d_oj-hot", "热香橙汁", "drink", 900, 150, tags=frozenset({"早餐"})),
    # ---- 甜品 ----
    MenuItem("t_taro-pie", "香芋派", "dessert", 850, 260),
    MenuItem("t_pineapple-pie", "菠萝派", "dessert", 850, 250),
    MenuItem("t_mcflurry", "麦旋风(奥利奥)", "dessert", 1150, 330),
    MenuItem("t_sundae", "新地(草莓)", "dessert", 900, 280),
]

DEMO_PEOPLE: list[Person] = [
    Person("阿伟", budget_fen=3500, prefer_keywords=("鸡",)),
    Person("小林", budget_fen=3200, prefer_keywords=("吉士",)),
    Person("大敏", budget_fen=2800, max_kcal=450, avoid_tags=frozenset({"辣"})),
    Person("老周", budget_fen=3600, prefer_keywords=("巨无霸",)),
    Person("实习生", budget_fen=1800),
]

# 演示优惠券：满 100 减 20（单位：分）
DEMO_COUPON = {"name": "满100减20", "threshold_fen": 10000, "discount_fen": 2000}
