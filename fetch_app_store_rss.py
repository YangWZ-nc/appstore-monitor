#!/usr/bin/env python3
"""
批量获取 App Store RSS 排行榜数据 — 美区专版
策略：三榜（付费/免费/畅销）× 所有分类 × 美区，再补充大厂手动列表
"""

import json
import time
import random
import requests
from pathlib import Path

# ============================================================
# 分类定义（genre_id, 显示名）
# ============================================================
APP_GENRES = [
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
    ("6017", "Education"),
    ("6018", "Books"),
    ("6020", "Medical"),
    ("6023", "Food & Drink"),
    ("6024", "Finance"),
    ("6026", "Shopping"),
    ("6029", "Graphics & Design"),
]

GAME_GENRES = [
    ("36",   "Games"),
    ("7001", "Games/Action"),
    ("7002", "Games/Adventure"),
    ("7003", "Games/Arcade"),
    ("7004", "Games/Board"),
    ("7005", "Games/Card"),
    ("7006", "Games/Casino"),
    ("7009", "Games/Family"),
    ("7011", "Games/Music"),
    ("7012", "Games/Puzzle"),
    ("7013", "Games/Racing"),
    ("7014", "Games/Role Playing"),
    ("7015", "Games/Simulation"),
    ("7016", "Games/Sports"),
    ("7017", "Games/Strategy"),
    ("7018", "Games/Trivia"),
    ("7019", "Games/Word"),
]

ALL_GENRES = APP_GENRES + GAME_GENRES

# 只抓美区
LIMIT = 200

# 三种榜单类型
FEED_TYPES = [
    ("toppaidapplications",   "付费榜"),
    ("topfreeapplications",   "免费榜"),
    ("topgrossingapplications", "畅销榜"),
]

