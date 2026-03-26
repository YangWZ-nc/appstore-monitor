# 🍎 App Store 美区价格监控

> 自动监控 **4864+ 个 App** 的价格变动，降价/限免时第一时间推送通知。

[![Monitor](https://github.com/YangWZ-nc/appstore-monitor/actions/workflows/monitor.yml/badge.svg)](https://github.com/YangWZ-nc/appstore-monitor/actions/workflows/monitor.yml)

🌐 **在线价格页面**: https://yangwz-nc.github.io/appstore-monitor/

---

## 这是什么？

这是一个**完全免费**的 App Store 价格监控工具，基于 GitHub Actions 自动运行，无需服务器。

**它能做什么：**
- 🔍 监控 App **本体价格**（降价、限免）
- 💰 监控 **内购价格**（订阅、道具、解锁包）
- 📲 降价时**自动推送到手机**（Bark / Telegram）
- 🌐 生成**在线价格页面**，随时查看历史价格

---

## 监控范围

| 项目 | 数量 |
|------|------|
| 监控 App | **4,864 个** |
| 覆盖分类 | 游戏、生产力、摄影、教育、健康、财务等 25+ 类 |
| 更新频率 | 每晚一次（分批轮询，10 天完成一轮） |
| 数据来源 | App Store 美区排行榜 |

**包含热门应用如：**
- 游戏：Minecraft、Terraria、Stardew Valley、Dead Cells、Slay the Spire
- 生产力：Notability、GoodNotes、Things 3、OmniFocus
- 摄影：Darkroom、Procreate、LumaFusion
- 工具：Shadowrocket、Surge、1Password

---

## 如何使用？

### 1. 查看价格页面
直接访问 https://yangwz-nc.github.io/appstore-monitor/ 查看当前价格和历史趋势。

### 2. 获取降价通知（可选）
如果你想在自己的仓库运行并接收推送：

#### ① Fork 本仓库
点击右上角 **Fork** 按钮，复制到你自己的 GitHub 账号。

#### ② 配置推送通知
进入你 Fork 的仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

**方案 A：Bark（iPhone 推荐）**
| Secret 名称 | 值 |
|------------|-----|
| `BARK_KEY` | 从 Bark App 获取的设备 Key |

**方案 B：Telegram**
| Secret 名称 | 值 |
|------------|-----|
| `TELEGRAM_BOT_TOKEN` | 你的 Bot Token |
| `TELEGRAM_CHAT_ID` | 你的 Chat ID |

#### ③ 开启 GitHub Actions
进入 **Actions** 标签页 → 点击 **"I understand..."** 启用。

#### ④ 开启 GitHub Pages（查看价格页面）
进入 **Settings** → **Pages** → Source 选择 **"Deploy from a branch"** → Branch 选 **"main"** → 点击 **Save**

等待 1-2 分钟，访问 `https://你的用户名.github.io/appstore-monitor/`

---

## 项目结构

```
├── .github/workflows/monitor.yml   # 定时任务配置
├── main.py                         # 核心监控脚本
├── fetch_app_store_rss.py          # 抓取 App Store 排行榜
├── watchlist.json                  # 监控列表（4864 个 App）
├── history_prices.json             # 价格历史数据
├── monitor_progress.json           # 分批处理进度
└── index.html                      # 自动生成的价格展示页
```

---

## 常见问题

**Q：为什么价格页面只显示部分 App？**  
A：正常。4864 个 App 采用分批处理，每晚更新 500 个，约 10 天完成一轮完整扫描。

**Q：能监控国区 App Store 吗？**  
A：可以。修改 `watchlist.json` 中的 `"country": "us"` 为 `"cn"` 即可。

**Q：能添加自己想监控的 App 吗？**  
A：可以。编辑 `watchlist.json`，按格式添加 App ID 和名称。

**Q：推送是实时的吗？**  
A：每晚运行一次。如需更频繁，可修改 `.github/workflows/monitor.yml` 中的 `cron` 表达式。

**Q：运行这个要花多少钱？**  
A：完全免费。GitHub Actions 对公开仓库无限制。

---

## 技术细节

- **定时运行**: GitHub Actions（`0 2 * * *`，北京时间每天 10:00）
- **分批策略**: 每批 500 个 App，避免超时
- **价格来源**: iTunes API + App Store 网页解析
- **数据存储**: Git 仓库（`history_prices.json`）

---

## License

MIT License · 仅供学习和个人使用
