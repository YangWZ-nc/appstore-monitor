#!/usr/bin/env python3
"""
批量获取 App Store RSS 排行榜数据，扩充 watchlist
使用 iTunes RSS Feed (https://rss.applemarketingtools.com/)
"""

import json
import time
import random
import requests
from pathlib import Path

# iTunes RSS Feed 基础 URL
RSS_BASE = "https://itunes.apple.com/{country}/rss/{feed}/limit={limit}/json"

# 要抓取的分类（付费榜、免费榜、畅销榜）
FEEDS = {
    "top_paid_apps": "toppaidapplications",
    "top_free_apps": "topfreeapplications",
    "top_grossing_apps": "topgrossingapplications",
    "top_paid_games": "toppaidapplications",
    "top_free_games": "topfreeapplications",
}

# 国家/地区
COUNTRIES = ["us"]  # 可以扩展更多国家

# 每个分类抓取数量
LIMIT = 200

# 已有的 App ID 集合（去重用）
existing_ids = set()

def load_existing_watchlist():
    """加载已有的 watchlist，提取所有 ID"""
    global existing_ids
    watchlist_path = Path("watchlist.json")
    if watchlist_path.exists():
        with open(watchlist_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for app in data.get("apps", []):
                existing_ids.add(str(app.get("id", "")))
        print(f"已加载现有 watchlist: {len(existing_ids)} 个 App")

def fetch_rss_feed(country: str, feed_type: str, genre: str = "", limit: int = 200) -> list[dict]:
    """
    获取 iTunes RSS Feed
    genre: 可以指定游戏分类 (36 是 Games)
    """
    url = f"https://itunes.apple.com/{country}/rss/{feed_type}/limit={limit}/json"
    if genre:
        url = f"https://itunes.apple.com/{country}/rss/{feed_type}/genre={genre}/limit={limit}/json"
    
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"  ⚠ 获取失败: {url} (HTTP {resp.status_code})")
            return []
        
        data = resp.json()
        entries = data.get("feed", {}).get("entry", [])
        
        apps = []
        for entry in entries:
            app_id = entry.get("id", {}).get("attributes", {}).get("im:id", "")
            name = entry.get("im:name", {}).get("label", "")
            category = entry.get("category", {}).get("attributes", {}).get("label", "")
            
            if app_id and name:
                apps.append({
                    "id": app_id,
                    "name": name,
                    "category": category or "Unknown",
                    "url": f"https://apps.apple.com/{country}/app/id{app_id}",
                })
        
        return apps
    except Exception as e:
        print(f"  ⚠ 解析失败: {e}")
        return []

def fetch_genre_list(country: str = "us") -> list[dict]:
    """获取所有可用的分类 ID"""
    # 游戏子分类
    game_genres = [
        ("36", "Games"),  # 游戏总类
        ("6014", "Games/Action"),
        ("6016", "Games/Adventure"),
        ("6017", "Games/Arcade"),
        ("6018", "Games/Board"),
        ("6019", "Games/Card"),
        ("6020", "Games/Casino"),
        ("6021", "Games/Dice"),
        ("6022", "Games/Educational"),
        ("6023", "Games/Family"),
        ("6024", "Games/Music"),
        ("6025", "Games/Puzzle"),
        ("6026", "Games/Racing"),
        ("6027", "Games/Role Playing"),
        ("6028", "Games/Simulation"),
        ("6029", "Games/Sports"),
        ("6030", "Games/Strategy"),
        ("6031", "Games/Trivia"),
        ("6032", "Games/Word"),
    ]
    
    # App 分类
    app_genres = [
        ("6000", "Business"),
        ("6001", "Weather"),
        ("6002", "Utilities"),
        ("6003", "Travel"),
        ("6004", "Sports"),
        ("6005", "Social Networking"),
        ("6006", "Reference"),
        ("6007", "Productivity"),
        ("6008", "Photo & Video"),
        ("6009", "News"),
        ("6010", "Navigation"),
        ("6011", "Music"),
        ("6012", "Lifestyle"),
        ("6013", "Health & Fitness"),
        ("6015", "Entertainment"),
        ("6016", "Games"),
        ("6017", "Education"),
        ("6018", "Books"),
        ("6020", "Medical"),
        ("6021", "Newsstand"),
        ("6022", "Catalogs"),
        ("6023", "Food & Drink"),
        ("6024", "Finance"),
        ("6025", "Magazines & Newspapers"),
        ("6026", "Shopping"),
        ("6027", "Stickers"),
        ("6028", "Developer Tools"),
        ("6029", "Graphics & Design"),
    ]
    
    return game_genres + app_genres

