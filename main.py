#!/usr/bin/env python3
"""
App Store 价格监控系统 v2.0
- 本体价格：通过 iTunes Lookup API 获取
- 内购价格：通过 App Store 网页（Chrome UA + allow_redirects）解析 Svelte 渲染的内购列表
- 推送：Bark（iOS）/ Telegram Bot
- 输出：history_prices.json + index.html（GitHub Pages）
"""

import json
import logging
import os
import random
import re
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────
WATCHLIST_FILE    = "watchlist.json"
HISTORY_FILE      = "history_prices.json"
PROGRESS_FILE     = "monitor_progress.json"   # 记录分批进度
HTML_OUTPUT_FILE  = "index.html"
LOG_FILE          = "monitor.log"

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
APP_PAGE_URL      = "https://apps.apple.com/{country}/app/id{app_id}"

# 重试 & 速率控制
MAX_RETRIES       = 3
RETRY_DELAY       = 5
REQUEST_DELAY     = (1.5, 3.5)   # 每次请求之间的随机延迟（秒）

# 分批运行配置
# MONITOR_FULL_SCAN=1 时跳过分批，一次扫完所有 App
# 否则每次处理 BATCH_SIZE 个 App，通过 progress 文件记录进度
BATCH_SIZE        = int(os.environ.get("MONITOR_BATCH_SIZE", "500"))
FULL_SCAN         = os.environ.get("MONITOR_FULL_SCAN", "").strip().lower() in ("1", "true", "yes")

# 推送渠道（从 GitHub Secrets / 环境变量读取）
BARK_KEY          = os.environ.get("BARK_KEY", "")
TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID  = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────
# 日志
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# HTTP 工具
# ─────────────────────────────────────────────
DESKTOP_UAS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

