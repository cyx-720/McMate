"""拼单邀请卡生成。

两种形态：
  render_text_card —— 纯文本，可直接粘贴到微信群 / 飞书 / 钉钉；
  render_html_card —— 自包含 HTML（内联样式，无外部依赖），
                      手机截图即可分享，页脚自带项目仓库链接——
                      这是本项目唯一的"增长引擎"：每张被截图发群的卡片，
                      都是一次回到 GitHub 的入口。

设计约束：HTML 必须单文件、无 JS 依赖（截图分享场景）、
宽度适配手机（max-width 420px 左右）。
"""

from __future__ import annotations

from .models import OrderLine, Person


def _fmt_yuan(fen: int) -> str:
    return f"{fen / 100:.2f}"


def render_text_card(
    lines: list[OrderLine],
    people: list[Person],
    amounts: dict[str, int],
    store_name: str = "麦当劳（就近门店）",
    deadline: str = "今天 11:20 前",
    gross_fen: int = 0,
    payable_fen: int = 0,
    repo_url: str = "https://github.com/<你的用户名>/mcd-mate",
) -> str:
    """生成微信群可直接粘贴的文本邀请卡。"""
    total_qty = sum(l.qty for l in lines)
    saved_fen = max(gross_fen - payable_fen, 0)
    lines_out: list[str] = []
    lines_out.append("🍔 麦搭子 · 拼单邀请")
    lines_out.append(f"📍 门店：{store_name}")
    lines_out.append(f"⏰ 截止：{deadline}，回复「+1」即参团")
    joined = len([n for n in amounts if amounts.get(n) is not None])
    lines_out.append(f"👥 已参团：{joined}/{len(people)} 人")
    lines_out.append("——————————————")
    by_person: dict[str, list[OrderLine]] = {}
    for line in lines:
        by_person.setdefault(line.person, []).append(line)
    for p in people:
        own = by_person.get(p.name, [])
        if not own:
            lines_out.append(f"☐ {p.name}：待点餐")
            continue
        detail = "；".join(
            f"{l.item.name}×{l.qty}" if l.qty > 1 else l.item.name for l in own
        )
        lines_out.append(f"☑ {p.name}：{detail}（¥{_fmt_yuan(amounts.get(p.name, 0))}）")
    lines_out.append("——————————————")
    if saved_fen > 0:
        lines_out.append(
            f"🎫 合计 {total_qty} 件，原价 ¥{_fmt_yuan(gross_fen)}，"
            f"券后 ¥{_fmt_yuan(payable_fen)}，省 ¥{_fmt_yuan(saved_fen)}"
        )
    else:
        lines_out.append(f"🧾 合计 {total_qty} 件，¥{_fmt_yuan(payable_fen)}")
    lines_out.append(f"💬 本卡由「麦搭子 McMate」生成 → {repo_url}")
    return "\n".join(lines_out)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麦搭子 · 拼单邀请</title>
