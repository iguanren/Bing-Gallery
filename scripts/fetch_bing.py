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
import hashlib
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

# ---------- 图片链接体检参数（防归档无限增长后体检耗时爆掉流水线） ----------
HEALTH_FULL_DAYS = 30      # 最近 30 天全量体检（约 15 市场 × 30 天 ≈ 450 条）
HEALTH_SAMPLE_OLD = 120    # 更早的归档每天轮换抽样条数（每天换一批，长期覆盖全部）
HEALTH_BUDGET_SEC = 240    # 体检总耗时熔断（秒），超预算立即停止，剩余条目保持原状态
HEALTH_WORKERS = 20        # 并发 HEAD 数
HEALTH_TIMEOUT = 12        # 单请求超时（秒）—— UHD 原图可达 3~4MB，10s 偏紧容易误判

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
        # 只存"不可还原"的信息：thumb/full/dateLabel 三个字段都能由 urlbase 推出来，
        # 存进 JSON 是纯冗余（1000+ 条 × 每条约 130 字节），一律在前端按需推导。
        return {
            "date": date,
            "region": region,
            "title": img.get("title", ""),
            "copyright": img.get("copyright", ""),
            "copyrightlink": img.get("copyrightlink", ""),
            "urlbase": urlbase,
        }
    except Exception as e:
        print(f"  {mkt} idx={idx}: 异常 {e}", file=sys.stderr)
        return None


def load_existing() -> list[dict]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                return json.load(f).get("items", [])
        except Exception as e:
            print(f"data.json 读取失败，重新生成: {e}", file=sys.stderr)
    return []


def health_check(items: list[dict], today: str) -> tuple[int, int, int]:
    """并发 HEAD 体检图片链接。

    为什么分层：站点做"全量归档、只增不减"，条目数会无限增长（现已 1000+ 条）。
    若每次都全量 HEAD，并发 20 × 超时 10s 的最坏耗时随条目数线性上升，
    迟早撞破 workflow 的 timeout-minutes: 10，整条自动更新流水线直接挂。
    策略：
      · 最近 HEALTH_FULL_DAYS 天：全量体检（首屏图与近期展示的准确性优先）
      · 更早的归档：按日轮换抽样 HEALTH_SAMPLE_OLD 条（每天换一批，长期覆盖全部）
      · 总耗时熔断 HEALTH_BUDGET_SEC：超预算立刻停止，剩余条目保持原状态

    失效判定：只有明确的 404 才标 dead；超时 / 限流 / 5xx / 网络异常一律视为
    "不确定"，保持条目原状态。原来的实现把异常也判成 dead —— Bing 侧一次
    网络抖动就能把大批正常图误杀，前端会大面积空图。

    返回 (存活数, 失效数, 未体检数)
    """
    from concurrent.futures import ThreadPoolExecutor
    import random

    # 分层：最近 N 天全检，其余按日轮换抽样
    try:
        today_d = datetime.strptime(today, "%Y%m%d").date()
        cutoff = (today_d - timedelta(days=HEALTH_FULL_DAYS)).strftime("%Y%m%d")
    except ValueError:
        cutoff = today  # 日期异常就退化成"全检当天"

    recent, old = [], []
    for it in items:
        (recent if it.get("date", "") >= cutoff else old).append(it)

    # 老数据抽样：已判定失效的不再重复查（省时间），每天换一批样本保证长期覆盖
    old_alive = [it for it in old if not it.get("dead")]
    rng = random.Random(today)
    picked = rng.sample(old_alive, min(HEALTH_SAMPLE_OLD, len(old_alive)))
    targets = recent + picked

    deadline = time.monotonic() + HEALTH_BUDGET_SEC
    state = {"alive": 0, "dead": 0, "skip": 0}

    def check(it: dict) -> None:
        if time.monotonic() > deadline:
            state["skip"] += 1
            return          # 熔断：保持原状态，不误判
        try:
            # data.json 已瘦身，full 字段不再落盘，这里按 urlbase 现场拼 UHD 直链
            r = requests.head(f"https://cn.bing.com{it['urlbase']}_UHD.jpg",
                              headers={"User-Agent": UA},
                              timeout=HEALTH_TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                it.pop("dead", None)   # 之前挂过现在复活，清掉标记
                state["alive"] += 1
            elif r.status_code == 404:
                it["dead"] = True      # 明确 404 才判死
                state["dead"] += 1
            else:
                state["skip"] += 1      # 限流/5xx 等：不确定，保持原状态
        except Exception:
            state["skip"] += 1          # 网络异常：不确定，保持原状态

    with ThreadPoolExecutor(max_workers=HEALTH_WORKERS) as ex:
        list(ex.map(check, targets))

    # 未参与本次体检的条目保持原状态，计入"未体检"
    state["skip"] += len(items) - len(targets)
    return state["alive"], state["dead"], state["skip"]


DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json")
INDEX_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html")
ABOUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "about.html")
OG_FILES = [INDEX_FILE, ABOUT_FILE]   # 两页的分享图都跟随当天壁纸
OG_RE = re.compile(r'(<meta (?:property="og:image"|name="twitter:image") content=")[^"]*(" />)')
README_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
README_ZH_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.zh-CN.md")
README_FILES = [README_FILE, README_ZH_FILE]   # 中英双语 README，今日壁纸图一起更新
# README 顶部「今日壁纸」图：锚定 markdown 图片 + 必应直链（中英两版 alt 文案不同，故不绑 alt）
README_IMG_RE = re.compile(r'(!\[[^\]]*\]\()(https://cn\.bing\.com/[^)]+)(\))')

