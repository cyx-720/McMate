"""TOON 格式营养数据解析器。

麦当劳 MCP 的 list-nutrition-foods 工具返回的不是 JSON，而是 TOON
（Token-Oriented Object Notation）文本：

  首行是字段定义头，形如
      {productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  之后每一行对应一个餐品，字段顺序以首行定义为准。

两个实测出来的坑（复用价值高于结论本身）：

1. nutritionDescription 可能是 null，也可能自身包含逗号——
   因此不能对整行按固定位置 split(",") 了事；
2. 字段顺序以定义头为准，不写死。

本模块的容错策略：
  - 行内逗号数多于字段数时，优先把多余片段合并进"自由文本字段"
    （字段名含 description / note / remark / desc 者），否则退化为合并进
    第 2 个字段（营养表里第 2 个字段通常是描述），再不行就丢弃多余片段；
  - 空行与 # / // 注释行直接跳过；
  - null / 空串统一转为 None。
"""

from __future__ import annotations

from typing import Any


def _split_header(line: str) -> list[str]:
    """解析 TOON 定义头：{a,b,c}: -> ['a', 'b', 'c']"""
    body = line.strip()
    if body.startswith("{"):
        body = body[1:]
    if body.endswith("}:"):
        body = body[:-2]
    elif body.endswith(":"):
        body = body[:-1]
    if body.endswith("}"):
        body = body[:-1]
    return [f.strip() for f in body.split(",") if f.strip()]


def _free_text_field_index(fields: list[str]) -> int | None:
    """找出最可能容纳逗号的自由文本字段下标。"""
    for i, f in enumerate(fields):
        low = f.lower()
        if any(k in low for k in ("description", "desc", "note", "remark")):
            return i
    return None


def parse_toon(text: str) -> tuple[list[str], list[dict[str, Any]]]:
    """解析 TOON 文本，返回 (字段列表, 行字典列表)。

    任何一行解析失败都不会抛异常——坏行静默跳过，保证批量数据可用。
    """
    fields: list[str] = []
    rows: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        if not fields:
            if line.startswith("{"):
                fields = _split_header(line)
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == len(fields):
            values = parts
        elif len(parts) > len(fields):
            # 逗号溢出：合并进自由文本字段（或退化到第 2 个字段）
            idx = _free_text_field_index(fields)
            if idx is None:
                idx = 1 if len(fields) > 1 else 0
            head, tail = parts[:idx], parts[idx + (len(parts) - len(fields)) + 1 :]
            values = head + [",".join(parts[idx : idx + (len(parts) - len(fields)) + 1])] + tail
        else:
            values = parts + [None] * (len(fields) - len(parts))
        row = {}
        for f, v in zip(fields, values):
            if v is None or v == "" or v.lower() == "null":
                row[f] = None
            else:
                row[f] = v
        rows.append(row)
    return fields, rows


def build_kcal_map(nutrition_rows: list[dict[str, Any]]) -> dict[str, int]:
    """从营养行中提取 {餐品名称: 热量(千卡)}。

    能拿到能量就换算（1 千卡 ≈ 4.184 千焦），拿不到就跳过。
    名称与 query-meals 的餐品名对齐靠上层做模糊匹配。
    """
    kcal_map: dict[str, int] = {}
    for row in nutrition_rows:
        name = row.get("productName") or row.get("name")
        if not name:
            continue
        kcal = row.get("energyKcal") or row.get("kcal")
        if kcal is None:
            kj = row.get("energyKj")
            try:
                kcal = round(float(kj) / 4.184) if kj else None
            except (TypeError, ValueError):
                kcal = None
        try:
            kcal_map[str(name)] = int(float(kcal))
        except (TypeError, ValueError):
            continue
    return kcal_map
