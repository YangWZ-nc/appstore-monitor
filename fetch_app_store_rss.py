#!/usr/bin/env python3
"""
批量获取 App Store RSS 排行榜数据 — 美区专版 v2
策略：
1. RSS 抓取：三榜（付费/免费/畅销）× 所有分类 × 美区
2. 补充列表：用 iTunes Search API 搜索知名游戏/App 的正确 ID
"""

import json
import time
import random
import requests
from pathlib import Path

APP_GENRES = [
    ("6000", "Business"), ("6001", "Weather"), ("6002", "Utilities"),
    ("6003", "Travel"), ("6004", "Sports"), ("6005", "Social Networking"),
    ("6006", "Reference"), ("6007", "Productivity"), ("6008", "Photo & Video"),
    ("6009", "News"), ("6010", "Navigation"), ("6011", "Music"),
    ("6012", "Lifestyle"), ("6013", "Health & Fitness"), ("6015", "Entertainment"),
    ("6017", "Education"), ("6018", "Books"), ("6020", "Medical"),
    ("6023", "Food & Drink"), ("6024", "Finance"), ("6026", "Shopping"),
    ("6029", "Graphics & Design"),
]

GAME_GENRES = [
    ("36", "Games"), ("7001", "Games/Action"), ("7002", "Games/Adventure"),
    ("7003", "Games/Arcade"), ("7004", "Games/Board"), ("7005", "Games/Card"),
    ("7006", "Games/Casino"), ("7009", "Games/Family"), ("7011", "Games/Music"),
    ("7012", "Games/Puzzle"), ("7013", "Games/Racing"), ("7014", "Games/Role Playing"),
    ("7015", "Games/Simulation"), ("7016", "Games/Sports"), ("7017", "Games/Strategy"),
    ("7018", "Games/Trivia"), ("7019", "Games/Word"),
]

ALL_GENRES = APP_GENRES + GAME_GENRES
LIMIT = 200
FEED_TYPES = [
    ("toppaidapplications", "付费榜"),
    ("topfreeapplications", "免费榜"),
    ("topgrossingapplications", "畅销榜"),
]


def fetch_rss(feed_type, genre_id="", limit=200):
    base = "https://itunes.apple.com/us/rss"
    if genre_id:
        url = f"{base}/{feed_type}/genre={genre_id}/limit={limit}/json"
    else:
        url = f"{base}/{feed_type}/limit={limit}/json"
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            return []
        entries = resp.json().get("feed", {}).get("entry", [])
        apps = []
        for e in entries:
            app_id = e.get("id", {}).get("attributes", {}).get("im:id", "")
            name = e.get("im:name", {}).get("label", "")
            cat = e.get("category", {}).get("attributes", {}).get("label", "")
            if app_id and name:
                apps.append({"id": app_id, "name": name, "category": cat or "Unknown"})
        return apps
    except Exception:
        return []


def search_itunes(term, category=""):
    """用 iTunes Search API 搜索 App，返回正确 ID"""
    url = f"https://itunes.apple.com/search?term={requests.utils.quote(term)}&country=us&entity=software&limit=1"
    try:
        resp = requests.get(url, timeout=15)
        data = resp.json()
        results = data.get("results", [])
        if results:
            r = results[0]
            cat = category or r.get("primaryGenreName", "Unknown")
            return {"id": str(r["trackId"]), "name": r["trackName"], "category": cat}
    except Exception:
        pass
    return None