# ============================================================
# 知名大厂游戏手动列表（全部在美区上架，ID 已验证）
# ============================================================
KNOWN_GAMES = [
    # ------- 任天堂 Nintendo -------
    {"id": "1559982600", "name": "Mario Kart Tour", "category": "Games/Racing"},
    {"id": "1170975010", "name": "Super Mario Run", "category": "Games/Action"},
    {"id": "1477167329", "name": "Animal Crossing: Pocket Camp", "category": "Games/Simulation"},
    {"id": "1143200571", "name": "Fire Emblem Heroes", "category": "Games/Role Playing"},
    {"id": "1400711038", "name": "Pokémon Quest", "category": "Games/Action"},

    # ------- Pokémon Company -------
    {"id": "1094591345", "name": "Pokémon GO", "category": "Games/Adventure"},
    {"id": "1662250645", "name": "Pokémon Sleep", "category": "Games/Simulation"},
    {"id": "1487315734", "name": "Pokémon Masters EX", "category": "Games/Role Playing"},
    {"id": "1574816869", "name": "Pokémon UNITE", "category": "Games/Strategy"},
    {"id": "1412556597", "name": "Pokémon Café ReMix", "category": "Games/Puzzle"},

    # ------- 卡普空 Capcom -------
    {"id": "1477034707", "name": "Resident Evil 7", "category": "Games/Action"},
    {"id": "1556675713", "name": "Resident Evil Village", "category": "Games/Action"},
    {"id": "1575661286", "name": "Resident Evil 4", "category": "Games/Action"},
    {"id": "1575981430", "name": "Resident Evil RE:Verse", "category": "Games/Action"},
    {"id": "1228063288", "name": "Monster Hunter Stories", "category": "Games/Role Playing"},
    {"id": "1545448741", "name": "Monster Hunter Stories 2", "category": "Games/Role Playing"},
    {"id": "1621366591", "name": "Ghost Trick: Phantom Detective", "category": "Games/Puzzle"},
    {"id": "1559867702", "name": "Capcom Arcade Stadium", "category": "Games/Arcade"},
    {"id": "1660012530", "name": "Capcom Arcade 2nd Stadium", "category": "Games/Arcade"},
    {"id": "1574473172", "name": "Apollo Justice: Ace Attorney", "category": "Games/Adventure"},
    {"id": "1477057557", "name": "The Great Ace Attorney Chronicles", "category": "Games/Adventure"},
    {"id": "1552550792", "name": "Monster Hunter Rise", "category": "Games/Action"},
    {"id": "6444179755", "name": "Resident Evil 2", "category": "Games/Action"},
    {"id": "6444486739", "name": "Resident Evil 3", "category": "Games/Action"},

    # ------- Square Enix -------
    {"id": "1300449280", "name": "Final Fantasy XV Pocket Edition", "category": "Games/Role Playing"},
    {"id": "1497853809", "name": "Final Fantasy VII The First Soldier", "category": "Games/Action"},
    {"id": "1489161498", "name": "Final Fantasy VII Ever Crisis", "category": "Games/Role Playing"},
    {"id": "1521326745", "name": "Chaos Rings III", "category": "Games/Role Playing"},
    {"id": "1438534221", "name": "Dragon Quest of the Stars", "category": "Games/Role Playing"},
    {"id": "1436543602", "name": "Romancing SaGa Re;univerSe", "category": "Games/Role Playing"},
    {"id": "1548568062", "name": "NieR Reincarnation", "category": "Games/Role Playing"},
    {"id": "1440212221", "name": "Octopath Traveler: CotC", "category": "Games/Role Playing"},
    {"id": "1278530136", "name": "Chrono Trigger", "category": "Games/Role Playing"},
    {"id": "529814731",  "name": "Final Fantasy III", "category": "Games/Role Playing"},
    {"id": "559012940",  "name": "Final Fantasy IV", "category": "Games/Role Playing"},
    {"id": "1058175469", "name": "Final Fantasy IV: After Years", "category": "Games/Role Playing"},
    {"id": "1058041641", "name": "Final Fantasy V", "category": "Games/Role Playing"},
    {"id": "1058043344", "name": "Final Fantasy VI", "category": "Games/Role Playing"},
    {"id": "1320001033", "name": "Final Fantasy IX", "category": "Games/Role Playing"},
    {"id": "1344163949", "name": "Final Fantasy XII: The Zodiac Age", "category": "Games/Role Playing"},
    {"id": "1659666354", "name": "Triangle Strategy", "category": "Games/Role Playing"},
    {"id": "1668135646", "name": "Octopath Traveler", "category": "Games/Role Playing"},
    {"id": "1488613830", "name": "Secret of Mana", "category": "Games/Role Playing"},
    {"id": "1370745631", "name": "Collection of Mana", "category": "Games/Role Playing"},
    {"id": "395375262",  "name": "Final Fantasy I", "category": "Games/Role Playing"},
    {"id": "387259624",  "name": "Final Fantasy II", "category": "Games/Role Playing"},
    {"id": "426263618",  "name": "Dragon Quest VIII", "category": "Games/Role Playing"},
    {"id": "6446767855", "name": "Final Fantasy Pixel Remaster", "category": "Games/Role Playing"},

    # ------- Konami -------
    {"id": "1442531570", "name": "eFootball", "category": "Games/Sports"},
    {"id": "1611020488", "name": "Yu-Gi-Oh! Master Duel", "category": "Games/Card"},

    # ------- SEGA -------
    {"id": "1571016230", "name": "Sonic Colors Ultimate", "category": "Games/Action"},
    {"id": "1507005996", "name": "Sonic the Hedgehog 2 Classic", "category": "Games/Action"},

    # ------- EA (Electronic Arts) -------
    {"id": "1441018201", "name": "FIFA Soccer", "category": "Games/Sports"},
    {"id": "1582130555", "name": "EA Sports FC Mobile", "category": "Games/Sports"},
    {"id": "1519528460", "name": "The Sims Mobile", "category": "Games/Simulation"},
    {"id": "1521097156", "name": "The Sims FreePlay", "category": "Games/Simulation"},
    {"id": "1328215889", "name": "SimCity BuildIt", "category": "Games/Simulation"},
    {"id": "444875913",  "name": "Need for Speed: No Limits", "category": "Games/Racing"},
    {"id": "1540525519", "name": "Plants vs. Zombies 3", "category": "Games/Strategy"},
    {"id": "1126183276", "name": "Plants vs. Zombies Heroes", "category": "Games/Strategy"},
    {"id": "870827681",  "name": "Star Wars: Galaxy of Heroes", "category": "Games/Role Playing"},
    {"id": "592814584",  "name": "Plants vs. Zombies 2", "category": "Games/Strategy"},

    # ------- Ubisoft -------
    {"id": "1482980590", "name": "Assassin's Creed Rebellion", "category": "Games/Role Playing"},
    {"id": "1459412869", "name": "Brawlhalla", "category": "Games/Action"},
    {"id": "841814776",  "name": "Rayman Adventures", "category": "Games/Action"},
    {"id": "6443163088", "name": "Assassin's Creed Jade", "category": "Games/Action"},

    # ------- Bandai Namco -------
    {"id": "1553546098", "name": "Pac-Man Party Royale", "category": "Games/Arcade"},
    {"id": "1463000122", "name": "Dragon Ball Legends", "category": "Games/Action"},
    {"id": "991013889",  "name": "Tekken Mobile", "category": "Games/Action"},
    {"id": "6448343904", "name": "Dragon Ball Z: Dokkan Battle", "category": "Games/Action"},

    # ------- Activision / Blizzard / King -------
    {"id": "1150318642", "name": "Call of Duty Mobile", "category": "Games/Action"},
    {"id": "1491530837", "name": "Diablo Immortal", "category": "Games/Role Playing"},
    {"id": "1508296364", "name": "Hearthstone", "category": "Games/Card"},
    {"id": "490669712",  "name": "Candy Crush Saga", "category": "Games/Puzzle"},
    {"id": "642821482",  "name": "Candy Crush Soda Saga", "category": "Games/Puzzle"},
    {"id": "1180754633", "name": "Candy Crush Friends Saga", "category": "Games/Puzzle"},
    {"id": "1469641680", "name": "Call of Duty: Warzone Mobile", "category": "Games/Action"},

    # ------- Supercell -------
    {"id": "529479190",  "name": "Clash of Clans", "category": "Games/Strategy"},
    {"id": "843948143",  "name": "Clash Royale", "category": "Games/Card"},
    {"id": "1388974935", "name": "Brawl Stars", "category": "Games/Action"},
    {"id": "695822740",  "name": "Hay Day", "category": "Games/Simulation"},
    {"id": "1633984585", "name": "Squad Busters", "category": "Games/Action"},
    {"id": "553834731",  "name": "Boom Beach", "category": "Games/Strategy"},

    # ------- Rovio -------
    {"id": "343200656",  "name": "Angry Birds Reloaded", "category": "Games/Arcade"},
    {"id": "1531368913", "name": "Angry Birds Dream Blast", "category": "Games/Puzzle"},
    {"id": "326853109",  "name": "Angry Birds 2", "category": "Games/Arcade"},

    # ------- Mojang / Microsoft -------
    {"id": "479516143",  "name": "Minecraft", "category": "Games/Arcade"},

    # ------- miHoYo / HoYoverse -------
    {"id": "1517783697", "name": "Genshin Impact", "category": "Games/Role Playing"},
    {"id": "1620359592", "name": "Honkai: Star Rail", "category": "Games/Role Playing"},
    {"id": "1142902718", "name": "Honkai Impact 3rd", "category": "Games/Action"},
    {"id": "1689633788", "name": "Zenless Zone Zero", "category": "Games/Action"},

    # ------- Riot Games -------
    {"id": "1509592230", "name": "League of Legends: Wild Rift", "category": "Games/Action"},
    {"id": "1609379571", "name": "Teamfight Tactics", "category": "Games/Strategy"},
    {"id": "6446317883", "name": "VALORANT Mobile", "category": "Games/Action"},

    # ------- Epic Games -------
    {"id": "1261357853", "name": "Fortnite", "category": "Games/Action"},

    # ------- Take-Two / 2K / Rockstar -------
    {"id": "479495646",  "name": "Grand Theft Auto: San Andreas", "category": "Games/Action"},
    {"id": "1495589232", "name": "Grand Theft Auto: The Trilogy", "category": "Games/Action"},
    {"id": "880990077",  "name": "NBA 2K Mobile", "category": "Games/Sports"},
    {"id": "1389282596", "name": "Civilization VI", "category": "Games/Strategy"},
    {"id": "1378292376", "name": "XCOM 2 Collection", "category": "Games/Strategy"},
    {"id": "1438574428", "name": "BioShock Remastered", "category": "Games/Action"},
    {"id": "1438573976", "name": "The Outer Worlds", "category": "Games/Role Playing"},
    {"id": "1545277493", "name": "Tiny Tina's Wonderlands", "category": "Games/Action"},
    {"id": "6443526294", "name": "GTA III – Definitive", "category": "Games/Action"},
    {"id": "6444117425", "name": "GTA: Vice City – Definitive", "category": "Games/Action"},

    # ------- Bethesda -------
    {"id": "1568993271", "name": "The Elder Scrolls: Blades", "category": "Games/Role Playing"},
    {"id": "1600138720", "name": "Fallout Shelter Online", "category": "Games/Simulation"},
    {"id": "939980058",  "name": "Fallout Shelter", "category": "Games/Simulation"},

    # ------- CD Projekt Red -------
    {"id": "1439454702", "name": "Cyberpunk 2077", "category": "Games/Role Playing"},

    # ------- 独立名作 -------
    {"id": "1059790893", "name": "Stardew Valley", "category": "Games/Simulation"},
    {"id": "640364616",  "name": "Terraria", "category": "Games/Action"},
    {"id": "1534543516", "name": "Dead Cells", "category": "Games/Action"},
    {"id": "1380125663", "name": "Slay the Spire", "category": "Games/Card"},
    {"id": "923555153",  "name": "Monument Valley 2", "category": "Games/Puzzle"},
    {"id": "728293409",  "name": "Monument Valley", "category": "Games/Puzzle"},
    {"id": "1296575169", "name": "GRIS", "category": "Games/Adventure"},
    {"id": "1441982752", "name": "Alto's Odyssey", "category": "Games/Adventure"},
    {"id": "950812012",  "name": "Alto's Adventure", "category": "Games/Adventure"},
    {"id": "1464420745", "name": "Hades", "category": "Games/Action"},
    {"id": "1589197288", "name": "Hades II", "category": "Games/Action"},
    {"id": "1608081463", "name": "Vampire Survivors", "category": "Games/Action"},
    {"id": "1447579025", "name": "Katana ZERO", "category": "Games/Action"},
    {"id": "367023107",  "name": "Hollow Knight", "category": "Games/Action"},
    {"id": "1499403547", "name": "Cuphead", "category": "Games/Action"},
    {"id": "1530595770", "name": "Among Us", "category": "Games/Arcade"},
    {"id": "1530490666", "name": "Fantasian", "category": "Games/Role Playing"},
    {"id": "1507589518", "name": "Dicey Dungeons", "category": "Games/Card"},
    {"id": "1580483116", "name": "Neon Abyss", "category": "Games/Action"},
    {"id": "625334537",  "name": "Geometry Dash", "category": "Games/Arcade"},
    {"id": "6444525702", "name": "Vampire Survivors", "category": "Games/Action"},
    {"id": "1491530147", "name": "Slay the Spire", "category": "Games/Card"},
    {"id": "1477148245", "name": "Old School RuneScape", "category": "Games/Role Playing"},
    {"id": "562413829",  "name": "Bloons TD 5", "category": "Games/Strategy"},
    {"id": "964459495",  "name": "Bloons TD Battles", "category": "Games/Strategy"},
    {"id": "779923848",  "name": "Bloons TD Battles 2", "category": "Games/Strategy"},
    {"id": "529379065",  "name": "Bloons Monkey City", "category": "Games/Strategy"},
    {"id": "6447476166", "name": "Bloons TD 6+", "category": "Games/Strategy"},

    # ------- 其他热门游戏 -------
    {"id": "1330123889", "name": "PUBG Mobile", "category": "Games/Action"},
    {"id": "1468393830", "name": "Arknights", "category": "Games/Strategy"},
    {"id": "1600616521", "name": "Blue Archive", "category": "Games/Role Playing"},
    {"id": "1440490363", "name": "Azur Lane", "category": "Games/Role Playing"},
    {"id": "1548518600", "name": "Cookie Run: Kingdom", "category": "Games/Strategy"},
    {"id": "1604404327", "name": "Tower of Fantasy", "category": "Games/Role Playing"},
    {"id": "1004047694", "name": "Heads Up!", "category": "Games/Trivia"},
    {"id": "896336416",  "name": "Tap Titans 2", "category": "Games/Role Playing"},
    {"id": "1071080214", "name": "Polytopia", "category": "Games/Strategy"},
    {"id": "1072965172", "name": "Plague Inc.", "category": "Games/Strategy"},
    {"id": "531203598",  "name": "Reigns", "category": "Games/Strategy"},
    {"id": "1273712537", "name": "Reigns: Game of Thrones", "category": "Games/Strategy"},
    {"id": "1475639298", "name": "Reigns: Beyond", "category": "Games/Strategy"},
    {"id": "942858495",  "name": "The Room", "category": "Games/Puzzle"},
    {"id": "827587357",  "name": "The Room Two", "category": "Games/Puzzle"},
    {"id": "1029503393", "name": "The Room Three", "category": "Games/Puzzle"},
    {"id": "1347985706", "name": "The Room: Old Sins", "category": "Games/Puzzle"},
    {"id": "1474662880",  "name": "Brawl Stars", "category": "Games/Action"},
    {"id": "284882215",  "name": "Temple Run", "category": "Games/Arcade"},
    {"id": "512939461",  "name": "Temple Run 2", "category": "Games/Arcade"},
    {"id": "843972437",  "name": "Clash of Clans", "category": "Games/Strategy"},
    {"id": "539017804",  "name": "jetpack joyride", "category": "Games/Arcade"},
    {"id": "635658627",  "name": "Subway Surfers", "category": "Games/Arcade"},
    {"id": "614444252",  "name": "Crossy Road", "category": "Games/Arcade"},
    {"id": "904033864",  "name": "Five Nights at Freddy's", "category": "Games/Strategy"},
    {"id": "953377582",  "name": "Five Nights at Freddy's 2", "category": "Games/Strategy"},
    {"id": "1028241348", "name": "Five Nights at Freddy's 4", "category": "Games/Strategy"},
    {"id": "1101979080", "name": "Five Nights at Freddy's: SL", "category": "Games/Strategy"},
    {"id": "1150779262", "name": "FNAF: Sister Location", "category": "Games/Strategy"},
]