def make_browser_headers():
    """生成模拟桌面浏览器的请求头（必须用这个才能绕过 App Store 的重定向检测）"""
    return {
        "User-Agent": random.choice(DESKTOP_UAS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Cache-Control": "max-age=0",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
    }

def make_api_headers():
    """iTunes API 请求头"""
    return {
        "User-Agent": "iTunes/12.13.0 (Macintosh; OS X 14.5)",
        "Accept": "application/json",
    }

def request_with_retry(url, params=None, headers=None, allow_redirects=True, timeout=15):
    """带重试机制的 HTTP GET"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=headers or make_api_headers(),
                timeout=timeout,
                allow_redirects=allow_redirects,
            )
            if resp.status_code == 200:
                return resp
            elif resp.status_code in (301, 302) and not allow_redirects:
                return resp
            elif resp.status_code == 404:
                logger.debug(f"404 Not Found: {url}")
                return None
            else:
                logger.warning(f"  HTTP {resp.status_code} on attempt {attempt}: {url[:80]}")
        except requests.RequestException as e:
            logger.warning(f"  Request error attempt {attempt}: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)
    return None


# ─────────────────────────────────────────────
# 数据获取
# ─────────────────────────────────────────────

def fetch_app_info(app_id: str, country: str = "us") -> dict | None:
    """通过 iTunes Lookup API 获取 App 本体信息（名称、价格、图标等）"""
    resp = request_with_retry(
        ITUNES_LOOKUP_URL,
        params={"id": app_id, "country": country, "lang": "en-us"},
    )
    if not resp:
        return None
    try:
        results = resp.json().get("results", [])
        if not results:
            return None
        r = results[0]
        return {
            "app_id":       app_id,
            "name":         r.get("trackName", "Unknown"),
            "price":        float(r.get("price", 0.0)),
            "currency":     r.get("currency", "USD"),
            "formatted_price": r.get("formattedPrice", "Free"),
            "icon_url":     r.get("artworkUrl100", ""),
            "developer":    r.get("artistName", ""),
            "bundle_id":    r.get("bundleId", ""),
            "store_url":    r.get("trackViewUrl", f"https://apps.apple.com/us/app/id{app_id}"),
            "category":     r.get("primaryGenreName", ""),
            "rating":       round(float(r.get("averageUserRating", 0)), 1),
        }
    except Exception as e:
        logger.warning(f"  解析 App 信息失败 [{app_id}]: {e}")
        return None


def fetch_iap_from_webpage(app_id: str, country: str = "us") -> list[dict]:
    """
    通过 App Store 网页获取内购列表。
    
    关键技术：
    - 必须使用桌面端 Chrome UA（iPhone UA 会被 301→itms-appss:// 拒绝）
    - allow_redirects=True 跟随 301 到带 slug 的 URL
    - App Store 使用 Svelte 渲染，内购在 <details class="svelte-*"> 的 <li> 里
    """
    url = APP_PAGE_URL.format(country=country, app_id=app_id)
    resp = request_with_retry(url, headers=make_browser_headers(), allow_redirects=True)
    if not resp:
        return []

    # 检查是否被重定向到 App Store 客户端协议
    if "itms-appss://" in resp.url or "itms-apps://" in resp.url:
        logger.debug(f"  内购页面被重定向到App客户端，跳过")
        return []

    try:
        html = resp.content.decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "lxml")
        iap_list = []

        # ── 方式1：找包含 "In-App Purchases" 的 dt，然后找相邻 details 里的 li ──
        for dt in soup.find_all("dt"):
            if "purchase" in dt.text.lower():
                parent = dt.parent
                details = parent.find("details") if parent else None
                if details:
                    for li in details.find_all("li"):
                        text = li.get_text(" ", strip=True)
                        # 跳过 "Learn More" 等非价格项
                        if not re.search(r'\$\d', text):
                            continue
                        price_m = re.search(r'\$([\d]+\.?\d*)', text)
                        if price_m:
                            price = float(price_m.group(1))
                            name = re.sub(r'\s*\$[\d.]+.*$', '', text).strip()
                            if name and price > 0:
                                iap_list.append({"name": name, "price": price})
                if iap_list:
                    logger.info(f"  [网页] 找到 {len(iap_list)} 个内购项目")
                    return iap_list
                break

        # ── 方式2：JSON-LD 兜底（部分App可能用此格式）──
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                obj = json.loads(script.string or "")
                offers = obj.get("offers", [])
                if isinstance(offers, list):
                    for offer in offers:
                        name  = offer.get("name", "")
                        price_str = str(offer.get("price", ""))
                        if name and price_str:
                            try:
                                price = float(price_str)
                                if price > 0:
                                    iap_list.append({"name": name, "price": price})
                            except ValueError:
                                pass
                if iap_list:
                    logger.info(f"  [JSON-LD] 找到 {len(iap_list)} 个内购项目")
                    return iap_list
            except Exception:
                pass

        return []

    except Exception as e:
        logger.warning(f"  解析内购页面失败 [{app_id}]: {e}")
        return []


# ─────────────────────────────────────────────
# 价格比对
# ─────────────────────────────────────────────

def merge_iap_with_history(current_iap: list[dict], prev_iap: list[dict]) -> list[dict]:
    """
    将当前内购列表与历史记录合并，保留每个项目的历史最高价（original_price）。
    original_price = 历史上见过的最高价，用于展示折扣力度。
    """
    # 构建历史记录映射：name -> {price, original_price}
    prev_map = {item["name"]: item for item in prev_iap}

    merged = []
    for item in current_iap:
        name  = item["name"]
        price = item["price"]
        prev  = prev_map.get(name, {})

        # original_price = max(历史original_price, 历史price, 当前price)
        prev_original = prev.get("original_price", prev.get("price", price))
        original_price = max(prev_original, price)

        merged.append({
            "name":           name,
            "price":          price,
            "original_price": round(original_price, 2),
        })

    return merged


def compare_prices(current: dict, previous: dict) -> list[dict]:
    """
    比对当前和历史价格，返回降价列表。
    每个降价项格式：
    {
        "type": "app" | "iap",
        "name": str,
        "old_price": float,
        "new_price": float,
        "drop": float,
    }
    """
    drops = []

    # 本体价格
    old_price = previous.get("price", None)
    new_price = current.get("price", None)
    if old_price is not None and new_price is not None:
        if new_price < old_price and old_price > 0:
            drops.append({
                "type":      "app",
                "name":      current.get("name", "Unknown"),
                "old_price": old_price,
                "new_price": new_price,
                "drop":      round(old_price - new_price, 2),
            })

    # 内购价格：与历史 original_price 比对，才能反映真实折扣
    prev_iap_map = {item["name"]: item for item in previous.get("iap", [])}
    for item in current.get("iap", []):
        iap_name  = item["name"]
        iap_price = item["price"]
        prev_item = prev_iap_map.get(iap_name, {})
        # 用 original_price 作为参考原价（如无则用历史 price）
        ref_price = prev_item.get("original_price", prev_item.get("price", None))
        if ref_price is not None and iap_price < ref_price and ref_price > 0:
            drops.append({
                "type":      "iap",
                "name":      iap_name,
                "old_price": ref_price,
                "new_price": iap_price,
                "drop":      round(ref_price - iap_price, 2),
            })

    return drops


# ─────────────────────────────────────────────
# 推送通知
# ─────────────────────────────────────────────

def push_bark(title: str, body: str, url: str = ""):
    """通过 Bark 推送到 iPhone"""
    if not BARK_KEY:
        return
    try:
        api = f"https://api.day.app/{BARK_KEY}"
        payload = {"title": title, "body": body}
        if url:
            payload["url"] = url
        requests.post(api, json=payload, timeout=10)
        logger.info(f"  [Bark] 推送成功: {title}")
    except Exception as e:
        logger.warning(f"  [Bark] 推送失败: {e}")


def push_telegram(title: str, body: str):
    """通过 Telegram Bot 推送"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        text = f"*{title}*\n{body}"
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        logger.info(f"  [Telegram] 推送成功: {title}")
    except Exception as e:
        logger.warning(f"  [Telegram] 推送失败: {e}")


def send_notification(app_name: str, drops: list[dict], store_url: str):
    """为一个 App 的所有降价项发送通知"""
    if not drops:
        return

    lines = [f"🎉 {app_name} 降价了！"]
    for d in drops:
        if d["type"] == "app":
            lines.append(f"📦 本体: ${d['old_price']:.2f} → ${d['new_price']:.2f} (省 ${d['drop']:.2f})")
        else:
            lines.append(f"🎁 内购「{d['name']}」: ${d['old_price']:.2f} → ${d['new_price']:.2f}")

    title = f"💰 {app_name} 降价提醒"
    body  = "\n".join(lines[1:])

    push_bark(title, body, store_url)
    push_telegram(title, "\n".join(lines))


# ─────────────────────────────────────────────
# HTML 生成
# ─────────────────────────────────────────────

def generate_html(all_data: dict):
    """生成美观的 index.html 展示所有监控 App 的价格"""

    # 对 App 排序：有内购的排前面，然后按价格降序
    apps = list(all_data.values())
    apps.sort(key=lambda x: (-len(x.get("iap", [])), -x.get("price", 0)))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(apps)
    paid_count = sum(1 for a in apps if a.get("price", 0) > 0)
    iap_count  = sum(1 for a in apps if a.get("iap"))

    cards_html = ""
    for app in apps:
        app_id    = app.get("app_id", "")
        name      = app.get("name", "Unknown")
        price     = app.get("price", 0)
        fmt_price = app.get("formatted_price", "Free")
        icon      = app.get("icon_url", "")
        dev       = app.get("developer", "")
        cat       = app.get("category", "")
        rating    = app.get("rating", 0)
        url       = app.get("store_url", f"https://apps.apple.com/us/app/id{app_id}")
        iap_list  = app.get("iap", [])

        price_color = "#30d158" if price == 0 else "#ff9f0a" if price < 5 else "#ff6b6b"
        price_badge = f'<span class="price-badge" style="background:{price_color}">{fmt_price}</span>'

        stars = "★" * int(rating) + "☆" * (5 - int(rating)) if rating else ""
        rating_html = f'<span class="rating" title="{rating}">{stars}</span>' if stars else ""

        iap_html = ""
        if iap_list:
            iap_items = ""
            has_discount = False
            for item in iap_list[:10]:
                cur_price  = item["price"]
                orig_price = item.get("original_price", cur_price)
                disc_pct   = 0
                if orig_price > cur_price and orig_price > 0:
                    disc_pct = round((orig_price - cur_price) / orig_price * 100)
                    has_discount = True

                if disc_pct > 0:
                    iap_items += (
                        f'<li>'
                        f'<span class="iap-name">{item["name"]}</span>'
                        f'<span class="iap-prices">'
                        f'<span class="iap-orig">${orig_price:.2f}</span>'
                        f'<span class="iap-price disc">${cur_price:.2f}</span>'
                        f'<span class="disc-badge">-{disc_pct}%</span>'
                        f'</span>'
                        f'</li>'
                    )
                else:
                    iap_items += (
                        f'<li>'
                        f'<span class="iap-name">{item["name"]}</span>'
                        f'<span class="iap-prices">'
                        f'<span class="iap-price">${cur_price:.2f}</span>'
                        f'</span>'
                        f'</li>'
                    )

            disc_label = ' 🔥 有折扣' if has_discount else ''
            iap_html = f'''
            <div class="iap-section">
                <div class="iap-header">🎁 内购 {len(iap_list)} 项{disc_label}</div>
                <ul class="iap-list">{iap_items}</ul>
            </div>'''

        has_iap_discount = any(
            item.get("original_price", item["price"]) > item["price"]
            for item in iap_list
        ) if iap_list else False

        icon_html = f'<img src="{icon}" alt="{name}" class="app-icon" loading="lazy">' if icon else '<div class="app-icon-placeholder">📱</div>'

        cards_html += f'''
        <div class="app-card" data-price="{price}" data-name="{name.lower()}" data-hasiap="{"1" if iap_list else "0"}" data-discount="{"1" if has_iap_discount else "0"}">
            <a href="{url}" target="_blank" class="card-link">
                <div class="card-header">
                    {icon_html}
                    <div class="card-info">
                        <h3 class="app-name">{name}</h3>
                        <p class="app-dev">{dev}</p>
                        <p class="app-cat">{cat} {rating_html}</p>
                    </div>
                    {price_badge}
                </div>
            </a>
            {iap_html}
        </div>'''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>🎯 App Store 价格监控</title>
    <style>
        :root {{
            --bg: #0a0a0f;
            --surface: #14141e;
            --surface2: #1e1e2e;
            --border: #2a2a3d;
            --text: #e2e2ee;
            --muted: #7f7f99;
            --accent: #5c6bc0;
            --green: #30d158;
            --orange: #ff9f0a;
            --red: #ff453a;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
            min-height: 100vh;
        }}
        header {{
            background: linear-gradient(135deg, var(--surface) 0%, #1a1a2e 100%);
            border-bottom: 1px solid var(--border);
            padding: 24px 32px;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(12px);
        }}
        .header-top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
        }}
        h1 {{ font-size: 1.5rem; font-weight: 700; letter-spacing: -0.5px; }}
        h1 span {{ color: var(--accent); }}
        .stats {{
            display: flex;
            gap: 16px;
            font-size: 0.85rem;
            color: var(--muted);
        }}
        .stats b {{ color: var(--text); }}
        .search-bar {{
            margin-top: 16px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .search-bar input {{
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            font-size: 0.9rem;
            padding: 8px 16px;
            outline: none;
            width: 240px;
        }}
        .search-bar input:focus {{ border-color: var(--accent); }}
        .filter-btn {{
            background: var(--surface2);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
            cursor: pointer;
            font-size: 0.85rem;
            padding: 8px 14px;
            transition: all 0.2s;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: var(--accent);
            border-color: var(--accent);
        }}
        main {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 16px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 16px;
        }}
        .app-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .app-card:hover {{
            transform: translateY(-2px);
            border-color: var(--accent);
        }}
        .card-link {{
            display: block;
            text-decoration: none;
            color: inherit;
            padding: 16px;
        }}
        .card-header {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        .app-icon {{
            width: 60px;
            height: 60px;
            border-radius: 14px;
            flex-shrink: 0;
            object-fit: cover;
        }}
        .app-icon-placeholder {{
            width: 60px;
            height: 60px;
            border-radius: 14px;
            background: var(--surface2);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            flex-shrink: 0;
        }}
        .card-info {{ flex: 1; min-width: 0; }}
        .app-name {{
            font-size: 0.95rem;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .app-dev, .app-cat {{
            font-size: 0.78rem;
            color: var(--muted);
            margin-top: 2px;
        }}
        .rating {{ color: var(--orange); letter-spacing: -1px; }}
        .price-badge {{
            font-size: 0.85rem;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 20px;
            white-space: nowrap;
            color: #000;
            flex-shrink: 0;
        }}
        .iap-section {{
            border-top: 1px solid var(--border);
            padding: 10px 16px 12px;
        }}
        .iap-header {{
            font-size: 0.82rem;
            color: var(--muted);
            margin-bottom: 8px;
            font-weight: 600;
        }}
        .iap-list {{
            list-style: none;
        }}
        .iap-list li {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 0;
            font-size: 0.82rem;
            border-bottom: 1px solid var(--border);
        }}
        .iap-list li:last-child {{ border-bottom: none; }}
        .iap-name {{
            color: var(--text);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 170px;
            flex: 1;
        }}
        .iap-prices {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-shrink: 0;
            margin-left: 8px;
        }}
        .iap-price {{
            color: var(--green);
            font-weight: 600;
        }}
        .iap-price.disc {{
            color: #ff453a;
        }}
        .iap-orig {{
            color: var(--muted);
            text-decoration: line-through;
            font-size: 0.76rem;
        }}
        .disc-badge {{
            background: #ff453a;
            color: #fff;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 1px 5px;
            border-radius: 6px;
            white-space: nowrap;
        }}
        footer {{
            text-align: center;
            padding: 24px;
            color: var(--muted);
            font-size: 0.8rem;
            border-top: 1px solid var(--border);
            margin-top: 32px;
        }}
        .hidden {{ display: none !important; }}
    </style>
</head>
<body>
    <header>
        <div class="header-top">
            <h1>🎯 App Store <span>价格监控</span></h1>
            <div class="stats">
                <span>共监控 <b>{total}</b> 个 App</span>
                <span>付费 <b>{paid_count}</b> 个</span>
                <span>含内购 <b>{iap_count}</b> 个</span>
                <span>更新于 {now}</span>
            </div>
        </div>
        <div class="search-bar">
            <input type="text" id="search" placeholder="🔍 搜索 App 名称..." oninput="filterApps()" />
            <button class="filter-btn active" onclick="setFilter('all', this)">全部</button>
            <button class="filter-btn" onclick="setFilter('paid', this)">付费</button>
            <button class="filter-btn" onclick="setFilter('iap', this)">含内购</button>
            <button class="filter-btn" onclick="setFilter('discount', this)">🔥 内购折扣</button>
            <button class="filter-btn" onclick="setFilter('free', this)">免费</button>
        </div>
    </header>
    <main>
        <div class="grid" id="app-grid">
{cards_html}
        </div>
    </main>
    <footer>
        <p>由 GitHub Actions 自动更新 · 数据来源：Apple iTunes API + App Store 网页</p>
        <p style="margin-top:4px">⚠️ 价格仅供参考，以 App Store 实际显示为准</p>
    </footer>
    <script>
        let currentFilter = 'all';

        function filterApps() {{
            const q = document.getElementById('search').value.toLowerCase();
            const cards = document.querySelectorAll('.app-card');
            cards.forEach(card => {{
                const name     = card.dataset.name     || '';
                const price    = parseFloat(card.dataset.price    || '0');
                const hasIap   = card.dataset.hasiap   === '1';
                const hasDisc  = card.dataset.discount === '1';
                let show = name.includes(q);
                if (show && currentFilter === 'paid')     show = price > 0;
                if (show && currentFilter === 'free')     show = price === 0;
                if (show && currentFilter === 'iap')      show = hasIap;
                if (show && currentFilter === 'discount') show = hasDisc;
                card.classList.toggle('hidden', !show);
            }});
        }}

        function setFilter(type, btn) {{
            currentFilter = type;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterApps();
        }}
    </script>
</body>
</html>"""

    Path(HTML_OUTPUT_FILE).write_text(html, encoding="utf-8")
    logger.info(f"HTML 已生成: {HTML_OUTPUT_FILE} ({len(apps)} 个 App)")


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info(f"App Store 价格监控 启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 1. 读取 watchlist
    watchlist_path = Path(WATCHLIST_FILE)
    if not watchlist_path.exists():
        logger.error(f"找不到 {WATCHLIST_FILE}，请先创建该文件。")
        return
    with watchlist_path.open(encoding="utf-8") as f:
        watchlist = json.load(f)
    apps_to_watch = watchlist.get("apps", [])
    settings      = watchlist.get("settings", {})
    country       = settings.get("country", "us")
    fetch_iap     = settings.get("fetch_iap", True)

    # 过滤掉 skip=true 的条目
    apps_to_watch = [a for a in apps_to_watch if not a.get("skip", False)]
    total_apps = len(apps_to_watch)

    # ── 分批处理逻辑 ──
    # FULL_SCAN 模式：一次扫完所有 App
    # 分批模式：每次处理 BATCH_SIZE 个 App，通过 progress 文件记录进度
    progress_path = Path(PROGRESS_FILE)
    batch_offset = 0

    if FULL_SCAN:
        logger.info("🔄 全量扫描模式：一次处理所有 App")
        batch_end = total_apps
        current_batch = apps_to_watch
        next_offset = 0
    else:
        if progress_path.exists():
            try:
                batch_offset = json.loads(progress_path.read_text())
                batch_offset = int(batch_offset)
            except Exception:
                batch_offset = 0

        # 如果 offset >= total_apps，说明上一轮全量扫描已完成，从头开始
        if batch_offset >= total_apps:
            batch_offset = 0
            logger.info("✅ 上一轮已完成，从头开始新一轮")

        batch_end    = min(batch_offset + BATCH_SIZE, total_apps)
        current_batch = apps_to_watch[batch_offset:batch_end]
        next_offset  = batch_end if batch_end < total_apps else 0

    logger.info(f"监控列表: 共 {total_apps} 个 App，本次处理 [{batch_offset+1}~{batch_end}]，批大小: {BATCH_SIZE if not FULL_SCAN else '全量'}")
    logger.info(f"国家: {country}，内购抓取: {fetch_iap}")

    # 2. 读取历史价格
    history_path = Path(HISTORY_FILE)
    history: dict = {}
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"读取历史价格文件失败: {e}，将从头开始记录")

    # 用于中断时保存进度的全局变量
    _last_processed_index = [batch_offset]

    def save_progress_on_exit(signum, frame):
        """收到中断信号时保存当前进度"""
        idx = _last_processed_index[0]
        logger.warning(f"⚠ 收到中断信号，保存进度: {idx}")
        progress_path.write_text(json.dumps(idx), encoding="utf-8")
        # 也保存当前已扫描的数据
        timestamp = datetime.now(timezone.utc).isoformat()
        for app_id, data in current_data.items():
            data["last_updated"] = timestamp
        merged = dict(history)
        merged.update(current_data)
        history_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        generate_html(merged)
        logger.info("已保存进度和数据，安全退出")
        raise SystemExit(0)

    # 注册信号处理（Ctrl+C 和 SIGTERM）
    signal.signal(signal.SIGINT, save_progress_on_exit)
    signal.signal(signal.SIGTERM, save_progress_on_exit)

    # 3. 遍历本批次监控列表
    all_drops: list[dict] = []
    current_data: dict    = {}
    success_count = 0
    fail_count    = 0

    for i, app_entry in enumerate(current_batch, batch_offset + 1):
        app_id = str(app_entry.get("id", "")).strip()
        hint   = app_entry.get("name", app_id)

        # 去重（watchlist 里可能有重复 ID）
        if app_id in current_data:
            continue

        logger.info(f"[{i:>4}/{total_apps}] 处理: {hint} (id={app_id})")

        try:
            # 3.1 获取本体信息
            info = fetch_app_info(app_id, country)
            if not info:
                logger.warning(f"  ⚠ 获取失败，跳过")
                fail_count += 1
                time.sleep(random.uniform(*REQUEST_DELAY))
                continue

            logger.info(f"  ✓ {info['name']} | 价格: {info['formatted_price']} | 类别: {info['category']}")

            # 3.2 获取内购（仅付费 App 或免费但有内购的 App）
            iap = []
            if fetch_iap:
                prev_iap = history.get(app_id, {}).get("iap", [])
                # 付费 App 一定爬，免费 App 如果历史上有内购记录也爬
                should_fetch = info["price"] > 0 or len(prev_iap) > 0
                if should_fetch:
                    time.sleep(random.uniform(*REQUEST_DELAY))
                    iap_raw = fetch_iap_from_webpage(app_id, country)
                    if iap_raw:
                        # 合并历史，保留 original_price（历史最高价）
                        iap = merge_iap_with_history(iap_raw, prev_iap)
                        logger.info(f"  ✓ 内购: {len(iap)} 项")
                    else:
                        # 保留上次的内购数据（防止暂时爬不到就清空）
                        iap = prev_iap
                        if prev_iap:
                            logger.info(f"  ⟳ 内购暂时获取失败，保留上次数据 ({len(prev_iap)} 项)")
                else:
                    iap = prev_iap

            info["iap"] = iap

            # 3.3 比对价格
            prev = history.get(app_id, {})
            if prev:
                drops = compare_prices(info, prev)
                if drops:
                    for d in drops:
                        d["app_id"]   = app_id
                        d["app_name"] = info["name"]
                        d["store_url"] = info["store_url"]
                    all_drops.extend(drops)
                    logger.info(f"  🔥 降价！共 {len(drops)} 项变动")
                    for d in drops:
                        logger.info(f"     [{d['type']}] {d['name']}: ${d['old_price']} → ${d['new_price']}")
                    # 发送通知
                    send_notification(info["name"], drops, info["store_url"])
            else:
                logger.info(f"  ℹ 首次记录，无历史价格可比对")

            current_data[app_id] = info
            success_count += 1

        except Exception as e:
            logger.error(f"  ✗ 处理 App {app_id} 时发生意外错误: {e}")
            fail_count += 1
            # 保留历史数据
            if app_id in history:
                current_data[app_id] = history[app_id]

        time.sleep(random.uniform(*REQUEST_DELAY))

        # 定期保存进度（每 100 个 App 保存一次，防止中断丢失太多）
        if (i - batch_offset) % 100 == 0 and FULL_SCAN:
            _last_processed_index[0] = i
            progress_path.write_text(json.dumps(i), encoding="utf-8")

    # 4. 保存历史价格和进度
    # 更新当前数据中的时间戳
    timestamp = datetime.now(timezone.utc).isoformat()
    for app_id, data in current_data.items():
        data["last_updated"] = timestamp

    # 合并：保留 watchlist 中已有但本次未成功获取的 App 的历史数据
    merged = dict(history)
    merged.update(current_data)

    history_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"历史价格已保存: {len(merged)} 条记录（本次新增/更新: {len(current_data)}）")

    # 保存分批进度
    # 全量模式：完成后保存 total_apps 表示一轮已完成，中途中断保存当前进度
    if FULL_SCAN:
        progress_path.write_text(json.dumps(total_apps), encoding="utf-8")
        logger.info(f"✅ 全量扫描完成，进度标记为 {total_apps}（表示已完成一轮）")
    else:
        progress_path.write_text(json.dumps(next_offset), encoding="utf-8")
        if next_offset == 0:
            logger.info("✅ 完成一轮完整扫描，下次从头开始")
        else:
            logger.info(f"📌 进度已保存：下次从第 {next_offset + 1} 个 App 开始（共 {total_apps} 个）")

    # 5. 生成 HTML
    generate_html(merged)

    # 6. 汇总日志
    logger.info("=" * 60)
    logger.info(f"运行完成 | 成功: {success_count} | 失败: {fail_count} | 降价: {len(all_drops)} 项")
    if all_drops:
        logger.info("本次降价汇总:")
        for d in all_drops:
            logger.info(f"  [{d['type']}] {d.get('app_name', '')} - {d['name']}: ${d['old_price']} → ${d['new_price']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
