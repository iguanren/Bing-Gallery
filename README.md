**English** | [中文简体](README.zh-CN.md)

# Bing Gallery

> A personal gallery of Bing's daily wallpapers — 4K, watermark-free, fully archived.

[![Wallpaper data auto-update](https://github.com/iguanren/Bing-Gallery/actions/workflows/wallpaper.yml/badge.svg)](https://github.com/iguanren/Bing-Gallery/actions/workflows/wallpaper.yml)
[![Archived wallpapers](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Figuanren%2FBing-Gallery%40main%2Fdata.json&query=%24.count&label=Archived&color=orange&maxAge=3600)](https://iguanren.eu.org/)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-iguanren.eu.org-brightgreen)](https://iguanren.eu.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

![Today's Bing wallpaper](https://cn.bing.com/th?id=OHR.FrenchRivieraVillage_ZH-CN2888811422_1920x1080.jpg)

Bing releases a different official HD wallpaper every day, then quietly swaps it out the next. This project does one simple thing: keeps them.

Today's pick on a full-screen hero · card flow with a 4K lightbox · full monthly archive · pure static site with zero image storage (all images hotlinked from Bing's official CDN).

🔗 **Live demo**: [iguanren.eu.org](https://iguanren.eu.org/) · [About](https://iguanren.eu.org/about.html)

---

## 📖 Background

This project grew out of an old habit. Back when I was running a blog, I liked using Bing's daily wallpapers as page backgrounds — but Bing swaps each one out the next day, which makes them a pain to find again. So I decided to collect them, archive them properly, and keep them around for a quiet browse now and then.

## ✨ Features

- **Daily auto-update** — GitHub Actions pulls from 15 markets three times a day and runs a full link health check each time; dead images are replaced automatically, so nothing gets lost
- **Full-screen hero** — today's wallpaper fills the first screen, China region first with US fallback
- **Card flow + lightbox** — the 30 most recent wallpapers; click for a 4K preview, flip with the arrow keys or by tapping the screen edges
- **Monthly archive** — hit Archive to browse by month; everything is kept in full and never deleted
- **Fully bilingual** — English / 中文 across the whole site: nav, filter bar, archive, footer and the About page, switched instantly with no reload
- **Genuinely English content** — in English mode, wallpaper titles and copyright lines come from Bing's English-market data for the *same* image (matched by image fingerprint), not machine translation
- **The details** — night mode, mobile full-screen adaptation (incl. iPhone safe area), full SEO setup

## 🗂 Project Structure

No build step — plain static files, split by responsibility:

```
index.html              main page (markup + SEO meta; all logic lives in the JS files)
about.html              About page
style.css               all styles for both pages
site.js                 shared logic: language / night mode / floating buttons / uptime
gallery.js              main page: data loading, card flow, monthly archive, lightbox
about.js                About page: today's wallpaper, bilingual captions
data.json               all wallpaper data (auto-generated)
scripts/fetch_bing.py   daily fetch + link health check
.github/workflows/      scheduled auto-update
```

## 🚀 Quick Start

Pure static site — no build step required.

```bash
pip install requests
python3 scripts/fetch_bing.py        # fetch + update data.json
python3 -m http.server 8899          # preview at http://localhost:8899
```

## 📦 Deployment

Connect the repository to EdgeOne Pages, bind your domain, and you're done.

---

## 📄 License & Disclaimer

**Source code** is released under the [MIT License](LICENSE) — free to learn from, modify, deploy, and even use commercially.

**Data and images are a different matter** — the MIT License covers the **source code only**, not the wallpaper data. Wallpaper data is collected from Bing's official API and the images are hotlinked from Bing's official CDN. Copyright belongs to **Microsoft / Bing / their original authors**. This project is for personal collection and display only.

> ⚠️ **Anyone using the collected wallpaper data for commercial purposes** (building a paid wallpaper service, redistributing the images, embedding them in commercial products, etc.) **must obtain authorization from the copyright holders, and bears full legal responsibility for their own actions. The author of this project assumes no liability whatsoever.**

> ℹ️ Some data was lost during a maintenance upgrade; the latest data has been re-scraped and archived since August 2026.

## 💬 Feedback

Suggestions are welcome — open a [GitHub Issue](https://github.com/iguanren/Bing-Gallery/issues).