# ---------- 首屏解耦 + 缓存版本号 ----------
# index.html / about.html 的 <head> 里预置两块占位，由本脚本每次运行注入内容：
#   <style id="hero-preload">首屏大图的 background（HTML 到达即出图，不必等 data.json 往返）
#   <script id="bg-meta" type="application/json">当天 hero 元信息 + 数据内容哈希 v
# 「v」同时充当：静态资源版本号（?v=xxx）、data.json 的缓存键、localStorage 缓存键
# —— 数据结构一升级，v 变，老访客的旧 JS 与旧缓存自动失效，不会出现"新数据配旧前端"
HERO_STYLE_RE = re.compile(r'<style id="hero-preload">.*?</style>', re.S)
META_RE = re.compile(r'(<script id="bg-meta" type="application/json">).*?(</script>)', re.S)
# 静态资源版本号：只匹配 .js/.css/.svg 的 ?v= 参数，不碰 og:image / README 里的必应直链
ASSET_VER_RE = re.compile(r'(\.(?:js|css|svg))(\?v=)([A-Za-z0-9._-]+)')
# data.json 里可由 urlbase 无损还原的派生字段（瘦身前存在旧数据里，入库时统一剔除）
DERIVED_FIELDS = ("dateLabel", "thumb", "full")


def strip_derived(it: dict) -> dict:
    """剔除可由 urlbase 还原的派生字段，保证 JSON 里只留不可还原的信息。
    对旧数据同样生效 —— 历史归档里的老记录也会顺势瘦身。"""
    for k in DERIVED_FIELDS:
        it.pop(k, None)
    return it


def compute_version(items: list[dict]) -> str:
    """数据内容哈希 → 资源版本号。
    内容不变则版本号不变（浏览器/CDN 缓存继续命中）；内容一变则版本号变
    （URL 变 → 全新 200，不会拿到半新半旧的组合）。"""
    blob = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:10]


def build_meta(hero_item: dict | None, today: str, count: int, ver: str) -> dict:
    """构建 bg-meta 内联块内容：当天首屏图元信息 + 数据版本号"""
    hero = None
    if hero_item and hero_item.get("urlbase"):
        hero = {
            "date": hero_item.get("date", ""),
            "region": hero_item.get("region", "CN"),
            "title": hero_item.get("title", ""),
            "copyright": hero_item.get("copyright", ""),
            "urlbase": hero_item["urlbase"],
            "hero": hero_item.get("hero") or f"https://cn.bing.com{hero_item['urlbase']}_1920x1080.jpg",
        }
    return {"v": ver, "today": today, "count": count, "hero": hero}


