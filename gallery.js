/* ============================================================
 * Bing Gallery - 主逻辑脚本
 * 分区索引：
 *   ① 回到顶部 + 滚动进度环 ……已移至 site.js
 *   ② 夜间模式 ……已移至 site.js
 *   ③ 壁纸数据加载（含 localStorage 本地缓存）
 *   ④ 首屏背景图
 *   ⑤ 卡片流渲染（含懒加载预取）
 *   ⑥ 历史壁纸归档
 *   ⑦ 灯箱预览（含左右切换 / 键盘操作）
 *   ⑧ 图片下载（iOS 走系统分享，其余走 a[download]）
 *   ⑨ 全局事件绑定
 *   ⑩ 语言文案渲染（中 / EN）
 *   ⑪ 启动入口
 *   ⑫ 底部信息 ……已移至 site.js
 *
 * 说明：本文件只放主站（index.html）专属逻辑；
 *      两页共用的悬浮按钮 / 偏好存储 / 运行天数在 site.js
 * ============================================================ */

/* ---------- 页面切换：不恢复旧滚动位置，避免从 About 等页面返回时停在半途 ---------- */
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

/* ---------- 全局状态 ---------- */
var todayStr = ""; // 今日日期字符串 YYYYMMDD（来自 data.json）
var WALLPAPERS = []; // 全部壁纸数据
var WP_CACHE_KEY = "bing_wp_cache_v2"; // 本地缓存键名（v2：region 字段结构升级，强制老访客拉新数据）

/* ---------- 站点双语（中 / EN） ---------- */
/* 说明：语言偏好读写、html[lang] 切换、悬浮按钮绑定均由公共脚本 site.js 负责，
   本页只保留"按当前语言渲染文案"的逻辑（见 ⑩ applyLang）。 */
var LANG = "en"; // 当前语言，默认英文

/* 界面文案词典：静态部分走 HTML 双份 + CSS 显隐，这里放 JS 动态渲染的文案 */
var I18N = {
  zh: {
    pageTitle: "Bing Gallery - 4K 高清美图壁纸画廊",
    download: "下载原图",
    downloading: "下载中…",
    loading: "正在加载...",
    loadFail: "图片加载失败，请检查网络后重试",
    loadingData: "壁纸数据加载中，请稍候刷新...",
    noArchive: "暂无归档数据",
    fallbackTitle: "必应美图",
    close: "关闭",
    nightMode: "夜间模式",
    backTop: "回到顶部",
    filterSuffix: function (n) { return "壁纸归档 · 共 " + n + " 张"; }
  },
  en: {
    pageTitle: "Bing Gallery - 4K HD Wallpaper Gallery",
    download: "Download",
    downloading: "Downloading…",
    loading: "Loading...",
    loadFail: "Image failed to load. Please check your network.",
    loadingData: "Loading wallpapers, please refresh...",
    noArchive: "No archive data",
    fallbackTitle: "Bing wallpaper",
    close: "Close",
    nightMode: "Night mode",
    backTop: "Back to top",
    filterSuffix: function (n) { return " wallpaper archive · " + n + " images"; }
  }
};

/* 英文市场与图片指纹映射：已抽到 site.js（BGSite.buildFpMap / BGSite.enVariant），两页共用一套算法 */
var MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function t(key) { return I18N[LANG][key]; }

/* 展示层未来日期过滤：必应部分市场会提前一天放出"明日图"（enddate 超前），
 * 数据照存不丢，但展示一律只显示 ≤ 今日，避免卡片流/首屏出现未来日期 */
function sanitizeItems(list) {
  if (!todayStr || !list) return list || [];
  return list.filter(function (it) {
    return !it.date || it.date <= todayStr;
  });
}

/* ---------- 工具函数 ---------- */

/* HTML 转义（卡片标题 / 缩略图 alt 防注入） */
function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* ---------- 双语工具 ---------- */

/* 图片指纹识别（fpOf）/ 英文市场映射（buildFpMap / enVariant）已抽到 site.js，
   主站与 About 页共用同一套算法，调用方式：BGSite.fpOf() / BGSite.buildFpMap() / BGSite.enVariant() */

