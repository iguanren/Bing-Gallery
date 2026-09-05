#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iguanren.eu.org 壁纸数据生成脚本（纯自抓，仅依赖 requests）
===========================================================
- 端点：global.bing.com（国际版，中国 IP 也能拿到全球市场数据）
- 市场：全球 15 个市场全抓，每天出多少抓多少（idx=0..7，最近 8 天）
- 每条记录带 region 字段（国家码），非中区图在前端显示市场标签
- 合并进 data.json，按"日期+市场"去重，全量归档（永不删除，无限攒数据）
- 图片全部热链 cn.bing.com（缩略图 _400x240 / 4K _UHD），本站零图片存储
- 由 GitHub Actions 每日定时执行

市场权重：排序时中区最前、美区次之，保证 items[0] 是中区最新图
（前端首屏背景逻辑：当日中区 → 当日美区 → 最新一条）

用法：
    python3 scripts/fetch_bing.py              # 抓取并更新 data.json
    python3 scripts/fetch_bing.py --dry-run    # 只打印结果不写文件
依赖：requests（pip install requests）
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

BING_API = "https://global.bing.com/HPImageArchive.aspx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
IDX_RANGE = range(0, 8)  # 每市场每次抓最近 8 天（idx=0 今天 … idx=7 八天前）
SLEEP = 0.35             # 请求间隔，避免频率限制（15 市场 × 8 天 = 120 请求/轮）
BJ_TZ = timezone(timedelta(hours=8))   # 北京时间（GitHub runner 是 UTC，必须显式转换）

# 全球市场清单：能抓到的都抓；权重越小排序越靠前
# 实测部分市场（en-AU/zh-TW/ko-KR/ru-RU/ar-SA）title 返回 "Info" 占位，照抓不误，前端兜底
MARKETS = [
    ("zh-CN", 0),   # 中国（本站主市场，权重最高）
    ("en-US", 1),   # 美国（中区空窗时的首屏兜底）
    ("en-GB", 2), ("ja-JP", 3), ("de-DE", 4), ("fr-FR", 5), ("en-IN", 6),
    ("it-IT", 7), ("es-ES", 8), ("pt-BR", 9), ("en-AU", 10), ("zh-TW", 11),
    ("ko-KR", 12), ("ru-RU", 13), ("ar-SA", 14),
]
# 权重表键必须是短码（CN/US/BR...）：数据里 region = mkt.split("-")[-1] 是短码，
# 若直接 dict(MARKETS) 用全码（zh-CN）做键，get(region) 永远 miss、权重全 fallback 99，
# 同日期排序退化成"文件原有顺序"（2026-09-01 BR 顶到 CN 前的根因）
MARKET_WEIGHT = {code.split("-")[-1]: w for code, w in MARKETS}


def fetch_day(mkt: str, idx: int) -> dict | None:
    """抓取指定市场指定 idx 的必应壁纸信息，失败返回 None"""
    url = f"{BING_API}?format=js&idx={idx}&n=1&mkt={mkt}"
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        if resp.status_code != 200:
            print(f"  {mkt} idx={idx}: HTTP {resp.status_code}", file=sys.stderr)
            return None
        images = resp.json().get("images") or []
        if not images:
            print(f"  {mkt} idx={idx}: 接口返回空 images", file=sys.stderr)
            return None
        img = images[0]
        # enddate 是必应的展示日期，用它做日期键
        date = img.get("enddate", "")
        if len(date) != 8 or not date.isdigit():
            print(f"  {mkt} idx={idx}: enddate 异常 {date!r}，跳过", file=sys.stderr)
            return None
        urlbase = img.get("urlbase", "")  # 形如 /th?id=OHR.xxx_EN-US123
        if not urlbase:
            print(f"  {mkt} idx={idx}: urlbase 为空，跳过", file=sys.stderr)
            return None
        region = mkt.split("-")[-1]  # en-US -> US, zh-CN -> CN
        return {
            "date": date,
            "region": region,
            "dateLabel": _fmt_date(date),
            "title": img.get("title", ""),
            "copyright": img.get("copyright", ""),
            "copyrightlink": img.get("copyrightlink", ""),
            "urlbase": urlbase,
            "thumb": f"https://cn.bing.com{urlbase}_400x240.jpg",
            "full": f"https://cn.bing.com{urlbase}_UHD.jpg",
        }
    except Exception as e:
        print(f"  {mkt} idx={idx}: 异常 {e}", file=sys.stderr)
        return None