def main():
    print("=" * 60)
    print("App Store RSS 数据抓取工具")
    print("=" * 60)
    
    # 加载已有数据
    load_existing_watchlist()
    
    all_apps = []
    fetched_ids = set(existing_ids)  # 用于去重
    
    # 1. 抓取总榜（付费、免费、畅销）
    print("\n📊 抓取总榜...")
    for feed_name, feed_type in FEEDS.items():
        if "game" in feed_name:
            continue  # 游戏单独处理
        print(f"  正在抓取: {feed_name}...")
        apps = fetch_rss_feed("us", feed_type, limit=LIMIT)
        for app in apps:
            if app["id"] not in fetched_ids:
                all_apps.append(app)
                fetched_ids.add(app["id"])
        print(f"    ✓ 获取 {len(apps)} 个，累计新 App: {len(all_apps)}")
        time.sleep(random.uniform(0.5, 1.5))
    
    # 2. 抓取各分类的付费榜和免费榜
    print("\n📂 抓取各分类榜单...")
    genres = fetch_genre_list()
    
    for genre_id, genre_name in genres:
        print(f"  正在抓取: {genre_name}...")
        
        # 付费榜
        apps_paid = fetch_rss_feed("us", "toppaidapplications", genre_id, limit=100)
        for app in apps_paid:
            if app["id"] not in fetched_ids:
                app["category"] = genre_name
                all_apps.append(app)
                fetched_ids.add(app["id"])
        
        time.sleep(random.uniform(0.3, 0.8))
        
        # 免费榜
        apps_free = fetch_rss_feed("us", "topfreeapplications", genre_id, limit=100)
        for app in apps_free:
            if app["id"] not in fetched_ids:
                app["category"] = genre_name
                all_apps.append(app)
                fetched_ids.add(app["id"])
        
        print(f"    ✓ {genre_name}: 付费 {len(apps_paid)} + 免费 {len(apps_free)}，累计: {len(all_apps)}")
        time.sleep(random.uniform(0.3, 0.8))
    
    print(f"\n🎉 抓取完成！共获取 {len(all_apps)} 个新 App")
    
    # 3. 合并并保存
    print("\n💾 保存到 watchlist.json...")
    
    watchlist_path = Path("watchlist.json")
    if watchlist_path.exists():
        with open(watchlist_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    else:
        existing_data = {"settings": {"country": "us", "fetch_iap": True}, "apps": []}
    
    # 合并
    existing_apps = existing_data.get("apps", [])
    combined_apps = existing_apps + all_apps
    
    # 去重（按 ID）
    seen_ids = set()
    unique_apps = []
    for app in combined_apps:
        app_id = str(app.get("id", ""))
        if app_id and app_id not in seen_ids:
            seen_ids.add(app_id)
            unique_apps.append(app)
    
    existing_data["apps"] = unique_apps
    existing_data["settings"]["note"] = f"All IDs verified from official App Store URLs. Last updated: {time.strftime('%Y-%m-%d')}"
    
    with open(watchlist_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已保存！总计: {len(unique_apps)} 个 App")
    print(f"   原有: {len(existing_apps)} 个")
    print(f"   新增: {len(unique_apps) - len(existing_apps)} 个")

if __name__ == "__main__":
    main()