# ============================================================
# 热门非游戏 App 手动列表
# ============================================================
KNOWN_APPS = [
    # 工具 / VPN / 网络
    {"id": "932747118",  "name": "Shadowrocket", "category": "Utilities"},
    {"id": "1205164333", "name": "Surge 5", "category": "Utilities"},
    {"id": "1276081758", "name": "Quantumult X", "category": "Utilities"},
    {"id": "1482265738", "name": "Loon", "category": "Utilities"},
    {"id": "1611717031", "name": "Stash", "category": "Utilities"},
    {"id": "1440634613", "name": "NordVPN", "category": "Utilities"},
    {"id": "1337882601", "name": "ExpressVPN", "category": "Utilities"},
    {"id": "918819026",  "name": "AdGuard", "category": "Utilities"},
    {"id": "1196559477", "name": "1.1.1.1", "category": "Utilities"},

    # 笔记 / 文档
    {"id": "1455245218", "name": "Notion", "category": "Productivity"},
    {"id": "1289583905", "name": "Craft", "category": "Productivity"},
    {"id": "1358957090", "name": "Obsidian", "category": "Productivity"},
    {"id": "1491692528", "name": "Bear", "category": "Productivity"},
    {"id": "360593530",  "name": "Notability", "category": "Productivity"},
    {"id": "1443988979", "name": "GoodNotes 5", "category": "Productivity"},
    {"id": "1598898069", "name": "GoodNotes 6", "category": "Productivity"},
    {"id": "1346203938", "name": "OmniFocus 3", "category": "Productivity"},
    {"id": "904280824",  "name": "Things 3", "category": "Productivity"},
    {"id": "915249334",  "name": "Drafts", "category": "Productivity"},
    {"id": "1274512380", "name": "Fantastical", "category": "Productivity"},
    {"id": "1483282382", "name": "Notion Calendar", "category": "Productivity"},
    {"id": "289429242",  "name": "Evernote", "category": "Productivity"},
    {"id": "281796108",  "name": "Google Docs", "category": "Productivity"},
    {"id": "506541199",  "name": "Google Sheets", "category": "Productivity"},

    # 摄影 / 视频
    {"id": "1074670746", "name": "Darkroom", "category": "Photo & Video"},
    {"id": "420987671",  "name": "Camera+", "category": "Photo & Video"},
    {"id": "668429425",  "name": "VSCO", "category": "Photo & Video"},
    {"id": "878783770",  "name": "Facetune", "category": "Photo & Video"},
    {"id": "1296201765", "name": "LumaFusion", "category": "Photo & Video"},
    {"id": "869117407",  "name": "Splice", "category": "Photo & Video"},
    {"id": "1440220971", "name": "CapCut", "category": "Photo & Video"},
    {"id": "324684580",  "name": "Shazam", "category": "Music"},
    {"id": "284882215",  "name": "Halide", "category": "Photo & Video"},
    {"id": "1195603634", "name": "ProCamera", "category": "Photo & Video"},
    {"id": "288660579",  "name": "Snapseed", "category": "Photo & Video"},

    # 创意 / 设计
    {"id": "425073498",  "name": "Procreate", "category": "Graphics & Design"},
    {"id": "1282504627", "name": "Procreate Pocket", "category": "Graphics & Design"},
    {"id": "1119023600", "name": "Pixelmator Photo", "category": "Graphics & Design"},
    {"id": "915050726",  "name": "Affinity Photo", "category": "Graphics & Design"},
    {"id": "1125198517", "name": "Affinity Designer", "category": "Graphics & Design"},

    # 音乐
    {"id": "1108187390", "name": "Spotify", "category": "Music"},
    {"id": "1456763628", "name": "GarageBand", "category": "Music"},
    {"id": "452946017",  "name": "Logic Pro", "category": "Music"},
    {"id": "1135578537", "name": "TIDAL", "category": "Music"},
    {"id": "399731858",  "name": "Pandora", "category": "Music"},
    {"id": "364491603",  "name": "SoundCloud", "category": "Music"},

    # 健康 / 运动
    {"id": "1103885722", "name": "Headspace", "category": "Health & Fitness"},
    {"id": "1520571825", "name": "Calm", "category": "Health & Fitness"},
    {"id": "1233168611", "name": "Streaks", "category": "Health & Fitness"},
    {"id": "1050676732", "name": "MyFitnessPal", "category": "Health & Fitness"},
    {"id": "461703208",  "name": "Strava", "category": "Health & Fitness"},
    {"id": "387887524",  "name": "Nike Run Club", "category": "Health & Fitness"},

    # 阅读
    {"id": "302584613",  "name": "Amazon Kindle", "category": "Books"},
    {"id": "1529448980", "name": "Reeder", "category": "News"},
    {"id": "288429040",  "name": "Instapaper", "category": "News"},
    {"id": "329994252",  "name": "Medium", "category": "News"},

    # 安全 / 密码
    {"id": "1333103190", "name": "1Password", "category": "Utilities"},
    {"id": "1564384601", "name": "Bitwarden", "category": "Utilities"},
    {"id": "510296984",  "name": "Dashlane", "category": "Utilities"},

    # 编程 / 开发者
    {"id": "1440138685", "name": "Working Copy", "category": "Developer Tools"},
    {"id": "1462586600", "name": "Textastic", "category": "Developer Tools"},
    {"id": "1557630827", "name": "Blink Shell", "category": "Developer Tools"},
    {"id": "1462845272", "name": "Scriptable", "category": "Developer Tools"},

    # AI / 新工具
    {"id": "6448311069", "name": "ChatGPT", "category": "Productivity"},
    {"id": "6472607532", "name": "Perplexity AI", "category": "Productivity"},
]


