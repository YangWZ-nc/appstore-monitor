# 🍎 App Store 美区价格监控系统

> **完全免费 · 24小时无人值守 · 基于 GitHub Actions**  
> 自动监控 App 本体价格 + 内购价格，降价立即推送到手机。

[![Monitor](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/monitor.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/monitor.yml)

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 🔍 本体价格监控 | 检测 App 本体降价或限免 |
| 💰 内购价格监控 | 检测内购项目价格下降 |
| 📲 Bark 推送 | iOS 免费推送，秒到 |
| 🤖 Telegram 推送 | 备选推送方案 |
| 🌐 价格展示页面 | 自动生成 GitHub Pages 展示页 |
| ⏰ 定时运行 | 每 6 小时自动检查一次 |
| 🛡️ 高容错设计 | 单个 App 失败不影响整体 |

---

## 📁 项目结构

```
.
├── .github/
│   └── workflows/
│       └── monitor.yml      # GitHub Actions 定时工作流
├── main.py                  # 核心监控脚本
├── requirements.txt         # Python 依赖
├── watchlist.json           # 【你需要编辑】监控的 App 列表
├── history_prices.json      # 自动维护的价格历史（首次运行后生成）
└── index.html               # 自动生成的价格展示页（首次运行后生成）
```

---

## 🚀 小白部署指南（一步步来）

### 第一步：创建 GitHub 仓库

1. 打开 [github.com](https://github.com)，登录或注册账号。
2. 点击右上角 **"+"** → **"New repository"**。
3. 填写仓库名，例如 `appstore-monitor`。
4. 选择 **Public**（Public 才能使用免费的 GitHub Pages）。
5. **不要**勾选 "Add a README file"（我们自己上传文件）。
6. 点击 **"Create repository"**。

---

### 第二步：上传项目文件

**方法 A（推荐，使用 Git）：**

```bash
# 在本地项目目录执行
git init
git add .
git commit -m "init: App Store price monitor"
git branch -M main
git remote add origin https://github.com/你的用户名/appstore-monitor.git
git push -u origin main
```

**方法 B（网页直接上传）：**

1. 在仓库页面点击 **"uploading an existing file"**。
2. 把 `main.py`、`requirements.txt`、`watchlist.json` 三个文件拖进去。
3. 点击 **"Commit changes"**。
4. 然后创建 `.github/workflows/` 目录并上传 `monitor.yml`（注意层级）。

---

### 第三步：编辑你的监控列表

打开仓库中的 `watchlist.json`，把 App ID 替换成你想监控的应用。

**如何找到 App ID？**  
- 在 App Store 中找到目标 App，复制网页链接。
- 链接格式：`https://apps.apple.com/us/app/shadowrocket/id932747118`
- 其中 `id` 后面的数字（如 `932747118`）就是 App ID。

```json
{
  "apps": [
    { "id": "932747118", "name": "Shadowrocket" },
    { "id": "1107421413", "name": "Darkroom" },
    { "id": "你的AppID", "name": "备注名称（可以写中文）" }
  ],
  "settings": {
    "country": "us"
  }
}
```

---

### 第四步：设置推送通知（二选一）

> ⚠️ **重要**：密钥不能直接写在代码里！必须通过 GitHub Secrets 配置。

**进入 Secrets 设置页面：**  
仓库页面 → **Settings** → 左侧 **"Secrets and variables"** → **"Actions"** → 点击 **"New repository secret"**

---

#### 方案 A：Bark（推荐，iPhone 用户首选）

1. 在 App Store 搜索 **"Bark"** 并安装（免费）。
2. 打开 Bark App，复制首页显示的**设备 Key**（一串字符）。
3. 在 GitHub Secrets 中添加：

| Secret 名称 | 值 |
|------------|-----|
| `BARK_KEY` | 你的设备 Key（例如：`aBcDeFgHiJkLmN`） |
| `BARK_SERVER` | `https://api.day.app`（默认，可不填）|

---

#### 方案 B：Telegram Bot

1. 在 Telegram 中搜索 **@BotFather**，发送 `/newbot` 创建机器人。
2. 按提示设置机器人名字，获得 **Bot Token**（格式：`123456:ABCdefGHIjklMNO`）。
3. 搜索你的机器人并发送任意消息。
4. 访问 `https://api.telegram.org/bot你的Token/getUpdates`，在返回的 JSON 中找到 `chat.id`。
5. 在 GitHub Secrets 中添加：

| Secret 名称 | 值 |
|------------|-----|
| `TELEGRAM_BOT_TOKEN` | 你的 Bot Token |
| `TELEGRAM_CHAT_ID` | 你的 Chat ID（可能是负数，如 `-100xxxxxx`） |

---

### 第五步：开启 GitHub Actions

1. 进入仓库 → 点击顶部 **"Actions"** 标签。
2. 如果看到提示，点击 **"I understand my workflows, go ahead and enable them"**。
3. 在左侧找到 **"App Store Price Monitor"**，点击 **"Run workflow"** → **"Run workflow"** 手动触发一次，验证是否正常运行。
4. 查看运行日志，确认没有报错。

**运行成功后，你会在仓库中看到自动生成的 `history_prices.json` 和 `index.html` 文件。**

---

### 第六步：开启 GitHub Pages（可选，展示价格页面）

1. 进入仓库 → **Settings** → 左侧 **"Pages"**。
2. **Source** 选择 **"Deploy from a branch"**。
3. **Branch** 选择 **"main"**，目录选择 **"/ (root)"**。
4. 点击 **"Save"**。
5. 等待约 1 分钟，页面链接会显示在 Settings → Pages 顶部。
6. 链接格式：`https://你的用户名.github.io/appstore-monitor/`

> 每次 Actions 运行后会自动 push `index.html`，Pages 会自动更新。

---

## 📱 推送通知样式预览

**降价通知示例：**
```
💸 降价 40%！Shadowrocket
App 本体: App 本体
原价：USD $2.99  →  现价：$1.99（↓33%）
🔗 https://apps.apple.com/us/app/id932747118
```

**限免通知示例：**
```
🎉 限免！Darkroom
App 本体 现在免费！
原价：USD $4.99
快去下载 👉 https://apps.apple.com/us/app/id1107421413
```

---

## ⚙️ 常见问题

**Q：Actions 报错 "Process completed with exit code 1"？**  
A：点击具体的 step 查看日志。常见原因：`watchlist.json` 格式有误，或网络超时（重新触发即可）。

**Q：没有收到推送？**  
A：检查 Secrets 是否填写正确（注意没有多余空格），以及 Bark App 是否开启了通知权限。

**Q：想改变监控频率？**  
A：编辑 `monitor.yml` 中的 `cron` 表达式。例如每3小时：`0 */3 * * *`。

**Q：能同时使用 Bark 和 Telegram 吗？**  
A：可以！把两组 Secrets 都填上，两个推送会同时发送。

**Q：GitHub Actions 免费额度够用吗？**  
A：公开仓库 Actions 完全免费，无额度限制。每次运行约耗时 1-3 分钟。

---

## 📋 运行日志示例

```
2026-03-25 06:00:01 [INFO] ============================================================
2026-03-25 06:00:01 [INFO] App Store 价格监控 启动
2026-03-25 06:00:01 [INFO] 运行时间: 2026-03-25 06:00:01 UTC
2026-03-25 06:00:01 [INFO] ============================================================
2026-03-25 06:00:01 [INFO] 共监控 3 个 App，地区：US
2026-03-25 06:00:02 [INFO] [1/3] 正在处理 App ID: 932747118
2026-03-25 06:00:03 [INFO]   App: Shadowrocket  价格: $2.99
2026-03-25 06:00:06 [INFO]   [JSON-LD] 找到 3 个内购项目
2026-03-25 06:00:07 [INFO] [2/3] 正在处理 App ID: 1107421413
...
2026-03-25 06:02:15 [INFO] 未检测到降价，无需推送。
2026-03-25 06:02:16 [INFO] 已保存: history_prices.json
2026-03-25 06:02:16 [INFO] 已生成静态页面: index.html
2026-03-25 06:02:16 [INFO] 监控完成！处理 3 个 App，触发 0 条通知。
```

---

## 📄 License

MIT License · 仅供学习和个人使用