/* 标题：英文模式优先取同图英文市场标题，缺省回退原文；"Info" 占位则用通用文案 */
function dispTitle(item) {
  if (!item) return t("fallbackTitle");
  var title = item.title;
  if (LANG === "en") {
    var en = BGSite.enVariant(item);
    if (en && en.title) title = en.title;
  }
  return title && title !== "Info" ? title : t("fallbackTitle");
}

/* 版权描述：英文模式优先取同图英文市场描述 */
function dispCopyright(item) {
  if (!item) return "";
  if (LANG === "en") {
    var en = BGSite.enVariant(item);
    if (en && en.copyright) return en.copyright;
  }
  return item.copyright || "";
}

/* 日期本地化："2026-09-11" → 中文「2026年9月11日」 / 英文「Sep 11, 2026」 */
function fmtDate(dateLabel) {
  if (!dateLabel) return "";
  var p = String(dateLabel).split("-");
  if (p.length !== 3) return dateLabel;
  var y = p[0], mo = parseInt(p[1], 10), d = parseInt(p[2], 10);
  if (LANG === "zh") return y + "年" + mo + "月" + d + "日";
  return MONTHS_EN[mo - 1] + " " + d + ", " + y;
}

/* ============================================================
 * 回到顶部 / 夜间模式：已抽到公共脚本 site.js（与 About 页共用一份），
 * 初始化见本文件末尾的 BGSite.init()
 * ============================================================ */

/* ============================================================
 * ③ 壁纸数据加载（含 localStorage 本地缓存）
 * ============================================================ */
/* 拉取 data.json；失败或离线时回退到本地缓存 */
function loadData() {
  var cached = null;
  try {
    cached = JSON.parse(localStorage.getItem(WP_CACHE_KEY) || "null");
  } catch (e) {}

  /* 有缓存先渲染，保证首屏秒开 */
  if (cached && cached.items && cached.items.length) {
    todayStr = cached.today || todayStr;   // 先取今日，再过滤未来图
    WALLPAPERS = sanitizeItems(cached.items);
    try {
      applyBg(pickHero());
      renderGallery();
    } catch (e) {}
  }

  /* 再从网络拉最新数据 */
  return fetch("data.json", { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("data.json " + r.status);
      return r.json();
    })
    .then(function (d) {
      todayStr = d.today || todayStr;   // 网络数据更新今日（原逻辑只取 WALLPAPERS，漏了这里）
      WALLPAPERS = sanitizeItems(d.items || []);
      try {
        localStorage.setItem(WP_CACHE_KEY, JSON.stringify(d));
      } catch (e) {}
      return d;
    })
    .catch(function (e) {
      console.error("加载壁纸数据失败:", e);
      return cached || {};
    });
}

/* ============================================================
 * ④ 首屏背景图
 * ============================================================ */
/* 首屏选图：当日中区 → 当日美区 → 最新一条（中区凌晨空窗时美区补位；失效图跳过） */
function pickHero() {
  if (!WALLPAPERS.length) return null;
  var byReg = function (date, region) {
    for (var i = 0; i < WALLPAPERS.length; i++) {
      var it = WALLPAPERS[i];
      if (it.date === date && !it.dead && (it.region || "CN") === region) return it;
    }
    return null;
  };
  var aliveFirst = null;
  for (var j = 0; j < WALLPAPERS.length; j++) {
    if (!WALLPAPERS[j].dead) { aliveFirst = WALLPAPERS[j]; break; }
  }
  return (todayStr && (byReg(todayStr, "CN") || byReg(todayStr, "US"))) || aliveFirst;
}