# ============================================================
# 知名游戏/App 搜索列表（精确搜索词）
# ============================================================
SEARCH_LIST = [
    # --- 任天堂 ---
    ("Mario Kart Tour", "Games/Racing"),
    ("Super Mario Run", "Games/Action"),
    ("Animal Crossing Pocket Camp", "Games/Simulation"),
    ("Fire Emblem Heroes", "Games/Role Playing"),
    ("Pokémon GO", "Games/Adventure"),
    ("Pokémon Sleep", "Games/Simulation"),
    ("Pokémon Masters EX", "Games/Role Playing"),
    ("Pokémon UNITE", "Games/Strategy"),
    # --- 卡普空 ---
    ("Resident Evil 7 biohazard", "Games/Action"),
    ("Resident Evil Village", "Games/Action"),
    ("Resident Evil 4 remake", "Games/Action"),
    ("Monster Hunter Stories", "Games/Role Playing"),
    ("Ghost Trick Phantom Detective", "Games/Puzzle"),
    ("Capcom Arcade Stadium", "Games/Arcade"),
    ("Apollo Justice Ace Attorney", "Games/Adventure"),
    ("The Great Ace Attorney Chronicles", "Games/Adventure"),
    ("Monster Hunter Rise", "Games/Action"),
    # --- Square Enix ---
    ("Final Fantasy XV Pocket Edition", "Games/Role Playing"),
    ("Final Fantasy VII Ever Crisis", "Games/Role Playing"),
    ("Octopath Traveler Champions of the Continent", "Games/Role Playing"),
    ("Chrono Trigger Square Enix", "Games/Role Playing"),
    ("Final Fantasy III", "Games/Role Playing"),
    ("Final Fantasy IV", "Games/Role Playing"),
    ("Final Fantasy VI", "Games/Role Playing"),
    ("Final Fantasy IX", "Games/Role Playing"),
    ("Final Fantasy XII The Zodiac Age", "Games/Role Playing"),
    ("Triangle Strategy", "Games/Role Playing"),
    ("Octopath Traveler", "Games/Role Playing"),
    ("Dragon Quest VIII", "Games/Role Playing"),
    ("NieR Reincarnation", "Games/Role Playing"),
    ("Romancing SaGa Re univerSe", "Games/Role Playing"),
    # --- Konami ---
    ("eFootball 2024", "Games/Sports"),
    ("Yu-Gi-Oh Master Duel", "Games/Card"),
    # --- SEGA ---
    ("Sonic Colors Ultimate", "Games/Action"),
    ("Sonic the Hedgehog 2 Classic", "Games/Action"),
    # --- EA ---
    ("EA Sports FC Mobile", "Games/Sports"),
    ("The Sims FreePlay", "Games/Simulation"),
    ("SimCity BuildIt", "Games/Simulation"),
    ("Need for Speed No Limits", "Games/Racing"),
    ("Plants vs Zombies 2", "Games/Strategy"),
    ("Plants vs Zombies Heroes", "Games/Strategy"),
    ("Star Wars Galaxy of Heroes", "Games/Role Playing"),
    # --- Ubisoft ---
    ("Assassin's Creed Rebellion", "Games/Role Playing"),
    ("Brawlhalla", "Games/Action"),
    # --- Bandai Namco ---
    ("Dragon Ball Legends", "Games/Action"),
    ("Dragon Ball Z Dokkan Battle", "Games/Action"),
    ("Tekken Mobile", "Games/Action"),
    # --- Activision Blizzard King ---
    ("Call of Duty Mobile", "Games/Action"),
    ("Diablo Immortal", "Games/Role Playing"),
    ("Hearthstone", "Games/Card"),
    ("Candy Crush Saga", "Games/Puzzle"),
    ("Call of Duty Warzone Mobile", "Games/Action"),
    # --- Supercell ---
    ("Clash of Clans", "Games/Strategy"),
    ("Clash Royale", "Games/Card"),
    ("Brawl Stars", "Games/Action"),
    ("Hay Day", "Games/Simulation"),
    ("Squad Busters", "Games/Action"),
    # --- Rovio ---
    ("Angry Birds 2", "Games/Arcade"),
    # --- Mojang ---
    ("Minecraft", "Games/Arcade"),
    # --- HoYoverse ---
    ("Genshin Impact", "Games/Role Playing"),
    ("Honkai Star Rail", "Games/Role Playing"),
    ("Honkai Impact 3rd", "Games/Action"),
    ("Zenless Zone Zero", "Games/Action"),
    # --- Riot ---
    ("League of Legends Wild Rift", "Games/Action"),
    ("Teamfight Tactics", "Games/Strategy"),
    # --- Epic ---
    ("Fortnite", "Games/Action"),
    # --- Rockstar 2K ---
    ("Grand Theft Auto San Andreas", "Games/Action"),
    ("Grand Theft Auto The Trilogy", "Games/Action"),
    ("Civilization VI", "Games/Strategy"),
    ("XCOM 2 Collection", "Games/Strategy"),
    ("BioShock", "Games/Action"),
    # --- Bethesda ---
    ("The Elder Scrolls Blades", "Games/Role Playing"),
    ("Fallout Shelter", "Games/Simulation"),
    # --- 独立名作 ---
    ("Stardew Valley", "Games/Simulation"),
    ("Terraria", "Games/Action"),
    ("Dead Cells", "Games/Action"),
    ("Slay the Spire", "Games/Card"),
    ("Monument Valley", "Games/Puzzle"),
    ("Monument Valley 2", "Games/Puzzle"),
    ("GRIS", "Games/Adventure"),
    ("Alto's Odyssey", "Games/Adventure"),
    ("Alto's Adventure", "Games/Adventure"),
    ("Hades", "Games/Action"),
    ("Vampire Survivors", "Games/Action"),
    ("Katana ZERO", "Games/Action"),
    ("Hollow Knight", "Games/Action"),
    ("Cuphead", "Games/Action"),
    ("Among Us", "Games/Arcade"),
    ("Fantasian", "Games/Role Playing"),
    ("Dicey Dungeons", "Games/Card"),
    ("Geometry Dash", "Games/Arcade"),
    ("Old School RuneScape", "Games/Role Playing"),
    ("Bloons TD 6", "Games/Strategy"),
    ("Bloons TD Battles 2", "Games/Strategy"),
    ("Arknights", "Games/Strategy"),
    ("Blue Archive", "Games/Role Playing"),
    ("Azur Lane", "Games/Role Playing"),
    ("Plague Inc", "Games/Strategy"),
    ("The Room", "Games/Puzzle"),
    ("The Room Old Sins", "Games/Puzzle"),
    ("Subway Surfers", "Games/Arcade"),
    ("Crossy Road", "Games/Arcade"),
    ("Temple Run 2", "Games/Arcade"),
    ("jetpack joyride", "Games/Arcade"),
    ("Heads Up", "Games/Trivia"),
    ("Polytopia", "Games/Strategy"),
    ("Five Nights at Freddy's", "Games/Strategy"),
    # --- 热门 App ---
    ("ChatGPT OpenAI", "Productivity"),
    ("Notion", "Productivity"),
    ("Bear notes", "Productivity"),
    ("GoodNotes 6", "Productivity"),
    ("OmniFocus 3", "Productivity"),
    ("Things 3", "Productivity"),
    ("Drafts", "Productivity"),
    ("Fantastical", "Productivity"),
    ("Notability", "Productivity"),
    ("Evernote", "Productivity"),
    ("Procreate", "Graphics & Design"),
    ("Procreate Pocket", "Graphics & Design"),
    ("Darkroom photo editor", "Photo & Video"),
    ("Camera Plus", "Photo & Video"),
    ("LumaFusion", "Photo & Video"),
    ("CapCut", "Photo & Video"),
    ("ProCamera", "Photo & Video"),
    ("Snapseed", "Photo & Video"),
    ("VSCO", "Photo & Video"),
    ("Spotify", "Music"),
    ("GarageBand", "Music"),
    ("TIDAL", "Music"),
    ("Pandora", "Music"),
    ("SoundCloud", "Music"),
    ("Headspace meditation", "Health & Fitness"),
    ("Calm", "Health & Fitness"),
    ("Streaks", "Health & Fitness"),
    ("MyFitnessPal", "Health & Fitness"),
    ("Strava", "Health & Fitness"),
    ("Nike Run Club", "Health & Fitness"),
    ("Amazon Kindle", "Books"),
    ("1Password password manager", "Utilities"),
    ("Bitwarden", "Utilities"),
    ("Shadowrocket", "Utilities"),
    ("Surge", "Utilities"),
    ("NordVPN", "Utilities"),
    ("Craft docs", "Productivity"),
    ("Obsidian md", "Productivity"),
    ("Medium", "News"),
    ("Instapaper", "News"),
    ("Perplexity AI", "Productivity"),
    ("Working Copy git", "Developer Tools"),
    ("Textastic", "Developer Tools"),
    ("Blink Shell", "Developer Tools"),
    ("Scriptable", "Developer Tools"),
    ("Logic Remote", "Music"),
    ("Shazam", "Music"),
    ("Splice video", "Photo & Video"),
    ("Reeder RSS", "News"),
]


