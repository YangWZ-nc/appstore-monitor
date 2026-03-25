#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
App Store 美区价格监控系统
支持：本体价格 + 内购价格监控
推送：Bark (iOS) / Telegram Bot
"""

import json
import os
import sys
import time
import random
import logging
import re
import traceback
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# 日志配置
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 常量 & 路径
# ─────────────────────────────────────────────
WATCHLIST_FILE   = "watchlist.json"
HISTORY_FILE     = "history_prices.json"
INDEX_HTML_FILE  = "index.html"

ITUNES_API_URL   = "https://itunes.apple.com/lookup"
APP_PAGE_URL     = "https://apps.apple.com/{country}/app/id{app_id}"

# 随机 User-Agent 池（当 fake-useragent 不可用时的备用列表）
FALLBACK_UA_LIST = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

# 重试参数
MAX_RETRIES    = 3
RETRY_DELAY    = 5   # 秒
REQUEST_DELAY  = (2, 5)  # 随机延迟范围（秒）

# ─────────────────────────────────────────────
# 推送配置（从环境变量读取）
# ─────────────────────────────────────────────
BARK_KEY         = os.environ.get("BARK_KEY", "")          # Bark 设备 Key
BARK_SERVER      = os.environ.get("BARK_SERVER", "https://api.day.app")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def get_random_ua() -> str:
    """获取随机 User-Agent"""
    try:
        from fake_useragent import UserAgent
        ua = UserAgent()
        return ua.random
    except Exception:
        return random.choice(FALLBACK_UA_LIST)


def make_headers() -> dict:
    """生成防反爬请求头"""
    return {
        "User-Agent": get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }


def request_with_retry(
    url: str,
    params: dict = None,
    headers: dict = None,
    timeout: int = 20,
) -> Optional[requests.Response]:
    """带重试机制的 HTTP GET 请求"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=headers or make_headers(),
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning(f"请求失败（第 {attempt}/{MAX_RETRIES} 次）: {url} → {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
    return None


def sleep_random():
    """随机延迟，降低被封禁风险"""
    delay = random.uniform(*REQUEST_DELAY)
    logger.debug(f"等待 {delay:.1f}s …")
    time.sleep(delay)


def load_json_file(path: str) -> dict:
    """加载 JSON 文件，文件不存在时返回空字典"""
    if not os.path.exists(path):
        logger.info(f"{path} 不存在，将创建新文件。")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"读取 {path} 失败: {e}")
        return {}


