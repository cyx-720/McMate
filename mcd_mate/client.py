"""麦当劳 MCP Streamable HTTP 客户端。

协议要点（来自官方 mcd-mcp-server 仓库）：
  - 接入地址 https://mcp.mcd.cn，传输协议 Streamable HTTP
  - 鉴权：Authorization: Bearer <MCD_MCP_TOKEN>，Token 在
    https://open.mcd.cn/mcp 控制台免费领取
  - 限流：每 Token 每分钟最多 600 次请求，超限返回 429
  - 响应可能是 application/json，也可能是 text/event-stream，均已处理

安全约定：
  - Token 只从环境变量 MCD_MCP_TOKEN 读取，任何代码路径都不接受
    硬编码 Token；
  - 本客户端对写操作（create-order 等）不做额外拦截，拦截策略由
    上层 CLI / Skill 负责（见 cli.py 的 --order 开关）。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

MCP_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-03-26"
_MIN_INTERVAL_SEC = 0.05  # 客户端侧最小调用间隔，主动远离 600 次/分钟红线
_MAX_RETRIES = 3


class MCPError(RuntimeError):
    """MCP 调用失败（含服务端返回的错误信息）。"""


class McdClient:
    """最小可用的麦当劳 MCP 客户端（仅依赖标准库）。"""

    def __init__(self, token: str | None = None, url: str = MCP_URL) -> None:
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        if not self.token:
            raise MCPError(
                "未找到 MCP Token。请先在 https://open.mcd.cn/mcp 控制台「激活」领取，"
                "并以环境变量 MCD_MCP_TOKEN 提供（切勿写进代码或提交到仓库）。"
            )
        self.url = url
        self.session_id: str | None = None
        self._req_id = 0
        self._last_call = 0.0
        self._initialized = False

    # ------------------------------------------------------------------ #
    # 基础 JSON-RPC 设施
    # ------------------------------------------------------------------ #
    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (固定官方地址)
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            raw = resp.read().decode("utf-8", errors="replace")
        return self._parse_response(raw)

    @staticmethod
    def _parse_response(raw: str) -> dict[str, Any]:
        """兼容 application/json 与 text/event-stream 两种响应体。"""
        text = raw.strip()
        if text.startswith("event:") or text.startswith("data:"):
            # SSE：取最后一条完整 data 帧
            data_lines = [
                ln[len("data:") :].strip()
                for ln in text.splitlines()
                if ln.startswith("data:")
            ]
            text = data_lines[-1] if data_lines else "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - 防御性分支
            raise MCPError(f"MCP 响应不是合法 JSON: {text[:200]}") from exc

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._req_id += 1
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        # 429 指数退避重试
        for attempt in range(_MAX_RETRIES):
            gap = time.monotonic() - self._last_call
            if gap < _MIN_INTERVAL_SEC:
                time.sleep(_MIN_INTERVAL_SEC - gap)
            self._last_call = time.monotonic()
            try:
                resp = self._post(payload)
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < _MAX_RETRIES - 1:
                    time.sleep(2**attempt)
                    continue
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                raise MCPError(f"MCP HTTP {exc.code}: {detail}") from exc
            if "error" in resp:
                raise MCPError(f"MCP 错误: {resp['error']}")
            return resp.get("result", {})
        raise MCPError("MCP 重试次数用尽（持续 429，请降低调用频率）")

    def initialize(self) -> dict[str, Any]:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcd-mate", "version": "1.0.0"},
            },
        )
        # 完成握手（通知，无响应体）
        try:
            self._post(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}
            )
        except MCPError:
            pass  # 部分服务端不要求该通知，忽略
        self._initialized = True
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        if not self._initialized:
            self.initialize()
        return self._rpc("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """调用一个 MCP 工具，返回其结构化内容（自动解包 content[0].text JSON）。"""
        if not self._initialized:
            self.initialize()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        content = result.get("content", [])
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text  # 例如 TOON 文本，交上层解析
        return result

    # ------------------------------------------------------------------ #
    # 麦搭子实际用到的工具封装（薄封装，参数名以官方文档 / tools/list 为准）
    # ------------------------------------------------------------------ #
    def now_time_info(self) -> Any:
        return self.call_tool("now-time-info")

    def nearby_stores(self, latitude: float, longitude: float) -> Any:
        return self.call_tool("query-nearby-stores", {"latitude": latitude, "longitude": longitude})

    def meals(self, **kwargs: Any) -> Any:
        """门店在售菜单。kwargs 依 tools/list 传入（如 storeCode / beCode）。"""
        return self.call_tool("query-meals", kwargs)

    def meal_detail(self, code: str) -> Any:
        return self.call_tool("query-meal-detail", {"code": code})

    def nutrition_foods(self) -> Any:
        """返回 TOON 文本（注意：不是 JSON）。"""
        return self.call_tool("list-nutrition-foods")

    def my_coupons(self) -> Any:
        return self.call_tool("query-my-coupons")

    def store_coupons(self, **kwargs: Any) -> Any:
        return self.call_tool("query-store-coupons", kwargs)

    def auto_bind_coupons(self) -> Any:
        """麦麦省一键领券。"""
        return self.call_tool("auto-bind-coupons")

    def calculate_price(self, items: list[dict[str, Any]], coupons: list[Any] | None = None) -> Any:
        """含券计价。items 结构以官方文档为准（餐品编码 + 数量 + 规格）。"""
        args: dict[str, Any] = {"items": items}
        if coupons:
            args["coupons"] = coupons
        return self.call_tool("calculate-price", args)

    def create_order(self, **kwargs: Any) -> Any:
        """创建订单，返回支付链接。写操作：调用前必须已获得用户明确确认。"""
        return self.call_tool("create-order", kwargs)
