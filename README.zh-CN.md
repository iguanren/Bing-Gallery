[English](README.md) | **中文简体**

# Bing Gallery（4K 高清美图壁纸画廊）

> 一个安静的必应每日壁纸画廊 —— 4K、无水印、全量归档。

[![壁纸数据自动更新](https://github.com/iguanren/Bing-Gallery/actions/workflows/wallpaper.yml/badge.svg)](https://github.com/iguanren/Bing-Gallery/actions/workflows/wallpaper.yml)
[![归档壁纸](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Figuanren%2FBing-Gallery%40main%2Fdata.json&query=%24.count&label=%E5%BD%92%E6%A1%A3%E5%A3%81%E7%BA%B8&color=orange&maxAge=3600)](https://iguanren.eu.org/)
[![演示网站](https://img.shields.io/badge/%E6%BC%94%E7%A4%BA%E7%BD%91%E7%AB%99-iguanren.eu.org-brightgreen)](https://iguanren.eu.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

![今日必应壁纸](https://cn.bing.com/th?id=OHR.FrenchRivieraVillage_ZH-CN2888811422_1920x1080.jpg)

必应每天都会放出一张官方高清壁纸，第二天却悄悄换掉。本项目做的事很简单：把它们留下来。

首屏今日大图 · 卡片流 + 4K 灯箱 · 历史按月归档 · 纯静态站点、零图片存储（图片热链必应官方 CDN）。

🔗 **演示站点**：[iguanren.eu.org](https://iguanren.eu.org/) · [About](https://iguanren.eu.org/about.html)

---

## 📖 由来

这个项目源于一个老习惯。以前做博客的时候，我喜欢拿必应每日壁纸当网页背景 —— 但必应第二天就会把它换掉，想再找就很麻烦。于是我决定把它们收集起来、归档存好，闲暇时还能翻出来品鉴一番。

## ✨ 功能

- **每日自动更新** — GitHub Actions 每日 3 次抓取 15 个市场，每次同步做全量链接体检；失效的图自动补位，不会出现数据丢失
- **首屏整屏大图** — 今日壁纸铺满首屏，国区优先、美区兜底
- **卡片流 + 灯箱** — 最近 30 张壁纸，点击预览 4K 原图，键盘或点击屏幕两侧翻页
- **历史归档** — 点 Archive 按月份浏览，数据全量留存、永不删除
- **双语 About 页** — 中英一键切换，不刷新
- **体验细节** — 夜间模式、移动端整屏适配（含 iPhone 安全区）、SEO 全套

## 🚀 快速开始

纯静态站点，无需构建。

```bash
pip install requests
python3 scripts/fetch_bing.py        # 抓取 + 更新 data.json
python3 -m http.server 8899          # 本地预览 http://localhost:8899
```

## 📦 部署

EdgeOne Pages 连接仓库、绑定域名即用。

---

## 📄 许可与免责

**源码**采用 [MIT 协议](LICENSE) 开源 —— 欢迎学习、修改、部署，商用也没有问题。

**数据与图片另当别论** —— MIT 协议仅适用于本项目的**源码**，不覆盖采集到的壁纸数据。壁纸数据来自必应（Bing）官方接口，图片热链官方 CDN，版权归 **Microsoft / 必应 / 原作者** 所有，本项目仅供个人收藏与展示。

> ⚠️ **任何人若将采集到的壁纸数据用于商业场景**（如搭建收费壁纸站、二次分发、嵌入商业产品等），**须自行获得版权方的合法授权，并自行承担由此产生的全部法律责任，与本项目作者无关。**

> ℹ️ 由于维护升级过程中部分数据丢失，最新数据从 2026 年 8 月开始重新抓取并进行归档。

## 💬 反馈

有建议欢迎开 [GitHub Issue](https://github.com/iguanren/Bing-Gallery/issues)。