/* 把今日壁纸铺到首屏大图背景（统一必应官方 1920 热链，大厂 CDN 秒开） */
function applyBg(item) {
  if (!item || !item.full) return;
  /* 统一 1920 热链：hero 条目用数据自带 hero 字段，兜底条目（US 补位/最新存活图）
     也拼 1920 —— 原逻辑兜底条目在 PC 端直上 UHD 4K（3~6MB），白白拖慢首屏 */
  var url = item.hero || (item.urlbase
    ? "https://cn.bing.com" + item.urlbase + "_1920x1080.jpg"
    : item.full);
  var main = document.getElementById("main");
  if (main) main.style.background = "url(" + url + ") center/cover no-repeat";
  /* 沉浸模式：首屏只留版权描述（随语言切换：英文模式取同图英文市场描述） */
  var pc = document.querySelector(".pbi-copyright");
  if (pc) {
    var copy = dispCopyright(item);
    if (copy) pc.textContent = copy;
    pc.style.display = copy ? "" : "none";
  }
}

/* ============================================================
 * ⑤ 卡片流渲染（含懒加载预取）
 * ============================================================ */
var currentFilter = null; // 当前月份筛选，null = 显示最近
var SHOW_RECENT = 30; // 首页默认展示最近张数

/* 按屏幕宽度拼缩略图参数（小屏用更小图省流量） */
function thumbFor(item) {
  var w = window.innerWidth;
  if (w < 480) return item.thumb + "&w=240&h=135&rs=1&c=4";
  if (w < 768) return item.thumb + "&w=320&h=180&rs=1&c=4";
  return item.thumb;
}

/* 展示过滤：剔除失效图(dead) → 按图片基础名全局去重（跨天/跨市场同图只显示一次；
   数据已按日期倒序+中区优先排序，先见先留 = 保留最新上架的版本） */
function displayFilter(items) {
  var seen = {};
  var out = [];
  for (var i = 0; i < items.length; i++) {
    var it = items[i];
    if (it.dead) continue;
    var m = /id=(OHR\.[^_]+)/.exec(it.urlbase || "");
    var k = m ? m[1] : it.urlbase || i;
    if (seen[k]) continue;
    seen[k] = 1;
    out.push(it);
  }
  return out;
}

/* 渲染卡片流；list 缺省时展示过滤去重后的最近 SHOW_RECENT 张 */
function renderGallery(list) {
  var grid = document.getElementById("gallery-grid");
  var items = displayFilter(list || WALLPAPERS);
  if (!list && items.length > SHOW_RECENT) items = items.slice(0, SHOW_RECENT);
  if (!items.length) {
    grid.innerHTML = '<p class="gallery-empty">' + t("loadingData") + "</p>";
    return;
  }
  grid.innerHTML = items
    .map(function (item, i) {
      return (
        '<div class="wp-card" tabindex="0" role="button" data-index="' +
        i +
        '" title="' +
        escapeHtml(dispTitle(item)) +
        '">' +
        '<img src="' +
        thumbFor(item) +
        '" alt="' +
        escapeHtml(dispTitle(item)) +
        '" loading="lazy" decoding="async" referrerpolicy="no-referrer" />' +
        '<div class="wp-card-meta">' +
        '<span class="wp-card-date">' +
        fmtDate(item.dateLabel) +
        "</span>" +
        (item.region ? '<span class="wp-card-region">' + item.region + "</span>" : "") +
        '<span class="wp-card-title">' +
        escapeHtml(dispTitle(item)) +
        "</span>" +
        "</div></div>"
      );
    })
    .join("");

  /* 点击卡片 → 打开灯箱 */
  grid.querySelectorAll(".wp-card").forEach(function (card) {
    card.addEventListener("click", function (e) {
      e.preventDefault();
      openLightbox(parseInt(card.dataset.index, 10));
    });
    /* div 卡片无原生键盘行为，补 Enter/空格 触发（保持键盘可达） */
    card.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openLightbox(parseInt(card.dataset.index, 10));
      }
    });
  });

  /* 图片加载完加 .loaded 类（触发 CSS 淡入） */
  grid.querySelectorAll(".wp-card img").forEach(function (img) {
    var mark = function () {
      img.classList.add("loaded");
    };
    if (img.complete && img.naturalWidth > 0) mark();
    else {
      img.addEventListener("load", mark);
      img.addEventListener("error", mark);
    }
  });

  updateFilterBar();

  /* 交叉观察：即将进入视口的懒加载图提前变 eager 预取 */
  if ("IntersectionObserver" in window) {
    var prefetchIO = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            var img = en.target;
            if (img.loading === "lazy") img.loading = "eager";
            prefetchIO.unobserve(img);
          }
        });
      },
      { rootMargin: "600px 0px" }
    );
    grid.querySelectorAll(".wp-card img").forEach(function (img) {
      prefetchIO.observe(img);
    });
  }
}

