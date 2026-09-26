/* 页面加载不恢复旧滚动位置，避免切换后停在中途 */
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

/* —— 悬浮按钮（语言切换 / 夜间模式 / 回到顶部）+ 运行天数 + 语言偏好：由公共脚本 site.js 统一初始化 —— */

/* 语言文案渲染：整块 .i18n-zh / .i18n-en 由 CSS 显隐驱动，这里只处理 data-en / data-zh 文本节点 */
var LANG = "en"; /* 当前语言，默认英文 */

function applyLang(lang) {
  LANG = (lang === "en") ? "en" : "zh";
  /* 双语文本节点（data-en / data-zh）：直接替换文本，切换零刷新 */
  document.querySelectorAll("[data-en][data-zh]").forEach(function (el) {
    el.textContent = el.dataset[LANG];
  });
  /* 今日壁纸的版权描述随之切换（英文模式取同图英文市场描述） */
  renderHeroCap();
  /* 浏览器标签标题固定为 About Bing Gallery，不随语言变化 */
}

BGSite.init({ onLang: applyLang });

/* —— 今日壁纸展示：取 data.json 最新一条（≤ 今日），只叠版权描述 —— */
var heroItem = null; // 当前展示的今日壁纸条目（供语言切换时重取版权描述）

/* 版权描述：英文模式优先取同图英文市场描述（与主站灯箱共用 site.js 的指纹算法） */
function capOf(item) {
  if (!item) return "";
  if (LANG === "en") {
    var en = BGSite.enVariant(item);
    if (en && en.copyright) return en.copyright;
  }
  return item.copyright || "";
}

function renderHeroCap() {
  var cap = document.getElementById("about-hero-caption");
  if (cap && heroItem) cap.textContent = capOf(heroItem);
}

(function () {
  var hero = document.getElementById("about-hero");
  var img = document.getElementById("about-hero-img");
  if (!hero || !img) return;

  function pad(n) { return (n < 10 ? "0" : "") + n; }
  var now = new Date();
  var todayStr = "" + now.getFullYear() + pad(now.getMonth() + 1) + pad(now.getDate());

  fetch("data.json", { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("data.json " + r.status);
      return r.json();
    })
    .then(function (d) {
      var items = d.items || d.images || [];
      BGSite.buildFpMap(items); // 构建「指纹 → 英文条目」映射，供英文模式取版权描述
      var item = null;
      for (var i = 0; i < items.length; i++) {
        if (!items[i].date || items[i].date <= todayStr) { item = items[i]; break; }
      }
      if (!item) throw new Error("no item");
      var url = item.hero || (item.urlbase
        ? "https://cn.bing.com" + item.urlbase + "_1920x1080.jpg"
        : item.full);
      if (!url) throw new Error("no url");
      img.addEventListener("load", function () { img.classList.add("is-loaded"); });
      img.addEventListener("error", function () { hero.style.display = "none"; });
      img.src = url;
      heroItem = item;
      renderHeroCap();
    })
    .catch(function () {
      hero.style.display = "none";   /* 拉取失败或没图：整块隐藏，不留空框 */
    });
})();