def _fmt_date(ymd: str) -> str:
    """20260816 -> 2026-08-16"""
    if len(ymd) != 8 or not ymd.isdigit():
        return ymd
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"


def load_existing() -> list[dict]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f).get("items", [])
        except Exception as e:
            print(f"data.json 读取失败，重新生成: {e}", file=sys.stderr)
    return []


def health_check(items: list[dict]) -> tuple[int, int]:
    """并发 HEAD 体检全量图片链接：失效的标记 dead=True（档案保留不删，
    前端展示时跳过 dead，自动用库里还活着的图补位）。
    返回 (存活数, 失效数)"""
    from concurrent.futures import ThreadPoolExecutor

    def check(it: dict) -> None:
        try:
            r = requests.head(it["full"], headers={"User-Agent": UA},
                              timeout=10, allow_redirects=True)
            if r.status_code == 200:
                it.pop("dead", None)   # 之前挂过现在复活，清掉标记
            else:
                it["dead"] = True
        except Exception:
            it["dead"] = True

    with ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(check, items))
    alive = sum(1 for it in items if not it.get("dead"))
    return alive, len(items) - alive


DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json")
INDEX_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
OG_RE = re.compile(r'(<meta (?:property="og:image"|name="twitter:image") content=")[^"]*(" />)')


def pick_hero_item(items: list[dict], today: str) -> dict | None:
    """挑选首屏 hero 图：当日中区(CN) → 当日美区(US) → 库里第一条存活图（与前端 pickHero 同逻辑）"""
    def by_reg(date: str, region: str):
        for it in items:
            if it["date"] == date and not it.get("dead") and it.get("region", "CN") == region:
                return it
        return None
    return by_reg(today, "CN") or by_reg(today, "US") or next(
        (it for it in items if not it.get("dead")), None
    )