/* ============================================================
 * ⑥ 历史壁纸归档（按月份浏览）
 * ============================================================ */
var archiveMask = document.getElementById("archive-mask");

/* 收集所有有数据的月份 YYYYMM，倒序 */
function getMonths() {
  var seen = {};
  WALLPAPERS.forEach(function (it) {
    seen[it.date.slice(0, 6)] = true;
  });
  return Object.keys(seen).sort().reverse();
}

/* 月份本地化："202509" → 中文「25 年 9 月」 / 英文「Sep 2025」 */
function fmtMonth(ym) {
  var y = ym.slice(0, 4), mo = parseInt(ym.slice(4), 10);
  if (LANG === "zh") return ym.slice(2, 4) + " 年 " + mo + " 月";
  return MONTHS_EN[mo - 1] + " " + y;
}

/* 按月份筛选并重渲染卡片流 */
function setMonthFilter(ym) {
  currentFilter = ym;
  var list = WALLPAPERS.filter(function (it) {
    return it.date.slice(0, 6) === ym;
  });
  renderGallery(list);
  closeArchive();
}

/* 回到首页：清筛选 + 滚回顶部 */
function goHome() {
  currentFilter = null;
  renderGallery();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* 筛选状态条：显示当前月份 + 张数 */
function updateFilterBar() {
  var bar = document.getElementById("filter-bar");
  var text = document.getElementById("filter-text");
  if (currentFilter) {
    var list = displayFilter(
      WALLPAPERS.filter(function (it) {
        return it.date.slice(0, 6) === currentFilter;
      })
    );
    text.textContent = fmtMonth(currentFilter) + t("filterSuffix")(list.length);
    bar.classList.add("show");
  } else {
    bar.classList.remove("show");
  }
}

/* 打开归档弹窗（月份按钮列表） */
function openArchive() {
  var box = document.getElementById("archive-months");
  var months = getMonths();
  box.innerHTML = months.length
    ? months
        .map(function (m) {
          return '<button type="button" class="archive-month" data-ym="' + escapeHtml(m) + '">' + fmtMonth(m) + "</button>";
        })
        .join("")
    : '<p class="archive-empty">' + t("noArchive") + "</p>";
  box.querySelectorAll(".archive-month").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setMonthFilter(btn.dataset.ym);
    });
  });
  archiveMask.classList.add("show");
  document.body.style.overflow = "hidden";
}

/* 关闭归档弹窗 */
function closeArchive() {
  archiveMask.classList.remove("show");
  document.body.style.overflow = "";
}

/* ============================================================
 * ⑦ 灯箱预览（含左右切换 / 键盘操作）
 * ============================================================ */
var lbModal = document.getElementById("lightbox");
var lbImg = document.getElementById("lb-img");
var lbLoading = document.getElementById("lb-loading");
var lbIndex = 0; // 当前灯箱下标
var currentList = []; // 灯箱所在列表（受月份筛选影响）
var currentLbItem = null; // 当前灯箱壁纸数据

/* 打开灯箱：列表取当前筛选结果（与卡片流同一套过滤去重，索引严格对齐） */
function openLightbox(index) {
  currentList = displayFilter(
    currentFilter
      ? WALLPAPERS.filter(function (it) {
          return it.date.slice(0, 6) === currentFilter;
        })
      : WALLPAPERS
  );
  if (!currentFilter && currentList.length > SHOW_RECENT) {
    currentList = currentList.slice(0, SHOW_RECENT);
  }
  if (!currentList.length) return;
  lbIndex = index;
  renderLightbox();
  lbModal.classList.add("show");
  document.body.style.overflow = "hidden";
}

/* 中图地址（移动端 1920 宽省流量） */
function midFor(item) {
  return "https://cn.bing.com" + item.urlbase + "_1920x1080.jpg";
}

