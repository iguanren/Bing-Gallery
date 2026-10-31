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

  img.addEventListener("load", function () { img.classList.add("is-loaded"); });
  img.addEventListener("error", function () { hero.style.display = "none"; });

  /* HTML 内联的当天首屏图：先秒开，不等 data.json 往返 */
  var meta = BGSite.meta();
  if (meta.hero && meta.hero.hero) {
    heroItem = meta.hero;
    img.src = meta.hero.hero;
    renderHeroCap();
  }

  /* 再拉全量数据：只为补「同图英文市场版权」的映射（切换语言时要用） */
  fetch(BGSite.dataUrl())
    .then(function (r) {
      if (!r.ok) throw new Error("data.json " + r.status);
      return r.json();
    })
    .then(function (d) {
      var items = BGSite.hydrate(d.items || d.images || []);
      BGSite.buildFpMap(items); // 构建「指纹 → 英文条目」映射，供英文模式取版权描述
      /* 首屏图以 bg-meta 内联为准（与主站 pickHero 同一口径、北京时间基准）：
         两页显示同一张图，也不会因本地时区与北京时间不一致而中途换图闪烁。
         内联块缺失时，才退回按本地日期挑一条的旧逻辑。 */
      var item = meta.hero;
      if (!item) {
        for (var i = 0; i < items.length; i++) {
          if (!items[i].date || items[i].date <= todayStr) { item = items[i]; break; }
        }
      }
      if (!item) throw new Error("no item");
      var url = item.hero || item.full;
      if (!url) throw new Error("no url");
      if (img.getAttribute("src") !== url) img.src = url;
      heroItem = item;
      renderHeroCap();
    })
    .catch(function () {
      /* 数据拉不到时：内联首屏图已经显示就别动它；压根没图才把整块收起来 */
      if (!heroItem) hero.style.display = "none";
    });
})();