def update_page_meta(path: str, meta: dict, ver: str, dry_run: bool = False) -> bool:
    """把 bg-meta 块 + 首屏背景样式注入 HTML，同时把静态资源 ?v= 统一刷成 ver。
    顺序要紧：先写 meta 块，再刷版本号 —— 版本号正则不扫刚写入的 JSON，
    避免版权文案里恰好含 ".js?v=" 时被误伤。"""
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        print(f"  meta: 读取 {name} 失败 {e}", file=sys.stderr)
        return False

    # 1) 首屏背景样式：HTML 里直接内联，浏览器解析到就渲染，不用等 JS 和 data.json
    hero = meta.get("hero")
    if hero and hero.get("hero"):
        bg = hero["hero"].replace("\\", "").replace('"', "%22")
        css = ('#main{background-image:url("%s");background-position:center center;'
               'background-size:cover;background-repeat:no-repeat;}' % bg)
    else:
        css = "#main{background-image:none;}"
    if HERO_STYLE_RE.search(html):
        html = HERO_STYLE_RE.sub(lambda m: '<style id="hero-preload">%s</style>' % css, html, count=1)
    else:
        html = html.replace("</head>", '<style id="hero-preload">%s</style>\n</head>' % css, 1)

    # 2) bg-meta 内联块：JSON 里的 "</" 要转义，否则会提前闭合 script 标签
    blob = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = META_RE.sub(lambda m: m.group(1) + blob + m.group(2), html, count=1)

    # 3) 静态资源版本号：?v=20260911l 之类的老版本号全部刷成当前 ver
    n_ver = len(ASSET_VER_RE.findall(html))
    html = ASSET_VER_RE.sub(lambda m: m.group(1) + m.group(2) + ver, html)

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    print(f"  meta: {name} 已注入首屏图 + bg-meta（v={ver}，刷新 {n_ver} 处资源版本号）")
    return True


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
    """把 index.html / about.html 的 og:image / twitter:image 更新为当天 hero 图的必应直链（社交分享卡片图）。
    每天跟随当天壁纸自动换，分享到微信/朋友圈/推特时预览图应景。"""
    if not item or not item.get("urlbase"):
        print("  og: 无 urlbase，跳过分享图更新", file=sys.stderr)
        return False
    new_url = f"https://cn.bing.com{item['urlbase']}_UHD.jpg"
    any_ok = False
    for path in OG_FILES:
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                html = f.read()
        except Exception as e:
            print(f"  og: 读取 {name} 失败 {e}", file=sys.stderr)
            continue
        n_before = len(OG_RE.findall(html))
        new_html, n = OG_RE.subn(lambda m: m.group(1) + new_url + m.group(2), html)
        if n == 0:
            print(f"  og: {name} 未找到 og:image 标签（现有 {n_before} 处）", file=sys.stderr)
            continue
        if n != 2:
            print(f"  og: {name} 匹配到 {n} 处（预期 2：og:image + twitter:image）", file=sys.stderr)
        if not dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_html)
        print(f"  og: {name} 分享图已更新为 {new_url}")
        any_ok = True
    return any_ok


def update_readme_image(item: dict, dry_run: bool = False) -> bool:
    """把中英两版 README 顶部的「今日壁纸」图更新为当天 hero 图（1920 热链，不用 4K 以免 README 加载过重）。
    每天跟随当天壁纸自动换；URL 每日不同，也能绕开 GitHub camo 图片代理的长缓存。"""
    if not item or not item.get("urlbase"):
        print("  readme: 无 urlbase，跳过今日壁纸图更新", file=sys.stderr)
        return False
    new_url = f"https://cn.bing.com{item['urlbase']}_1920x1080.jpg"
    any_ok = False
    for path in README_FILES:
        name = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as f:
                md = f.read()
        except Exception as e:
            print(f"  readme: 读取 {name} 失败 {e}", file=sys.stderr)
            continue
        new_md, n = README_IMG_RE.subn(lambda m: m.group(1) + new_url + m.group(3), md)
        if n == 0:
            print(f"  readme: {name} 未找到今日壁纸图，跳过", file=sys.stderr)
            continue
        if n != 1:
            print(f"  readme: {name} 匹配到 {n} 处（预期 1）", file=sys.stderr)
        if not dry_run:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_md)
        print(f"  readme: {name} 今日壁纸图已更新为 {new_url}")
        any_ok = True
    return any_ok


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
        strip_derived(it)          # 旧数据顺势瘦身（剔除可由 urlbase 还原的派生字段）
    merged = {(it["date"], it.get("region", "CN")): it for it in old_items}
    for item in fresh:
        strip_derived(item)
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

    # 图片链接体检：分层 + 熔断（最近 30 天全检 + 老数据按日轮换抽样），防归档涨大后拖爆流水线
    print(f"开始图片链接体检（最近 {HEALTH_FULL_DAYS} 天全检 + 老数据轮换抽样 {HEALTH_SAMPLE_OLD} 条，熔断 {HEALTH_BUDGET_SEC}s）...")
    t0 = time.monotonic()
    alive, dead, skipped = health_check(items, today)
    print(f"体检完成：存活 {alive} / 失效 {dead} / 未体检 {skipped}（耗时 {time.monotonic() - t0:.0f}s）")
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
        update_readme_image(hero_item, dry_run=args.dry_run)

    # 数据内容哈希 → 资源版本号 v（内容不变则版本号不变，缓存继续命中；内容变则全局刷新）
    ver = compute_version(items)
    meta = build_meta(hero_item, today, len(items), ver)
    print(f"  ver: 数据版本号 {ver}")
    for path in [INDEX_FILE, ABOUT_FILE]:
        update_page_meta(path, meta, ver, dry_run=args.dry_run)

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