<style>
  body { margin:0; padding:24px 12px; background:#f6f1e7;
         font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; }
  .card { max-width:400px; margin:0 auto; background:#fff; border-radius:20px;
          overflow:hidden; box-shadow:0 8px 30px rgba(0,0,0,.08); }
  .head { background:#DA291C; color:#fff; padding:20px 22px 16px; }
  .head h1 { margin:0; font-size:20px; letter-spacing:1px; }
  .head .sub { margin-top:6px; font-size:12px; opacity:.85; }
  .meta { display:flex; justify-content:space-between; padding:14px 22px;
          background:#FFC72C; color:#3d2b00; font-size:13px; font-weight:600; }
  .body { padding:18px 22px 8px; }
  .person { display:flex; align-items:flex-start; padding:9px 0;
            border-bottom:1px dashed #eee; }
  .person:last-child { border-bottom:none; }
  .avatar { width:34px; height:34px; border-radius:50%; background:#DA291C;
            color:#fff; font-size:15px; font-weight:700; flex:0 0 34px;
            display:flex; align-items:center; justify-content:center;
            margin-right:12px; }
  .who { font-weight:700; font-size:14px; color:#222; }
  .what { font-size:12.5px; color:#777; margin-top:2px; line-height:1.5; }
  .pay { margin-left:auto; font-weight:800; color:#DA291C; font-size:15px;
         white-space:nowrap; padding-left:8px; }
  .pay.pending { color:#bbb; font-weight:500; }
  .total { margin:10px 22px 0; padding:14px 16px; background:#faf7f0;
           border-radius:14px; }
  .total .row { display:flex; justify-content:space-between; font-size:13px;
                color:#555; padding:3px 0; }
  .total .row.final { font-size:16px; font-weight:800; color:#222;
                      padding-top:8px; }
  .total .save { color:#0a8a3d; font-weight:700; }
  .cta { text-align:center; padding:16px 22px 20px; font-size:13px; color:#888; }
  .cta b { color:#DA291C; }
  .foot { text-align:center; font-size:11px; color:#aaa; padding:0 22px 18px; }
  .foot a { color:#aaa; text-decoration:none; }
</style>
</head>
<body>
<div class="card">
  <div class="head">
    <h1>🍔 麦搭子 · 拼单邀请</h1>
    <div class="sub">一个人吃是快餐，一群人才是麦门</div>
  </div>
  <div class="meta">
    <span>📍 __STORE__</span>
    <span>⏰ __DEADLINE__</span>
  </div>
  <div class="body">
__PERSON_ROWS__
  </div>
  <div class="total">
    <div class="row"><span>原价合计</span><span>¥__GROSS__</span></div>
    <div class="row"><span>优惠券已抵</span><span class="save">-¥__SAVED__</span></div>
    <div class="row final"><span>实付（人均 ¥__AVG__）</span><span>¥__PAYABLE__</span></div>
  </div>
  <div class="cta">回复 <b>「+1」</b> 参团，或点 <b>「我要改」</b> 告诉搭子你的新选择</div>
  <div class="foot">本卡由「麦搭子 McMate」生成 · <a href="__REPO__">__REPO__</a></div>
</div>
</body>
</html>
"""


def render_html_card(
    lines: list[OrderLine],
    people: list[Person],
    amounts: dict[str, int],
    store_name: str = "麦当劳（就近门店）",
    deadline: str = "今天 11:20 前回复 +1",
    gross_fen: int = 0,
    payable_fen: int = 0,
    repo_url: str = "https://github.com/<你的用户名>/mcd-mate",
) -> str:
    """生成自包含 HTML 邀请卡（截图即分享）。"""
    by_person: dict[str, list[OrderLine]] = {}
    for line in lines:
        by_person.setdefault(line.person, []).append(line)

    rows: list[str] = []
    for p in people:
        own = by_person.get(p.name, [])
        initial = p.name[:1] if p.name else "?"
        if own:
            what = "；".join(
                f"{l.item.name}×{l.qty}" if l.qty > 1 else l.item.name for l in own
            )
            pay = f'<div class="pay">¥{_fmt_yuan(amounts.get(p.name, 0))}</div>'
        else:
            what = "待点餐…"
            pay = '<div class="pay pending">待定</div>'
        rows.append(
            f'    <div class="person">\n'
            f'      <div class="avatar">{initial}</div>\n'
            f'      <div><div class="who">{p.name}</div>'
            f'<div class="what">{what}</div></div>\n'
            f"      {pay}\n"
            f"    </div>"
        )

    saved_fen = max(gross_fen - payable_fen, 0)
    n = len(people) or 1
    html = _HTML_TEMPLATE
    html = html.replace("__STORE__", store_name)
    html = html.replace("__DEADLINE__", deadline)
    html = html.replace("__PERSON_ROWS__", "\n".join(rows))
    html = html.replace("__GROSS__", _fmt_yuan(gross_fen))
    html = html.replace("__SAVED__", _fmt_yuan(saved_fen))
    html = html.replace("__PAYABLE__", _fmt_yuan(payable_fen))
    html = html.replace("__AVG__", _fmt_yuan(payable_fen // n))
    html = html.replace("__REPO__", repo_url)
    return html