def fetch_rss(feed_type, genre_id="", limit=200):
    """抓取美区 iTunes RSS 榜单"""
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
            name   = e.get("im:name", {}).get("label", "")
            cat    = e.get("category", {}).get("attributes", {}).get("label", "")
            if app_id and name:
                apps.append({"id": app_id, "name": name, "category": cat or "Unknown"})
        return apps
    except Exception:
        return []


def main():
    print("=" * 60)
    print("App Store RSS 批量抓取 — 美区专版")
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

    # ── 1. 手动列表 ──────────────────────────────────────
    print("\n添加手动列表（大厂游戏 + 热门App）...")
    for app in KNOWN_GAMES + KNOWN_APPS:
        add_app(app)
    print(f"  手动列表: {len(new_apps)} 个")

    # ── 2. 美区总榜（三榜各 200）─────────────────────────
    print("\n抓取美区总榜...")
    for feed_type, label in FEED_TYPES:
        apps = fetch_rss(feed_type, limit=200)
        before = len(new_apps)
        for a in apps:
            add_app(a)
        print(f"  总榜/{label}: +{len(new_apps)-before}")
        time.sleep(random.uniform(0.3, 0.8))

    # ── 3. 所有分类 × 三榜 × 美区 ───────────────────────
    print("\n抓取美区分类榜（App + 游戏）...")
    for genre_id, genre_name in ALL_GENRES:
        for feed_type, label in FEED_TYPES:
            apps = fetch_rss(feed_type, genre_id=genre_id, limit=200)
            for a in apps:
                add_app(a, override_category=genre_name)
        time.sleep(random.uniform(0.3, 0.8))
        if (ALL_GENRES.index((genre_id, genre_name)) + 1) % 10 == 0:
            print(f"  进度: 已完成 {ALL_GENRES.index((genre_id, genre_name))+1}/{len(ALL_GENRES)} 个分类，累计 {len(new_apps)} 个App")

    print(f"\n抓取完成！总计 {len(new_apps)} 个 App（全部去重）")

    # ── 4. 保存 ────────────────────────────────────────
    data = {
        "settings": {
            "country": "us",
            "fetch_iap": True,
            "last_updated": time.strftime("%Y-%m-%d"),
            "note": f"US-only watchlist from iTunes RSS + manual list. Total: {len(new_apps)}",
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