/* 渲染灯箱：先显中图，加载完再无缝切 4K 原图 */
function renderLightbox() {
  var item = currentList[lbIndex];
  lbImg.style.opacity = "0";
  lbLoading.style.display = "flex";
  lbLoading.innerHTML = '<div class="wp-spin"></div><p>' + t("loading") + "</p>";
  lbImg.onload = function () {
    lbImg.style.opacity = "1";
    lbLoading.style.display = "none";
    var hd = new Image(); // 预加载 4K 原图，好了再替换
    hd.decoding = "async";
    hd.onload = function () {
      if (currentLbItem === item) lbImg.src = hd.src;
    };
    hd.onerror = function () {}; // 4K 加载失败静默保持 1920 中图（灯箱已有降级闭环）
    hd.src = item.full;
  };
  lbImg.onerror = function () {
    if (lbImg.src.indexOf("_1920x1080") !== -1) {
      lbImg.src = item.full;
      return;
    }
    lbLoading.innerHTML = "<p>" + t("loadFail") + "</p>";
  };
  lbImg.src = midFor(item);
  lbImg.alt = dispTitle(item);
  currentLbItem = item;
  document.getElementById("lb-date").textContent = fmtDate(item.dateLabel);
  document.getElementById("lb-title").textContent = dispTitle(item);
  document.getElementById("lb-copyright").textContent = dispCopyright(item);
}

/* 关闭灯箱 */
function closeLightbox() {
  lbModal.classList.remove("show");
  document.body.style.overflow = "";
}

/* 上一张 / 下一张 */
function lightboxPrev() {
  if (lbIndex > 0) {
    lbIndex--;
    renderLightbox();
  }
}
function lightboxNext() {
  if (lbIndex < currentList.length - 1) {
    lbIndex++;
    renderLightbox();
  }
}

/* 点空白/图片中间 1/3 关闭；左 1/3 上一张、右 1/3 下一张 */
lbModal.addEventListener("click", function (e) {
  if (e.target === lbModal) closeLightbox();
  else if (e.target === lbImg) {
    var r = lbImg.getBoundingClientRect();
    var third = r.width / 3;
    if (e.clientX < r.left + third) lightboxPrev();
    else if (e.clientX > r.right - third) lightboxNext();
    else closeLightbox();
  }
});
document.getElementById("lb-close").addEventListener("click", closeLightbox);

/* ============================================================
 * ⑧ 图片下载
 *    iOS 走系统分享面板，其余用 a[download] 触发浏览器下载
 * ============================================================ */
var dlBusy = false; // 下载互斥锁，防连点
var dlBtnEl = null; // 当前触发下载的按钮（实时回显文案/禁用态）

