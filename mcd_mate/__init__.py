"""麦搭子 McMate —— 麦当劳拼单决策助手。

基于麦当劳中国 MCP 能力的开源 Skill：多目标组合求解 + 券后精算 + AA 分摊
+ 拼单邀请卡生成。详见 README.md 与 SKILL.md。
"""

from .models import MenuItem, OrderLine, Person
from .combo_solver import Bundle, Plan, candidate_bundles, solve
from .aa_splitter import split_bill
from .toon_parser import build_kcal_map, parse_toon

__version__ = "1.0.0"
__all__ = [
    "MenuItem",
    "OrderLine",
    "Person",
    "Bundle",
    "Plan",
    "candidate_bundles",
    "solve",
    "split_bill",
    "parse_toon",
    "build_kcal_map",
]