def update_og_image(item: dict, dry_run: bool = False) -> bool:
    """把 index.html 的 og:image / twitter:image 更新为当天 hero 图的必应直链（社交分享卡片图）。
    每天跟随当天壁纸自动换，分享到微信/朋友圈/推特时预览图应景。"""
    if not item or not item.get("urlbase"):
        print("  og: 无 urlbase，跳过分享图更新", file=sys.stderr)
        return False
    new_url = f"https://cn.bing.com{item['urlbase']}_UHD.jpg"
    try:
        with open(INDEX_FILE, encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(f"  og: 读取 index.html 失败 {e}", file=sys.stderr)
        return False
    n_before = len(OG_RE.findall(html))
    new_html, n = OG_RE.subn(lambda m: m.group(1) + new_url + m.group(2), html)
    if n == 0:
        print(f"  og: index.html 未找到 og:image 标签（现有 {n_before} 处）", file=sys.stderr)
        return False
    if n != 2:
        print(f"  og: 匹配到 {n} 处（预期 2：og:image + twitter:image）", file=sys.stderr)
    if not dry_run:
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            f.write(new_html)
    print(f"  og: 分享图已更新为 {new_url}")
    return True


def main():
    parser = argparse.ArgumentParser(description="抓取必应壁纸生成 data.json")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写文件")
    args = parser.parse_args()

    total = len(MARKETS) * len(IDX_RANGE)
    print(f"[{datetime.now(BJ_TZ):%Y-%m-%d %H:%M:%S}] 开始抓取 {len(MARKETS)} 市场 × 8 天 = {total} 条 ...")
    fresh = []
    ok = fail = 0
    for mkt, _w in MARKETS:
        for idx in IDX_RANGE:
            item = fetch_day(mkt, idx)
            if item:
                fresh.append(item)
                ok += 1
            else:
                fail += 1
            time.sleep(SLEEP)
    print(f"抓取完成：成功 {ok} / 失败 {fail}")

    if not fresh:
        print("本次抓取全部失败，保留原 data.json", file=sys.stderr)
        sys.exit(1)

    # 合并：新抓的覆盖同"日期+市场"旧记录，其余保留；全量归档，不裁剪
    # 旧格式数据（v1，无 region 字段）全部是中区图，自动补 region=CN 一次性升级
    old_items = load_existing()
    for it in old_items:
        it.setdefault("region", "CN")
    merged = {(it["date"], it.get("region", "CN")): it for it in old_items}
    for item in fresh:
        merged[(item["date"], item["region"])] = item

    today = datetime.now(BJ_TZ).strftime("%Y%m%d")   # 北京时间，避免 UTC 差一天

    # 排序：日期倒序；同一天内按市场权重（中区最前，美区次之，其余按清单顺序）
    # 未来日期（> today）沉底：必应部分市场会提前一天放"明日图"（实测巴西等），
    # 数据照抓照存，但绝不能排到 items[0]（前端展示层另有未来日期过滤兜底）
    def _sort_key(x):
        """排序键：日期倒序（非法日期沉底，防历史脏数据搞崩排序）；同天按市场权重"""
        d = x.get("date", "")
        if not re.fullmatch(r"\d{8}", d):
            return (1, 99)   # 非 8 位纯数字日期 → 沉底，绝不排到 items[0]
        return (-int(d) if d <= today else 1,
                MARKET_WEIGHT.get(x.get("region", "CN"), 99))

    items = sorted(merged.values(), key=_sort_key)

    # 全量图片体检：失效的标记 dead（档案保留，前端跳过 dead 自动用活图补位）
    print("开始图片链接体检 ...")
    alive, dead = health_check(items)
    print(f"体检完成：存活 {alive} / 失效 {dead}")
    print(f"合并后 {len(items)} 条（全量归档，无限攒数据）")
    # 当日首屏大图：直接用必应官方 1920 热链（大厂 CDN 快且稳，实测 1~2s 内加载；
    # 自托管反而要过 EdgeOne 慢节点拖慢 10 倍，已废弃）。UHD 4K 版留给社交分享 og:image 用。
    hero_item = pick_hero_item(items, today)
    if hero_item:
        hero_idx = items.index(hero_item)
        hero_item = dict(hero_item)
        hero_item["hero"] = f"https://cn.bing.com{hero_item['urlbase']}_1920x1080.jpg"
        items[hero_idx] = hero_item
        print(f"  hero: 选定 {hero_item['date']} [{hero_item.get('region')}] 必应热链 1920")
    for it in items[:10]:
        print(f"  {it['date']} [{it['region']}] {it['title'][:24]}")

    # 社交分享图（og:image / twitter:image）跟随当天 hero 图自动更新（必应直链，UHD 4K）
    if hero_item:
        update_og_image(hero_item, dry_run=args.dry_run)

    # 直接写入（hero 每次注入新字段 + updated 时间戳必然变化，"跳过写入"判断永远不触发，
    # 纯死逻辑已清除；workflow 每次运行都会揉平提交，不存在空提交问题）

    payload = {
        "updated": datetime.now(BJ_TZ).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "today": today,
        "count": len(items),
        "items": items,
    }

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:1200])
        return

    try:
        # 先写临时文件再原子替换：防写入中途被杀/磁盘满留半截 JSON
        with open(DATA_FILE + ".tmp", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))   # 紧凑输出，EdgeOne 慢节点能省一点是一点
        os.replace(DATA_FILE + ".tmp", DATA_FILE)
    except Exception as e:
        print(f"写入 {DATA_FILE} 失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 写后回读校验：防止坏数据静默入库，校验不过直接失败（Actions 会告警）
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            back = json.load(f)
        assert back.get("count") == len(items), "count 字段与 items 条数不一致"
        assert len(back.get("items", [])) == len(items), "items 条数不一致"
        assert back.get("today"), "today 字段缺失"
        assert back.get("updated"), "updated 字段缺失"
        # 多市场结构校验：每条必须有 region 字段
        assert all("region" in it for it in back["items"]), "存在缺失 region 字段的记录"
    except Exception as e:
        print(f"回读校验失败，数据可能损坏: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"已写入 {DATA_FILE}（{len(items)} 条，回读校验通过）")


if __name__ == "__main__":
    main()