def save_json_file(path: str, data: dict):
    """保存 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"已保存: {path}")


# ═══════════════════════════════════════════════════════════
# 数据获取
# ═══════════════════════════════════════════════════════════

def fetch_app_info_from_api(app_id: str, country: str = "us") -> Optional[dict]:
    """
    通过 iTunes Lookup API 获取 App 基本信息及本体价格。
    返回示例：
      {
        "name": "Shadowrocket",
        "price": 2.99,
        "currency": "USD",
        "bundle_id": "...",
        "seller": "...",
        "icon_url": "...",
        "app_url": "..."
      }
    """
    resp = request_with_retry(
        ITUNES_API_URL,
        params={"id": app_id, "country": country, "entity": "software"},
    )
    if not resp:
        return None
    try:
        data = resp.json()
        results = data.get("results", [])
        if not results:
            logger.warning(f"iTunes API 未找到 App ID={app_id}")
            return None
        r = results[0]
        return {
            "name":      r.get("trackName", f"App {app_id}"),
            "price":     float(r.get("price", 0.0)),
            "currency":  r.get("currency", "USD"),
            "bundle_id": r.get("bundleId", ""),
            "seller":    r.get("sellerName", ""),
            "icon_url":  r.get("artworkUrl100", ""),
            "app_url":   r.get("trackViewUrl", ""),
            "genres":    r.get("genres", []),
        }
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"解析 iTunes API 响应失败 App ID={app_id}: {e}")
        return None


def fetch_iap_from_webpage(app_id: str, country: str = "us") -> list[dict]:
    """
    通过爬取 App Store 网页获取"Top In-App Purchases"列表。
    返回示例：
      [
        {"name": "1 Month Premium", "price": 4.99},
        {"name": "Lifetime Access",  "price": 29.99},
      ]
    """
    url = APP_PAGE_URL.format(country=country, app_id=app_id)
    resp = request_with_retry(url, headers=make_headers())
    if not resp:
        return []

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        iap_list = []

        # ── 方式 1：查找 JSON-LD 中的 inAppPurchase ──
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                obj = json.loads(script.string or "")
                offers = obj.get("offers", [])
                if isinstance(offers, list):
                    for offer in offers:
                        name  = offer.get("name", "")
                        price = offer.get("price", None)
                        if name and price is not None:
                            try:
                                iap_list.append({"name": name, "price": float(price)})
                            except ValueError:
                                pass
            except json.JSONDecodeError:
                pass

        if iap_list:
            logger.info(f"  [JSON-LD] 找到 {len(iap_list)} 个内购项目")
            return iap_list

        # ── 方式 2：CSS selector 解析内购区域 ──
        iap_section = soup.find("section", class_=re.compile(r"in-app", re.I))
        if not iap_section:
            iap_section = soup.find("div", class_=re.compile(r"iap|in.app", re.I))

        if iap_section:
            items = iap_section.find_all("li") or iap_section.find_all("div", class_=re.compile(r"item|row"))
            for item in items:
                text = item.get_text(separator="|", strip=True)
                parts = text.split("|")
                # 找价格：$X.XX 格式
                price_match = re.search(r"\$(\d+(?:\.\d{2})?)", text)
                if price_match and len(parts) >= 1:
                    name  = parts[0].strip()
                    price = float(price_match.group(1))
                    if name and price > 0:
                        iap_list.append({"name": name, "price": price})

        if iap_list:
            logger.info(f"  [CSS] 找到 {len(iap_list)} 个内购项目")
            return iap_list

        # ── 方式 3：全文正则兜底 ──
        pattern = re.compile(
            r'"name"\s*:\s*"([^"]+)"[^}]*?"price"\s*:\s*"?([\d.]+)"?',
            re.DOTALL,
        )
        for m in pattern.finditer(resp.text):
            name  = m.group(1)
            price = float(m.group(2))
            if price > 0 and name not in [i["name"] for i in iap_list]:
                iap_list.append({"name": name, "price": price})

        logger.info(f"  [Regex] 找到 {len(iap_list)} 个内购项目")
        return iap_list

    except Exception as e:
        logger.warning(f"解析内购失败 App ID={app_id}: {e}")
        return []


# ═══════════════════════════════════════════════════════════
# 比对逻辑
# ═══════════════════════════════════════════════════════════

def compare_prices(app_id: str, current: dict, history: dict) -> list[dict]:
    """
    比对当前价格与历史价格，返回降价事件列表。
    每个事件格式：
      {
        "app_id": ...,
        "app_name": ...,
        "type": "app" | "iap",
        "item_name": ...,
        "old_price": ...,
        "new_price": ...,
        "currency": "USD"
      }
    """
    alerts = []
    app_name = current.get("name", f"App {app_id}")
    currency = current.get("currency", "USD")

    # ── 本体价格比对 ──
    old_price = history.get("price")
    new_price = current.get("price")
    if old_price is not None and new_price is not None:
        if new_price < old_price:
            alerts.append({
                "app_id":    app_id,
                "app_name":  app_name,
                "type":      "app",
                "item_name": "App 本体",
                "old_price": old_price,
                "new_price": new_price,
                "currency":  currency,
            })
            logger.info(f"  ✅ 本体降价: ${old_price} → ${new_price}")
        elif new_price == 0.0 and old_price > 0:
            alerts.append({
                "app_id":    app_id,
                "app_name":  app_name,
                "type":      "app",
                "item_name": "App 本体（限免）",
                "old_price": old_price,
                "new_price": 0.0,
                "currency":  currency,
            })
            logger.info(f"  🎉 限时免费！")

    # ── 内购价格比对 ──
    old_iap: dict = {item["name"]: item["price"] for item in history.get("iap", [])}
    new_iap: dict = {item["name"]: item["price"] for item in current.get("iap", [])}

    for name, new_p in new_iap.items():
        old_p = old_iap.get(name)
        if old_p is not None and new_p < old_p:
            alerts.append({
                "app_id":    app_id,
                "app_name":  app_name,
                "type":      "iap",
                "item_name": name,
                "old_price": old_p,
                "new_price": new_p,
                "currency":  currency,
            })
            logger.info(f"  ✅ 内购降价: [{name}] ${old_p} → ${new_p}")

    return alerts


# ═══════════════════════════════════════════════════════════
# 消息推送
# ═══════════════════════════════════════════════════════════

def format_alert_message(alert: dict) -> tuple[str, str]:
    """格式化推送消息，返回 (title, body)"""
    name   = alert["app_name"]
    item   = alert["item_name"]
    old_p  = alert["old_price"]
    new_p  = alert["new_price"]
    cur    = alert["currency"]

    if new_p == 0.0:
        title = f"🎉 限免！{name}"
        body  = f"{item} 现在免费！\n原价：{cur} ${old_p:.2f}\n快去下载 👉 https://apps.apple.com/us/app/id{alert['app_id']}"
    else:
        pct   = int((1 - new_p / old_p) * 100) if old_p > 0 else 0
        title = f"💸 降价 {pct}%！{name}"
        body  = (
            f"{'App 本体' if alert['type'] == 'app' else '内购'}: {item}\n"
            f"原价：{cur} ${old_p:.2f}  →  现价：${new_p:.2f}（↓{pct}%）\n"
            f"🔗 https://apps.apple.com/us/app/id{alert['app_id']}"
        )
    return title, body


def send_bark(title: str, body: str):
    """发送 Bark 推送（iOS）"""
    if not BARK_KEY:
        logger.debug("BARK_KEY 未配置，跳过 Bark 推送。")
        return
    try:
        url = f"{BARK_SERVER}/{BARK_KEY}"
        payload = {
            "title":  title,
            "body":   body,
            "sound":  "minuet",
            "icon":   "https://is1-ssl.mzstatic.com/image/thumb/Purple116/v4/65/a5/3e/65a53e8b-dbb1-4a32-8c1d-6b0c56a00b10/AppIcon-0-0-1x_U007emarketing-0-0-0-7-0-0-sRGB-0-0-0-GLES2_U002c0-512MB-85-220-0-0.png/100x100bb.jpg",
            "group":  "AppStore监控",
        }
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            logger.info(f"  [Bark] 推送成功: {title}")
        else:
            logger.warning(f"  [Bark] 推送失败: HTTP {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        logger.error(f"  [Bark] 推送异常: {e}")


def send_telegram(title: str, body: str):
    """发送 Telegram Bot 推送"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram 配置不完整，跳过推送。")
        return
    try:
        text = f"*{title}*\n\n{body}"
        url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       text,
            "parse_mode": "Markdown",
        }
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            logger.info(f"  [Telegram] 推送成功: {title}")
        else:
            logger.warning(f"  [Telegram] 推送失败: {data.get('description', '')}")
    except Exception as e:
        logger.error(f"  [Telegram] 推送异常: {e}")


