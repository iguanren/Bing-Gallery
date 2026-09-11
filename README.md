# Bing Gallery（4K 高清美图壁纸画廊）

[![壁纸数据自动更新](https://github.com/iguanren/Bing-Gallery/actions/workflows/wallpaper.yml/badge.svg)](https://github.com/iguanren/Bing-Gallery/actions/workflows/wallpaper.yml)
[![归档壁纸](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Figuanren%2FBing-Gallery%40main%2Fdata.json&query=%24.count&label=%E5%BD%92%E6%A1%A3%E5%A3%81%E7%BA%B8&color=orange&maxAge=3600)](https://iguanren.eu.org/)
[![演示网站](https://img.shields.io/badge/%E6%BC%94%E7%A4%BA%E7%BD%91%E7%AB%99-iguanren.eu.org-brightgreen)](https://iguanren.eu.org/)

每日自动收录必应（Bing）官方每日高清美图，4K 超清无水印免费下载，历史壁纸按月归档一键回看。纯静态站点、零图片存储（图片热链必应官方 CDN），主站 [iguanren.eu.org](https://iguanren.eu.org/)。

## 功能

- **每日自动更新**：GitHub Actions 每日 3 次抓取 15 个市场，自动合并归档
- **首屏整屏大图**：今日壁纸铺满首屏，版权信息悬浮图内底部
- **卡片流 + 灯箱**：近 30 天壁纸卡片流，点击预览 4K 原图，支持键盘翻页
- **历史归档**：按月浏览，数据全量留存、永不删除
- **体验细节**：夜间模式、移动端整屏适配（含 iPhone 安全区）、SEO 全套

## 本地调试

```bash
pip install requests
python3 scripts/fetch_bing.py        # 抓取 + 更新 data.json
python3 -m http.server 8899          # 本地预览 http://localhost:8899
```

## 部署

纯静态站点，无构建：EdgeOne Pages 连接仓库、绑定域名即用（本站：iguanren.eu.org）。

## 数据与版权

壁纸数据来自 [Bing 官方接口](https://www.bing.com/HPImageArchive.aspx)，图片热链官方 CDN，版权归 **Microsoft / 必应** 所有，仅供个人收藏展示，请勿商用。
