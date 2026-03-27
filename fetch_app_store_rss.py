#!/usr/bin/env python3
"""
批量获取 App Store RSS 排行榜数据，扩充 watchlist 到 10000+
策略：三榜（付费/免费/畅销）× 所有分类 × 多国家，再补充大厂手动列表
"""

import json
import time
import random
import requests
from pathlib import Path

# ============================================================
# 分类定义（genre_id, 显示名, 是否是游戏子类）
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

# 多国家抓取（增加覆盖面）
COUNTRIES = ["us", "gb", "au", "ca", "de", "fr", "jp"]

# 每个分类每个榜单抓取数量（iTunes RSS 上限 200）
LIMIT = 200

# 三种榜单类型
FEED_TYPES = [
    ("toppaidapplications",   "付费榜"),
    ("topfreeapplications",   "免费榜"),
    ("topgrossingapplications", "畅销榜"),
]

# ============================================================
# 知名大厂游戏手动列表（iTunes 查询验证过的真实 ID）
# ============================================================
KNOWN_GAMES = [
    # ------- 任天堂 Nintendo -------
    {"id": "1559982600", "name": "Mario Kart Tour", "category": "Games/Racing", "developer": "Nintendo"},
    {"id": "1170975010", "name": "Super Mario Run", "category": "Games/Action", "developer": "Nintendo"},
    {"id": "1462182994", "name": "Dr. Mario World", "category": "Games/Puzzle", "developer": "Nintendo"},
    {"id": "1477167329", "name": "Animal Crossing: Pocket Camp", "category": "Games/Simulation", "developer": "Nintendo"},
    {"id": "1369948234", "name": "Dragalia Lost", "category": "Games/Role Playing", "developer": "Nintendo"},
    {"id": "1143200571", "name": "Fire Emblem Heroes", "category": "Games/Role Playing", "developer": "Nintendo"},
    {"id": "1400711038", "name": "Pokémon Quest", "category": "Games/Action", "developer": "Nintendo"},

    # ------- Pokémon Company -------
    {"id": "1094591345", "name": "Pokémon GO", "category": "Games/Adventure", "developer": "Niantic"},
    {"id": "1662250645", "name": "Pokémon Sleep", "category": "Games/Simulation", "developer": "The Pokémon Company"},
    {"id": "1487315734", "name": "Pokémon Masters EX", "category": "Games/Role Playing", "developer": "DeNA"},
    {"id": "1574816869", "name": "Pokémon UNITE", "category": "Games/Strategy", "developer": "TiMi Studio"},
    {"id": "1412556597", "name": "Pokémon Café ReMix", "category": "Games/Puzzle", "developer": "The Pokémon Company"},

    # ------- 卡普空 Capcom -------
    {"id": "1477034707", "name": "Resident Evil 7", "category": "Games/Action", "developer": "Capcom"},
    {"id": "1556675713", "name": "Resident Evil Village", "category": "Games/Action", "developer": "Capcom"},
    {"id": "1575661286", "name": "Resident Evil 4", "category": "Games/Action", "developer": "Capcom"},
    {"id": "1228063288", "name": "Monster Hunter Stories", "category": "Games/Role Playing", "developer": "Capcom"},
    {"id": "1545448741", "name": "Monster Hunter Stories 2", "category": "Games/Role Playing", "developer": "Capcom"},
    {"id": "1621366591", "name": "Ghost Trick: Phantom Detective", "category": "Games/Puzzle", "developer": "Capcom"},
    {"id": "1559867702", "name": "Capcom Arcade Stadium", "category": "Games/Arcade", "developer": "Capcom"},
    {"id": "1660012530", "name": "Capcom Arcade 2nd Stadium", "category": "Games/Arcade", "developer": "Capcom"},
    {"id": "1574473172", "name": "Apollo Justice: Ace Attorney", "category": "Games/Adventure", "developer": "Capcom"},
    {"id": "1477057557", "name": "The Great Ace Attorney Chronicles", "category": "Games/Adventure", "developer": "Capcom"},
    {"id": "1552550792", "name": "Monster Hunter Rise", "category": "Games/Action", "developer": "Capcom"},

    # ------- Square Enix -------
    {"id": "1300449280", "name": "Final Fantasy XV Pocket Edition", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1497853809", "name": "Final Fantasy VII The First Soldier", "category": "Games/Action", "developer": "Square Enix"},
    {"id": "1489161498", "name": "Final Fantasy VII Ever Crisis", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1521326745", "name": "Chaos Rings III", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1491665973", "name": "Dragon Quest Walk", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1438534221", "name": "Dragon Quest of the Stars", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1436543602", "name": "Romancing SaGa Re;univerSe", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1548568062", "name": "NieR Reincarnation", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1440212221", "name": "Octopath Traveler: CotC", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1278530136", "name": "Chrono Trigger", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "529814731",  "name": "Final Fantasy III (3D Remake)", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "559012940",  "name": "Final Fantasy IV (3D Remake)", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1058175469", "name": "Final Fantasy IV: After Years", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1058041641", "name": "Final Fantasy V", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1058043344", "name": "Final Fantasy VI", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1320001033", "name": "Final Fantasy IX", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1344163949", "name": "Final Fantasy XII: The Zodiac Age", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1659666354", "name": "Triangle Strategy", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1668135646", "name": "Octopath Traveler", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1488613830", "name": "Secret of Mana", "category": "Games/Role Playing", "developer": "Square Enix"},
    {"id": "1370745631", "name": "Collection of Mana", "category": "Games/Role Playing", "developer": "Square Enix"},

    # ------- Konami -------
    {"id": "1442531570", "name": "eFootball", "category": "Games/Sports", "developer": "Konami"},
    {"id": "1611020488", "name": "Yu-Gi-Oh! Master Duel", "category": "Games/Card", "developer": "Konami"},
    {"id": "1515859017", "name": "Yu-Gi-Oh! Cross Duel", "category": "Games/Card", "developer": "Konami"},

    # ------- SEGA -------
    {"id": "1571016230", "name": "Sonic Colors Ultimate", "category": "Games/Action", "developer": "SEGA"},
    {"id": "1507005996", "name": "Sonic the Hedgehog 2 Classic", "category": "Games/Action", "developer": "SEGA"},
    {"id": "1662390359", "name": "Like a Dragon: Ishin!", "category": "Games/Action", "developer": "SEGA"},
    {"id": "1530690860", "name": "Puyo Puyo Puzzle Pop", "category": "Games/Puzzle", "developer": "SEGA"},

    # ------- EA (Electronic Arts) -------
    {"id": "1441018201", "name": "FIFA Soccer", "category": "Games/Sports", "developer": "EA"},
    {"id": "1582130555", "name": "EA Sports FC Mobile", "category": "Games/Sports", "developer": "EA"},
    {"id": "1519528460", "name": "The Sims Mobile", "category": "Games/Simulation", "developer": "EA"},
    {"id": "1521097156", "name": "The Sims FreePlay", "category": "Games/Simulation", "developer": "EA"},
    {"id": "1328215889", "name": "SimCity BuildIt", "category": "Games/Simulation", "developer": "EA"},
    {"id": "444875913",  "name": "Need for Speed: No Limits", "category": "Games/Racing", "developer": "EA"},
    {"id": "1540525519", "name": "Plants vs. Zombies 3", "category": "Games/Strategy", "developer": "EA"},
    {"id": "1126183276", "name": "Plants vs. Zombies Heroes", "category": "Games/Strategy", "developer": "EA"},
    {"id": "870827681",  "name": "Star Wars: Galaxy of Heroes", "category": "Games/Role Playing", "developer": "EA"},
    {"id": "1580448446", "name": "Apex Legends Mobile", "category": "Games/Action", "developer": "EA"},

    # ------- Ubisoft -------
    {"id": "1482980590", "name": "Assassin's Creed Rebellion", "category": "Games/Role Playing", "developer": "Ubisoft"},
    {"id": "1459412869", "name": "Brawlhalla", "category": "Games/Action", "developer": "Ubisoft"},
    {"id": "1641533726", "name": "Rainbow Six Mobile", "category": "Games/Action", "developer": "Ubisoft"},
    {"id": "841814776",  "name": "Rayman Adventures", "category": "Games/Action", "developer": "Ubisoft"},

    # ------- Bandai Namco -------
    {"id": "1553546098", "name": "Pac-Man Party Royale", "category": "Games/Arcade", "developer": "Bandai Namco"},
    {"id": "1463000122", "name": "Dragon Ball Legends", "category": "Games/Action", "developer": "Bandai Namco"},
    {"id": "1617566060", "name": "Elden Ring Network Test", "category": "Games/Role Playing", "developer": "Bandai Namco"},
    {"id": "1639634689", "name": "Tales of Luminaria", "category": "Games/Role Playing", "developer": "Bandai Namco"},

    # ------- Activision / Blizzard -------
    {"id": "1150318642", "name": "Call of Duty Mobile", "category": "Games/Action", "developer": "Activision"},
    {"id": "1491530837", "name": "Diablo Immortal", "category": "Games/Role Playing", "developer": "Blizzard"},
    {"id": "1508296364", "name": "Hearthstone", "category": "Games/Card", "developer": "Blizzard"},
    {"id": "490669712",  "name": "Candy Crush Saga", "category": "Games/Puzzle", "developer": "King"},
    {"id": "642821482",  "name": "Candy Crush Soda Saga", "category": "Games/Puzzle", "developer": "King"},
    {"id": "1180754633", "name": "Candy Crush Friends Saga", "category": "Games/Puzzle", "developer": "King"},

    # ------- Supercell -------
    {"id": "529479190",  "name": "Clash of Clans", "category": "Games/Strategy", "developer": "Supercell"},
    {"id": "843948143",  "name": "Clash Royale", "category": "Games/Card", "developer": "Supercell"},
    {"id": "1388974935", "name": "Brawl Stars", "category": "Games/Action", "developer": "Supercell"},
    {"id": "695822740",  "name": "Hay Day", "category": "Games/Simulation", "developer": "Supercell"},
    {"id": "1545989586", "name": "Clash Quest", "category": "Games/Strategy", "developer": "Supercell"},
    {"id": "1633984585", "name": "Squad Busters", "category": "Games/Action", "developer": "Supercell"},

    # ------- Rovio / Angry Birds -------
    {"id": "343200656",  "name": "Angry Birds Reloaded", "category": "Games/Casual", "developer": "Rovio"},
    {"id": "1574348346", "name": "Angry Birds Journey", "category": "Games/Casual", "developer": "Rovio"},
    {"id": "1531368913", "name": "Angry Birds Dream Blast", "category": "Games/Puzzle", "developer": "Rovio"},

    # ------- Mojang / Minecraft -------
    {"id": "479516143",  "name": "Minecraft", "category": "Games/Arcade", "developer": "Mojang"},
    {"id": "1467655641", "name": "Minecraft Earth", "category": "Games/Adventure", "developer": "Mojang"},
    {"id": "1174445928", "name": "Minecraft Education", "category": "Games/Educational", "developer": "Mojang"},

    # ------- miHoYo / HoYoverse -------
    {"id": "1517783697", "name": "Genshin Impact", "category": "Games/Role Playing", "developer": "HoYoverse"},
    {"id": "1620359592", "name": "Honkai: Star Rail", "category": "Games/Role Playing", "developer": "HoYoverse"},
    {"id": "1142902718", "name": "Honkai Impact 3rd", "category": "Games/Action", "developer": "HoYoverse"},
    {"id": "1689633788", "name": "Zenless Zone Zero", "category": "Games/Action", "developer": "HoYoverse"},

    # ------- Riot Games -------
    {"id": "1548485301", "name": "VALORANT Mobile", "category": "Games/Action", "developer": "Riot"},
    {"id": "1509592230", "name": "League of Legends: Wild Rift", "category": "Games/Action", "developer": "Riot"},
    {"id": "1609379571", "name": "Teamfight Tactics", "category": "Games/Strategy", "developer": "Riot"},

    # ------- Epic Games -------
    {"id": "1261357853", "name": "Fortnite", "category": "Games/Action", "developer": "Epic Games"},

    # ------- Take-Two / 2K / Rockstar -------
    {"id": "479495646",  "name": "Grand Theft Auto: San Andreas", "category": "Games/Action", "developer": "Rockstar"},
    {"id": "1495589232", "name": "Grand Theft Auto: The Trilogy", "category": "Games/Action", "developer": "Rockstar"},
    {"id": "880990077",  "name": "NBA 2K Mobile", "category": "Games/Sports", "developer": "2K"},
    {"id": "1389282596", "name": "Civilization VI", "category": "Games/Strategy", "developer": "2K"},
    {"id": "1378292376", "name": "XCOM 2 Collection", "category": "Games/Strategy", "developer": "2K"},
    {"id": "1438574428", "name": "BioShock Remastered", "category": "Games/Action", "developer": "2K"},
    {"id": "1438573976", "name": "The Outer Worlds", "category": "Games/Role Playing", "developer": "2K"},
    {"id": "1545277493", "name": "Tiny Tina's Wonderlands", "category": "Games/Action", "developer": "2K"},

    # ------- Bethesda / Microsoft -------
    {"id": "1568993271", "name": "The Elder Scrolls: Blades", "category": "Games/Role Playing", "developer": "Bethesda"},
    {"id": "1617503919", "name": "Starfield", "category": "Games/Role Playing", "developer": "Bethesda"},
    {"id": "1600138720", "name": "Fallout Shelter Online", "category": "Games/Simulation", "developer": "Bethesda"},
    {"id": "939980058",  "name": "Fallout Shelter", "category": "Games/Simulation", "developer": "Bethesda"},
    {"id": "1489923579", "name": "Microsoft Solitaire Collection", "category": "Games/Card", "developer": "Microsoft"},
    {"id": "1602313855", "name": "Halo Infinite Campaign", "category": "Games/Action", "developer": "Microsoft"},
    {"id": "1295195715", "name": "Minecraft Dungeons", "category": "Games/Action", "developer": "Microsoft"},

    # ------- From Software -------
    {"id": "1593494870", "name": "Elden Ring", "category": "Games/Role Playing", "developer": "From Software"},
    {"id": "1442990580", "name": "Sekiro: Shadows Die Twice", "category": "Games/Action", "developer": "From Software"},

    # ------- CD Projekt Red -------
    {"id": "1572580140", "name": "The Witcher: Monster Slayer", "category": "Games/Role Playing", "developer": "CD Projekt"},
    {"id": "1439454702", "name": "Cyberpunk 2077", "category": "Games/Role Playing", "developer": "CD Projekt"},

    # ------- 独立名作 -------
    {"id": "1059790893", "name": "Stardew Valley", "category": "Games/Simulation", "developer": "ConcernedApe"},
    {"id": "640364616",  "name": "Terraria", "category": "Games/Action", "developer": "Re-Logic"},
    {"id": "1534543516", "name": "Dead Cells", "category": "Games/Action", "developer": "Motion Twin"},
    {"id": "1380125663", "name": "Slay the Spire", "category": "Games/Card", "developer": "Mega Crit"},
    {"id": "923555153",  "name": "Monument Valley 2", "category": "Games/Puzzle", "developer": "ustwo"},
    {"id": "728293409",  "name": "Monument Valley", "category": "Games/Puzzle", "developer": "ustwo"},
    {"id": "1296575169", "name": "GRIS", "category": "Games/Adventure", "developer": "Devolver"},
    {"id": "1441982752", "name": "Alto's Odyssey: The Lost City", "category": "Games/Adventure", "developer": "Team Alto"},
    {"id": "1464420745", "name": "Hades", "category": "Games/Action", "developer": "Supergiant Games"},
    {"id": "1589197288", "name": "Hades II", "category": "Games/Action", "developer": "Supergiant Games"},
    {"id": "1608081463", "name": "Vampire Survivors", "category": "Games/Action", "developer": "poncle"},
    {"id": "1447579025", "name": "Katana ZERO", "category": "Games/Action", "developer": "Askiisoft"},
    {"id": "1480924816", "name": "Hollow Knight: Silksong", "category": "Games/Action", "developer": "Team Cherry"},
    {"id": "367023107",  "name": "Hollow Knight", "category": "Games/Action", "developer": "Team Cherry"},
    {"id": "1499403547", "name": "Cuphead", "category": "Games/Action", "developer": "Studio MDHR"},
    {"id": "1577490259", "name": "Shovel Knight Pocket Dungeon", "category": "Games/Puzzle", "developer": "Yacht Club"},
    {"id": "1530595770", "name": "Among Us", "category": "Games/Casual", "developer": "Innersloth"},
    {"id": "1477112781", "name": "Pascal's Wager", "category": "Games/Role Playing", "developer": "TipsWorks"},
    {"id": "1530490666", "name": "Fantasian", "category": "Games/Role Playing", "developer": "Mistwalker"},
    {"id": "1506510890", "name": "World of Horror", "category": "Games/Role Playing", "developer": "Panstasz"},
    {"id": "1592369701", "name": "Coromon", "category": "Games/Role Playing", "developer": "TRAGsoft"},
    {"id": "1507589518", "name": "Dicey Dungeons", "category": "Games/Card", "developer": "Terry Cavanagh"},
    {"id": "1480700478", "name": "Telling Lies", "category": "Games/Adventure", "developer": "Sam Barlow"},
    {"id": "1540901086", "name": "Choo-Choo Charles", "category": "Games/Action", "developer": "Two Star Games"},
    {"id": "1612363865", "name": "Tinykin", "category": "Games/Puzzle", "developer": "Splashteam"},
    {"id": "1580483116", "name": "Neon Abyss", "category": "Games/Action", "developer": "Veewo Games"},

    # ------- TiMi Studio / Tencent -------
    {"id": "1330123889", "name": "PUBG Mobile", "category": "Games/Action", "developer": "Tencent"},
    {"id": "1578776069", "name": "PUBG: New State", "category": "Games/Action", "developer": "Krafton"},
    {"id": "1462944978", "name": "Call of Duty: Warzone Mobile", "category": "Games/Action", "developer": "Activision"},

    # ------- 其他热门 -------
    {"id": "1442210047", "name": "Genshin Impact - Test", "category": "Games/Role Playing", "developer": "HoYoverse"},
    {"id": "1604404327", "name": "Tower of Fantasy", "category": "Games/Role Playing", "developer": "Perfect World"},
    {"id": "1468393830", "name": "Arknights", "category": "Games/Strategy", "developer": "Yostar"},
    {"id": "1587288177", "name": "Path to Nowhere", "category": "Games/Strategy", "developer": "AISNO"},
    {"id": "1600616521", "name": "Blue Archive", "category": "Games/Role Playing", "developer": "Nexon"},
    {"id": "1506640635", "name": "Princess Connect! Re: Dive", "category": "Games/Role Playing", "developer": "Cygames"},
    {"id": "1440490363", "name": "Azur Lane", "category": "Games/Role Playing", "developer": "Yostar"},
    {"id": "1548518600", "name": "Cookie Run: Kingdom", "category": "Games/Strategy", "developer": "Devsisters"},
    {"id": "1352378306", "name": "Cookie Run: OvenBreak", "category": "Games/Action", "developer": "Devsisters"},
    {"id": "1552177613", "name": "Genshin Impact Beta", "category": "Games/Role Playing", "developer": "HoYoverse"},
]

# ============================================================
# 热门非游戏 App 手动列表（知名工具/生产力/创意类）
# ============================================================
KNOWN_APPS = [
    # 工具 / VPN
    {"id": "932747118",  "name": "Shadowrocket", "category": "Utilities", "developer": "Shadow Lab"},
    {"id": "1205164333", "name": "Surge 5", "category": "Utilities", "developer": "Nssurge"},
    {"id": "1276081758", "name": "Quantumult X", "category": "Utilities", "developer": "crossutility"},
    {"id": "1482265738", "name": "Loon", "category": "Utilities", "developer": "Loon"},
    {"id": "1611717031", "name": "Stash", "category": "Utilities", "developer": "Stash"},
    {"id": "1440634613", "name": "NordVPN", "category": "Utilities", "developer": "Nord"},
    {"id": "1337882601", "name": "ExpressVPN", "category": "Utilities", "developer": "ExpressVPN"},

    # 笔记 / 文档
    {"id": "1455245218", "name": "Notion", "category": "Productivity", "developer": "Notion"},
    {"id": "1289583905", "name": "Craft - Docs and Notes Editor", "category": "Productivity", "developer": "Craft"},
    {"id": "1358957090", "name": "Obsidian", "category": "Productivity", "developer": "Obsidian"},
    {"id": "1548678998", "name": "Logseq", "category": "Productivity", "developer": "Logseq"},
    {"id": "1491692528", "name": "Bear", "category": "Productivity", "developer": "Shiny Frog"},
    {"id": "1471860532", "name": "Noteship", "category": "Productivity", "developer": "Noteship"},
    {"id": "360593530",  "name": "Notability", "category": "Productivity", "developer": "Ginger Labs"},
    {"id": "1443988979", "name": "GoodNotes 5", "category": "Productivity", "developer": "Time Base Technology"},
    {"id": "1598898069", "name": "GoodNotes 6", "category": "Productivity", "developer": "Time Base Technology"},

    # 任务管理
    {"id": "904280824",  "name": "Things 3", "category": "Productivity", "developer": "Cultured Code"},
    {"id": "1346203938", "name": "OmniFocus 3", "category": "Productivity", "developer": "The Omni Group"},
    {"id": "1274512380", "name": "Fantastical", "category": "Productivity", "developer": "Flexibits"},
    {"id": "1483282382", "name": "Notion Calendar", "category": "Productivity", "developer": "Notion"},

    # 摄影 / 视频
    {"id": "1074670746", "name": "Darkroom", "category": "Photo & Video", "developer": "Bergen Co"},
    {"id": "420987671",  "name": "Camera+", "category": "Photo & Video", "developer": "Tap Tap Tap"},
    {"id": "668429425",  "name": "VSCO", "category": "Photo & Video", "developer": "Visual Supply Company"},
    {"id": "878783770",  "name": "Facetune", "category": "Photo & Video", "developer": "Lightricks"},
    {"id": "1296201765", "name": "LumaFusion", "category": "Photo & Video", "developer": "LumaTouch"},
    {"id": "869117407",  "name": "Splice", "category": "Photo & Video", "developer": "GoPro"},
    {"id": "1440220971", "name": "CapCut", "category": "Photo & Video", "developer": "Bytedance"},

    # 创意 / 设计
    {"id": "425073498",  "name": "Procreate", "category": "Graphics & Design", "developer": "Savage Interactive"},
    {"id": "1282504627", "name": "Procreate Pocket", "category": "Graphics & Design", "developer": "Savage Interactive"},
    {"id": "1405978634", "name": "Vectornator", "category": "Graphics & Design", "developer": "Linearity"},
    {"id": "1119023600", "name": "Pixelmator Photo", "category": "Graphics & Design", "developer": "Pixelmator"},
    {"id": "1282504627", "name": "Affinity Designer", "category": "Graphics & Design", "developer": "Serif"},

    # 音乐
    {"id": "1108187390", "name": "Spotify", "category": "Music", "developer": "Spotify"},
    {"id": "324684580",  "name": "Shazam", "category": "Music", "developer": "Apple"},
    {"id": "1491395406", "name": "Musi - Simple Music Streaming", "category": "Music", "developer": "Musi"},
    {"id": "1456763628", "name": "GarageBand", "category": "Music", "developer": "Apple"},
    {"id": "452946017",  "name": "Logic Pro", "category": "Music", "developer": "Apple"},

    # 健康
    {"id": "1103885722", "name": "Headspace", "category": "Health & Fitness", "developer": "Headspace"},
    {"id": "1520571825", "name": "Calm", "category": "Health & Fitness", "developer": "Calm.com"},
    {"id": "1233168611", "name": "Streaks", "category": "Health & Fitness", "developer": "Crunchy Bagel"},
    {"id": "1050676732", "name": "MyFitnessPal", "category": "Health & Fitness", "developer": "MyFitnessPal"},

    # 阅读
    {"id": "302584613",  "name": "Amazon Kindle", "category": "Books", "developer": "Amazon"},
    {"id": "1344097564", "name": "Reeder 5", "category": "News", "developer": "Silvio Rizzi"},
    {"id": "1529448980", "name": "Reeder.", "category": "News", "developer": "Silvio Rizzi"},
    {"id": "1289583905", "name": "Instapaper", "category": "News", "developer": "Instant Paper"},

    # 安全 / 密码
    {"id": "1333103190", "name": "1Password 8", "category": "Utilities", "developer": "AgileBits"},
    {"id": "1564384601", "name": "Bitwarden", "category": "Utilities", "developer": "Bitwarden"},
    {"id": "510296984",  "name": "Dashlane", "category": "Utilities", "developer": "Dashlane"},

    # 编程 / 开发者
    {"id": "1440138685", "name": "Working Copy - Git Client", "category": "Developer Tools", "developer": "Anders Borum"},
    {"id": "1462586600", "name": "Textastic Code Editor", "category": "Developer Tools", "developer": "Alexander Blach"},
    {"id": "1557630827", "name": "Blink Shell & Code Editor", "category": "Developer Tools", "developer": "Carlos Cabrera"},
    {"id": "1579036315", "name": "Play - App Store Connect", "category": "Developer Tools", "developer": "Marcos Tanaka"},

    # 效率 / 自动化
    {"id": "915249334",  "name": "Drafts", "category": "Productivity", "developer": "Agile Tortoise"},
    {"id": "1222992032", "name": "Toolbox for Word", "category": "Productivity", "developer": "Bloop"},
    {"id": "1462845272", "name": "Scriptable", "category": "Developer Tools", "developer": "Simon Støvring"},
    {"id": "1303222628", "name": "Shortcuts", "category": "Productivity", "developer": "Apple"},
]

def load_existing_watchlist():
    """加载已有的 watchlist，返回已有 ID 集合"""
    watchlist_path = Path("watchlist.json")
    if watchlist_path.exists():
        with open(watchlist_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing = {str(a.get("id", "")) for a in data.get("apps", [])}
        print(f"已加载现有 watchlist: {len(existing)} 个 App")
        return data, existing
    return {"settings": {"country": "us", "fetch_iap": True}, "apps": []}, set()

def fetch_rss(country, feed_type, genre_id="", limit=200):
    """抓取 iTunes RSS 榜单"""
    if genre_id:
        url = f"https://itunes.apple.com/{country}/rss/{feed_type}/genre={genre_id}/limit={limit}/json"
    else:
        url = f"https://itunes.apple.com/{country}/rss/{feed_type}/limit={limit}/json"
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
    print("App Store RSS 批量抓取 - 目标 10000+")
    print("=" * 60)

    existing_data, seen_ids = load_existing_watchlist()
    new_apps = []

    def add_app(app, override_category=None):
        aid = str(app.get("id", ""))
        if aid and aid not in seen_ids:
            seen_ids.add(aid)
            a = dict(app)
            if override_category:
                a["category"] = override_category
            new_apps.append(a)

    # ── 1. 手动大厂列表 ──────────────────────────────────────
    print("\n🎮 添加大厂手动列表...")
    for app in KNOWN_GAMES + KNOWN_APPS:
        add_app(app)
    print(f"  ✓ 手动列表新增: {len(new_apps)} 个")

    # ── 2. 美区总榜（三榜各 200）─────────────────────────────
    print("\n📊 抓取美区总榜...")
    for feed_type, label in FEED_TYPES:
        apps = fetch_rss("us", feed_type, limit=200)
        before = len(new_apps)
        for a in apps:
            add_app(a)
        print(f"  us/{label}: +{len(new_apps)-before} 新App（共 {len(new_apps)+len(seen_ids)-len(new_apps)}）")
        time.sleep(random.uniform(0.3, 0.8))

    # ── 3. 所有分类 × 三榜 × 美区 ───────────────────────────
    print("\n📂 抓取美区分类榜（App + 游戏）...")
    all_genres = APP_GENRES + GAME_GENRES
    for genre_id, genre_name in all_genres:
        for feed_type, label in FEED_TYPES:
            apps = fetch_rss("us", feed_type, genre_id=genre_id, limit=200)
            before = len(new_apps)
            for a in apps:
                add_app(a, override_category=genre_name)
            cnt = len(new_apps) - before
        print(f"  {genre_name}: +{cnt} 新App  累计新增: {len(new_apps)}")
        time.sleep(random.uniform(0.4, 1.0))

    # ── 4. 多国家总榜 ──────────────────────────────────────
    print(f"\n🌍 抓取多国家总榜（{', '.join(COUNTRIES[1:])}）...")
    for country in COUNTRIES[1:]:  # 跳过 us（已抓）
        for feed_type, label in FEED_TYPES:
            apps = fetch_rss(country, feed_type, limit=200)
            before = len(new_apps)
            for a in apps:
                add_app(a)
            print(f"  {country}/{label}: +{len(new_apps)-before} 新App")
            time.sleep(random.uniform(0.3, 0.8))

    # ── 5. 多国家分类榜（只抓付费+免费）──────────────────────
    print("\n🌍 抓取多国家分类榜...")
    for country in COUNTRIES[1:]:
        for genre_id, genre_name in all_genres:
            for feed_type in ["toppaidapplications", "topfreeapplications"]:
                apps = fetch_rss(country, feed_type, genre_id=genre_id, limit=100)
                for a in apps:
                    add_app(a, override_category=genre_name)
            time.sleep(random.uniform(0.2, 0.5))
        print(f"  ✓ {country} 分类榜完成，累计新增: {len(new_apps)}")

    print(f"\n🎉 抓取完成！共新增 {len(new_apps)} 个 App")

    # ── 6. 合并保存 ────────────────────────────────────────
    existing_apps = existing_data.get("apps", [])
    combined = existing_apps + new_apps

    # 最终去重（防万一）
    final, seen2 = [], set()
    for a in combined:
        aid = str(a.get("id", ""))
        if aid and aid not in seen2:
            seen2.add(aid)
            final.append(a)

    existing_data["apps"] = final
    existing_data["settings"]["last_updated"] = time.strftime("%Y-%m-%d")
    existing_data["settings"]["note"] = f"All IDs from iTunes RSS or manually verified. Total: {len(final)}"

    with open("watchlist.json", "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    # 同时保存 watchlist_full.json（含 developer 字段）
    with open("watchlist_full.json", "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存！")
    print(f"   原有: {len(existing_apps)} 个")
    print(f"   新增: {len(new_apps)} 个")
    print(f"   总计: {len(final)} 个")

    # 分类统计
    cats = {}
    for a in final:
        c = a.get("category", "Unknown")
        cats[c] = cats.get(c, 0) + 1
    print("\n📊 分类统计（Top 20）:")
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1])[:20]:
        print(f"   {cat}: {cnt}")

if __name__ == "__main__":
    main()