def send_notifications(alerts: list[dict]):
    """发送所有降价通知"""
    for alert in alerts:
        title, body = format_alert_message(alert)
        logger.info(f"发送通知: {title}")
        send_bark(title, body)
        send_telegram(title, body)
        time.sleep(1)  # 避免推送频率过高


# ═══════════════════════════════════════════════════════════
# 静态页面生成
# ═══════════════════════════════════════════════════════════

def generate_html(apps_data: dict, last_updated: str):
    """生成监控状态的 HTML 静态页面"""

    # 构建 App 行
    rows = []
    for app_id, info in apps_data.items():
        name      = info.get("name", app_id)
        price     = info.get("price", "N/A")
        currency  = info.get("currency", "USD")
        icon_url  = info.get("icon_url", "")
        app_url   = info.get("app_url", f"https://apps.apple.com/us/app/id{app_id}")
        iap_list  = info.get("iap", [])
        genres    = ", ".join(info.get("genres", [])[:2])
        fetch_ok  = info.get("fetch_ok", True)

        price_str = "免费" if price == 0.0 else (f"${price:.2f}" if isinstance(price, float) else str(price))
        status_badge = (
            '<span class="badge badge-error">获取失败</span>'
            if not fetch_ok
            else '<span class="badge badge-success">正常</span>'
        )

        iap_html = ""
        if iap_list:
            iap_rows = "".join(
                f'<tr><td>{item["name"]}</td><td>${item["price"]:.2f}</td></tr>'
                for item in iap_list[:8]
            )
            iap_html = f"""
            <details>
              <summary>内购项目（{len(iap_list)}）</summary>
              <table class="iap-table">
                <thead><tr><th>名称</th><th>价格</th></tr></thead>
                <tbody>{iap_rows}</tbody>
              </table>
            </details>"""

        icon_html = (
            f'<img src="{icon_url}" alt="{name}" class="app-icon">'
            if icon_url
            else '<div class="app-icon-placeholder">APP</div>'
        )

        rows.append(f"""
        <tr>
          <td>{icon_html}</td>
          <td><a href="{app_url}" target="_blank" rel="noopener">{name}</a><br>
              <small class="genre">{genres}</small></td>
          <td class="price {'free' if price == 0.0 else ''}">{price_str}</td>
          <td>{status_badge}</td>
          <td>{iap_html if iap_html else '<span class="no-iap">无内购</span>'}</td>
        </tr>""")

    rows_html = "\n".join(rows)
    total = len(apps_data)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>App Store 价格监控</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --text: #e6edf3;
      --muted: #8b949e;
      --accent: #58a6ff;
      --green: #3fb950;
      --red: #f85149;
      --gold: #f0c40a;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg); color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      min-height: 100vh; padding: 24px 16px;
    }}
    header {{
      text-align: center; margin-bottom: 32px;
    }}
    header h1 {{
      font-size: 1.8rem; color: var(--accent);
      display: flex; align-items: center; justify-content: center; gap: 10px;
    }}
    .meta {{ color: var(--muted); font-size: 0.85rem; margin-top: 8px; }}
    .stats {{
      display: flex; justify-content: center; gap: 24px; margin-bottom: 28px;
      flex-wrap: wrap;
    }}
    .stat-card {{
      background: var(--card); border: 1px solid var(--border);
      border-radius: 10px; padding: 14px 28px; text-align: center;
    }}
    .stat-card .num {{ font-size: 2rem; font-weight: 700; color: var(--accent); }}
    .stat-card .label {{ font-size: 0.8rem; color: var(--muted); }}
    .table-wrap {{
      overflow-x: auto;
      background: var(--card); border: 1px solid var(--border);
      border-radius: 12px;
    }}
    table {{
      width: 100%; border-collapse: collapse;
    }}
    thead tr {{ background: #1c2128; }}
    th, td {{
      padding: 12px 16px; text-align: left;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
    }}
    th {{ color: var(--muted); font-size: 0.82rem; text-transform: uppercase; font-weight: 600; }}
    tbody tr:hover {{ background: #1c2128; }}
    tbody tr:last-child td {{ border-bottom: none; }}
    .app-icon {{ width: 52px; height: 52px; border-radius: 12px; object-fit: cover; }}
    .app-icon-placeholder {{
      width: 52px; height: 52px; border-radius: 12px;
      background: var(--border); display: flex; align-items: center;
      justify-content: center; font-size: 0.7rem; color: var(--muted);
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .genre {{ color: var(--muted); font-size: 0.78rem; }}
    .price {{ font-weight: 700; font-size: 1.05rem; }}
    .price.free {{ color: var(--green); }}
    .badge {{
      display: inline-block; padding: 2px 8px; border-radius: 20px;
      font-size: 0.75rem; font-weight: 600;
    }}
    .badge-success {{ background: rgba(63,185,80,.2); color: var(--green); }}
    .badge-error   {{ background: rgba(248,81,73,.2); color: var(--red); }}
    details summary {{
      cursor: pointer; color: var(--accent); font-size: 0.85rem;
      padding: 4px 0; user-select: none;
    }}
    .iap-table {{ width: 100%; margin-top: 8px; font-size: 0.82rem; }}
    .iap-table th, .iap-table td {{
      padding: 4px 8px; border-bottom: 1px solid var(--border);
    }}
    .iap-table th {{ font-size: 0.75rem; }}
    .no-iap {{ color: var(--muted); font-size: 0.82rem; }}
    footer {{ text-align: center; color: var(--muted); font-size: 0.78rem; margin-top: 32px; }}
    @media(max-width: 600px) {{
      th:nth-child(4), td:nth-child(4) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>🍎 App Store 价格监控</h1>
    <p class="meta">美区（US） · 最近更新：{last_updated}</p>
  </header>

  <div class="stats">
    <div class="stat-card">
      <div class="num">{total}</div>
      <div class="label">监控 App 数量</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:var(--green)">
        {sum(1 for v in apps_data.values() if v.get('price', 1) == 0.0)}
      </div>
      <div class="label">当前免费</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:var(--gold)">
        {sum(len(v.get('iap', [])) for v in apps_data.values())}
      </div>
      <div class="label">内购项目总数</div>
    </div>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>图标</th>
          <th>App 名称</th>
          <th>本体价格</th>
          <th>状态</th>
          <th>内购项目</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

  <footer>
    <p>由 GitHub Actions 自动运行 · 数据来源：iTunes API & App Store</p>
    <p style="margin-top:4px">⚠️ 价格仅供参考，请以 App Store 实际页面为准</p>
  </footer>
</body>
</html>
"""
    with open(INDEX_HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"已生成静态页面: {INDEX_HTML_FILE}")


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("=" * 60)
    logger.info("App Store 价格监控 启动")
    logger.info(f"运行时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("=" * 60)

    # 1. 读取 watchlist
    wl_data  = load_json_file(WATCHLIST_FILE)
    apps     = wl_data.get("apps", [])
    settings = wl_data.get("settings", {})
    country  = settings.get("country", "us")

    if not apps:
        logger.error(f"watchlist 为空，请检查 {WATCHLIST_FILE}")
        sys.exit(1)

    logger.info(f"共监控 {len(apps)} 个 App，地区：{country.upper()}")

    # 2. 读取历史价格
    history: dict = load_json_file(HISTORY_FILE)

    # 3. 遍历抓取
    current_data: dict = {}
    all_alerts:   list = []

    for idx, app_entry in enumerate(apps, 1):
        app_id = str(app_entry["id"]) if isinstance(app_entry, dict) else str(app_entry)
        logger.info(f"\n[{idx}/{len(apps)}] 正在处理 App ID: {app_id}")

        try:
            # 3.1 获取本体信息（API）
            info = fetch_app_info_from_api(app_id, country)
            if not info:
                logger.warning(f"  无法获取 App ID={app_id} 的 API 数据，跳过。")
                if app_id in history:
                    current_data[app_id] = {**history[app_id], "fetch_ok": False}
                continue

            logger.info(f"  App: {info['name']}  价格: ${info['price']:.2f}")
            sleep_random()

            # 3.2 获取内购（网页爬取）
            iap = []
            try:
                iap = fetch_iap_from_webpage(app_id, country)
            except Exception as e:
                logger.warning(f"  内购爬取失败，已跳过: {e}")

            info["iap"]      = iap
            info["fetch_ok"] = True
            info["last_checked"] = datetime.now(timezone.utc).isoformat()

            current_data[app_id] = info

            # 3.3 比对
            if app_id in history:
                alerts = compare_prices(app_id, info, history[app_id])
                all_alerts.extend(alerts)
            else:
                logger.info(f"  首次记录 App ID={app_id}，写入基线。")

        except Exception as e:
            logger.error(f"  处理 App ID={app_id} 时发生未知错误: {e}")
            logger.debug(traceback.format_exc())
            # 出错则保留历史数据，标记 fetch_ok=False
            if app_id in history:
                current_data[app_id] = {**history[app_id], "fetch_ok": False}

        sleep_random()

    # 4. 发送通知
    if all_alerts:
        logger.info(f"\n检测到 {len(all_alerts)} 条降价信息，准备推送…")
        send_notifications(all_alerts)
    else:
        logger.info("\n未检测到降价，无需推送。")

    # 5. 合并 & 保存历史
    merged = {**history, **current_data}
    save_json_file(HISTORY_FILE, merged)

    # 6. 生成静态 HTML
    last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    generate_html(merged, last_updated)

    logger.info("\n" + "=" * 60)
    logger.info(f"监控完成！处理 {len(current_data)} 个 App，触发 {len(all_alerts)} 条通知。")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
