# Kindle 出门看板（方案 A）

把 **Kindle Paperwhite 第 10 代** 变成常亮的日历看板：在 Mac「日历」里改日程 → 云端自动出图 → Kindle 定时拉取更新。**Mac 关机不影响当前画面，也不影响后续刷新**（只要 GitHub Actions 与 Kindle Wi‑Fi 可用）。

适用设备：Paperwhite 10（PW4），固件 **5.18.1.1.1** → 使用 **[SpringBreak](https://kindlemodding.org/jailbreaking/SpringBreak/)** 越狱（不是 AdBreak）。

---

## 整体怎么工作

```
Mac / iPhone「日历」改日程
        ↓ iCloud
公开 ICS 链接（密钥型 URL）
        ↓ 每 ~20 分钟
GitHub Actions 渲染 dashboard.png → GitHub Pages
        ↓ Kindle Wi‑Fi
越狱脚本下载 PNG，全屏显示，并禁止屏保
```

## 1. 准备 Apple 日历 ICS 链接

1. 打开 Mac 上的 **日历**。
2. 在左侧右键要点展示的日历 → **共享日历…** / **信息公开**。
3. 勾选 **公共日历**，复制链接。
4. 把开头的 `webcal://` 改成 `https://`。

得到类似：

`https://pXX-calendars.icloud.com/published/2/长串字符`

注意：

- 任何拿到该链接的人都能读日程，请当作密码保管，**不要写进代码仓库**。
- 多个日历：把多条 `https://…` 用英文逗号拼成一条即可。
- 改完日历后，iCloud 同步到公开 ICS 可能有几分钟延迟。

本地预览（可选）：

```bash
cd /Users/jonathan/Desktop/Kindle
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 CALENDAR_ICS_URL
export $(grep -v '^#' .env | xargs)
python render_dashboard.py
open output/dashboard.png
```

## 2. 推到 GitHub（源码私有）

日历链接只放在 GitHub **Secret** 里，不会进代码。

**注意：** 免费账号的**私有仓库不能用 GitHub Pages**。Kindle 必须能匿名下载 PNG，所以常见做法是：

- 源码仓库 **private**（本项目）
- 另建一个 **public** 仓库只用来挂 `dashboard.png`（不含日历链接）

若你接受「代码公开、日历仍保密」，把仓库改成 public 并开启 Pages 最简单。

设置 Secret：

1. 仓库 **Settings → Secrets and variables → Actions**
2. 新增 `CALENDAR_ICS_URL`，值为日历的 `https://…` ICS 地址（不要提交到 git）
3. **Settings → Pages** → Source 选 **GitHub Actions**（仅 public 或付费账号的 private 可用）
4. 打开 **Actions**，手动跑 **Render Kindle Dashboard**
5. 图片地址一般为：`https://<用户名>.github.io/<仓库名>/dashboard.png`

## 3. 越狱 Kindle（SpringBreak）

固件必须是 **5.18.1.1.1**，机型为 PW4 / 部分 KT4 等（以 [KindleModding 向导](https://kindlemodding.org/) 为准）。

简要步骤（细节以官网为准）：

1. **飞行模式 → 重启** Kindle。
2. USB 连上 Mac，按官网用 SpringBreak 写入填充文件（Mac 可用官网一键命令）。
3. 拔掉后点主页 **商店**，按提示关飞行模式；出现越狱成功界面。
4. 再插上 USB，再跑一遍 SpringBreak 做 **清理**（否则开机极慢）。
5. 按 [What's Next](https://kindlemodding.org/jailbreaking/post-jailbreak/) 安装 **hotfix**，并装上 **kterm**（终端）。
6. 删除 Kindle 根目录里可能存在的固件 `.bin`，避免被更新冲掉环境。

官方指南：https://kindlemodding.org/jailbreaking/SpringBreak/

## 4. 在 Kindle 上常亮显示

1. USB 连接后，在 Kindle 盘符创建目录 `dashboard`。
2. 复制本仓库 `kindle/run.sh` 到 `/mnt/us/dashboard/run.sh`（即盘符下的 `dashboard/run.sh`）。
3. 用电脑编辑 `run.sh` 顶部的 `IMAGE_URL`，改成你的 Pages PNG 地址。
4. 在 Kindle 打开 **kterm**，执行：

```sh
sh /mnt/us/dashboard/run.sh
```

脚本会：

- `preventScreenSaver` + `TESTD_PREVENT_SCREENSAVER` 尽量禁止息屏/屏保  
- 立刻下载并 `eips` 全屏显示  
- 默认每 20 分钟再拉一次；失败则保留当前墨水画面  

插电放置更省心。Wi‑Fi 越频繁，越耗电。

自启（可选）：越狱后可用 launchpad / KUAL 在开机后执行 `kindle/autostart.sh`；建议先手动跑通再配置自启。

## 5. 日常使用

| 你做什么 | 会发生什么 |
|----------|------------|
| 在 Mac/iPhone 改日历 | iCloud 更新 → Actions 出新图 → Kindle 下次拉取后换画面 |
| Mac 关机 | 看板继续显示；云端仍按计划出图；Kindle 仍可刷新 |
| Kindle 暂时没网 | 墨水屏保留最后一帧 |

## 目录说明

| 路径 | 作用 |
|------|------|
| `render_dashboard.py` | 拉 ICS，画成 1072×1448 灰度 PNG（PW4） |
| `.github/workflows/render.yml` | 定时渲染并发布到 GitHub Pages |
| `kindle/run.sh` | Kindle 拉图 + 防息屏循环 |
| `.env.example` | 本地调试用的环境变量模板 |

## 常见问题

**日程不更新？**  
检查 ICS 是否在浏览器能打开；Actions 是否成功；Kindle `dashboard.log`；Pages 上 PNG 的修改时间。

**只有英文/方框字？**  
云端 workflow 已装 Noto CJK。本地预览请确保系统有苹方 / 黑体等中文字体。

**屏保又出来了？**  
确认 `run.sh` 仍在跑；重启后需重新执行脚本；检查是否存在 `/mnt/us/TESTD_PREVENT_SCREENSAVER`。

**不想公开仓库？**  
仓库可私有；GitHub Pages 对私有仓有账号计划限制。也可改成 Cloudflare R2 / 其他静态托管，只需改 `IMAGE_URL` 与 workflow 上传步骤。