function downloadImage(url, name) {
  if (dlBusy || !url) return;
  dlBusy = true;
  var btn = dlBtnEl;
  if (btn) {
    btn.disabled = true;
    btn.textContent = t("downloading");
  }

  /* 收尾：恢复按钮状态（按当前语言恢复，切换语言后也不会文案错乱） */
  function done() {
    if (btn) {
      btn.disabled = false;
      btn.textContent = t("download");
    }
    dlBusy = false;
  }

  fetch(url)
    .then(function (r) {
      if (!r.ok) throw new Error("net");
      return r.blob();
    })
    .then(function (blob) {
      var fname =
        (name || "bing-wallpaper").replace(/[\\/:*?"<>|]/g, "_") + ".jpg";
      var file = new File([blob], fname, { type: "image/jpeg" });

      /* iOS：优先用系统分享（可存照片 / 存文件） */
      var isIOS =
        /iP(hone|ad|od)/.test(navigator.userAgent) || navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
      if (isIOS && navigator.canShare && navigator.canShare({ files: [file] })) {
        return navigator
          .share({ files: [file], title: fname })
          .catch(function (e) {
            /* 用户取消分享不报错，直接开新标签兜底 */
            if (e && e.name === "AbortError") return;
            window.open(URL.createObjectURL(blob), "_blank");
          });
      }

      /* 其余平台：创建临时 a[download] 触发下载 */
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      setTimeout(function () {
        URL.revokeObjectURL(a.href);
        a.remove();
      }, 1000);
    })
    .catch(function () {
      window.open(url, "_blank");
    })
    .then(done);
}

/* 下载文件名：日期-标题（非法字符替换为下划线） */
function dlName(item) {
  return item ? item.date + "-" + dispTitle(item) : "bing-wallpaper";
}

document.getElementById("lb-download").addEventListener("click", function () {
  dlBtnEl = this;
  downloadImage(currentLbItem ? currentLbItem.full : "", dlName(currentLbItem));
});

/* ============================================================
 * ⑨ 全局事件绑定
 * ============================================================ */

/* 首屏导航行：Home 回首页 / Archive 开归档弹窗 */
document.getElementById("pbi-home").addEventListener("click", function (e) {
  e.preventDefault();
  goHome();
});
document.getElementById("pbi-archive").addEventListener("click", function (e) {
  e.preventDefault();
  openArchive();
});
document.getElementById("archive-close").addEventListener("click", closeArchive);
archiveMask.addEventListener("click", function (e) {
  if (e.target === archiveMask) closeArchive();
});
document.getElementById("filter-home").addEventListener("click", goHome);

/* 卡片缩略图禁止右键（防右键存图 / 误操作） */
document.getElementById("gallery-grid").addEventListener("contextmenu", function (e) {
  if (e.target && e.target.tagName === "IMG") e.preventDefault();
});

/* 键盘：Esc 关所有弹层；← → 切灯箱 */
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") {
    closeLightbox();
    closeArchive();
  } else if (e.key === "ArrowLeft" && lbModal.classList.contains("show")) lightboxPrev();
  else if (e.key === "ArrowRight" && lbModal.classList.contains("show")) lightboxNext();
});

/* ============================================================
 * ⑩ 语言文案渲染（语言状态由公共脚本 site.js 统一管理）
 * ============================================================ */
/* 按当前语言刷新本页文案与动态内容，由 BGSite.init({ onLang }) 回调触发 */
function applyLang(lang) {
  LANG = lang === "en" ? "en" : "zh";

  /* JS 动态文案：data-i18n 文本 / data-i18n-aria 无障碍标签 / data-i18n-title 悬停提示 / data-i18n-alt 替代文本 */
  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    var v = I18N[LANG][el.dataset.i18n];
    if (v) el.textContent = v;
  });
  document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
    var v = I18N[LANG][el.dataset.i18nAria];
    if (v) el.setAttribute("aria-label", v);
  });
  document.querySelectorAll("[data-i18n-title]").forEach(function (el) {
    var v = I18N[LANG][el.dataset.i18nTitle];
    if (v) el.title = v;
  });
  document.querySelectorAll("[data-i18n-alt]").forEach(function (el) {
    var v = I18N[LANG][el.dataset.i18nAlt];
    if (v) el.alt = v;
  });

  /* 浏览器标签标题 */
  document.title = I18N[LANG].pageTitle;

  /* 受语言影响的动态内容重渲染（数据尚未加载时跳过，等 loadData 回来自然按当前语言渲染） */
  if (WALLPAPERS.length) {
    BGSite.buildFpMap(WALLPAPERS);
    applyBg(pickHero());
    renderGallery();
    updateFilterBar();
    if (archiveMask.classList.contains("show")) openArchive();
    if (lbModal.classList.contains("show")) renderLightbox();
  }
}

/* 悬浮按钮（语言切换 / 夜间模式 / 回到顶部）+ 运行天数 + 语言偏好：由公共脚本 site.js 统一初始化 */
BGSite.init({ onLang: applyLang });

/* ============================================================
 * ⑪ 启动入口
 * ============================================================ */
loadData().then(function (d) {
  d = d || {};
  todayStr = d.today || "";
  BGSite.buildFpMap(WALLPAPERS); // 构建「指纹 → 英文条目」映射，供英文模式取英文标题 / 版权
  if (d.items && d.items.length) applyBg(pickHero());
  renderGallery();
});

/* ⑫ 底部信息（运行天数 / 版权年份）已由公共脚本 site.js 渲染 */