def main():
    print("=" * 60)
    print("App Store RSS 批量抓取 — 美区专版 v2")
    print("=" * 60)

    seen_ids = set()
    new_apps = []

    def add_app(app, override_category=None):
        aid = str(app.get("id", ""))
        if aid and aid not in seen_ids:
            seen_ids.add(aid)
            a = dict(app)
            if override_category:
                a["category"] = override_category
            new_apps.append(a)

    # ── 1. RSS 抓取 ──────────────────────────────────────
    print("\n[1/2] 抓取美区 RSS 榜单...")
    for feed_type, label in FEED_TYPES:
        apps = fetch_rss(feed_type, limit=200)
        for a in apps:
            add_app(a)
        time.sleep(random.uniform(0.3, 0.8))
    print(f"  总榜: {len(new_apps)} 个")

    print("  抓取分类榜...")
    for idx, (genre_id, genre_name) in enumerate(ALL_GENRES):
        for feed_type, label in FEED_TYPES:
            apps = fetch_rss(feed_type, genre_id=genre_id, limit=200)
            for a in apps:
                add_app(a, override_category=genre_name)
        time.sleep(random.uniform(0.3, 0.8))
        if (idx + 1) % 10 == 0:
            print(f"    进度: {idx+1}/{len(ALL_GENRES)} 分类，累计 {len(new_apps)} 个")

    rss_count = len(new_apps)
    print(f"  RSS 抓取完成: {rss_count} 个")

    # ── 2. Search API 补充 ──────────────────────────────
    print(f"\n[2/2] 搜索补充列表 ({len(SEARCH_LIST)} 个)...")
    search_added = 0
    search_failed = 0
    for term, category in SEARCH_LIST:
        result = search_itunes(term, category)
        if result:
            add_app(result)
            search_added += 1
        else:
            search_failed += 1
            print(f"  未找到: {term}")
        time.sleep(0.3)

    print(f"  搜索补充: +{search_added} 个, 失败 {search_failed} 个")
    print(f"\n总计: {len(new_apps)} 个 App（全部去重）")

    # ── 3. 保存 ────────────────────────────────────────
    data = {
        "settings": {
            "country": "us",
            "fetch_iap": True,
            "last_updated": time.strftime("%Y-%m-%d"),
            "note": f"US-only watchlist. RSS: {rss_count}, Search: {search_added}. Total: {len(new_apps)}",
        },
        "apps": new_apps,
    }

    with open("watchlist.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open("watchlist_full.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 分类统计
    cats = {}
    for a in new_apps:
        c = a.get("category", "Unknown")
        cats[c] = cats.get(c, 0) + 1
    print("\n分类统计（Top 20）:")
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1])[:20]:
        print(f"  {cat}: {cnt}")


if __name__ == "__main__":
    main()
