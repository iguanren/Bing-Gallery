/* ============================================================
 * Bing Gallery · 站点公共脚本（site.js）
 * 主站 index.html 与 About 页 about.html 共用，同一套逻辑只维护一份。
 *
 * 负责：回到顶部 + 阅读进度环 / 夜间模式 / 运行天数 / 语言偏好
 * 依赖元素：
 *   #float-actions  #back-top（内含 .ring-fg）
 *   #night-toggle（内含 .icon-moon / .icon-sun）
 *   #lang-toggle（内含 .lang-alt-zh / .lang-alt-en）
 *   #uptime  #year
 *
 * 用法（在页面自己的脚本末尾调用）：
 *   BGSite.init({ onLang: function (lang) { ...按语言刷新本页文案... } });
 * ============================================================ */
window.BGSite = (function () {
  "use strict";

  var NIGHT_KEY = "iguanren_night";                        // 夜间模式偏好（两页共用）
  var LANG_KEY = "iguanren_lang";                          // 语言偏好（两页共用）
  var SITE_START = new Date("2019-06-16T00:00:00+08:00");  // 站点上线日（运行天数起算）

  var lang = "en";    // 当前语言：默认英文
  var onLang = null;  // 语言变化回调，由页面注入自己的文案渲染逻辑

  /* ---------- 回到顶部 + 阅读进度环 ---------- */
  function initTop() {
    var wrap = document.getElementById("float-actions");
    var btn = document.getElementById("back-top");
    if (!wrap || !btn) return;

    var ring = btn.querySelector(".ring-fg");
    var c = 0;
    /* 进度环半径取自 SVG 的 r 属性；万一取不到也不影响按钮本身可用 */
    if (ring && ring.r && ring.r.baseVal) {
      c = 2 * Math.PI * ring.r.baseVal.value;
      ring.style.strokeDasharray = c;
      ring.style.strokeDashoffset = c;
    }

    function update() {
      var st = window.scrollY || document.documentElement.scrollTop || 0;
      var max = document.documentElement.scrollHeight - window.innerHeight;
      var p = max > 0 ? Math.min(st / max, 1) : 0;
      if (ring) ring.style.strokeDashoffset = c * (1 - p);
      wrap.classList.toggle("show", st > 20);
    }

    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    btn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    update();
  }

  /* ---------- 夜间模式 ---------- */
  function applyNight(night) {
    document.documentElement.classList.toggle("night", night);
    var btn = document.getElementById("night-toggle");
    if (btn) {
      var moon = btn.querySelector(".icon-moon");
      var sun = btn.querySelector(".icon-sun");
      if (moon) moon.style.display = night ? "none" : "";
      if (sun) sun.style.display = night ? "" : "none";
    }
    try { localStorage.setItem(NIGHT_KEY, night ? "1" : "0"); } catch (e) {}
  }

  function initNight() {
    var btn = document.getElementById("night-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        applyNight(!document.documentElement.classList.contains("night"));
      });
    }
    var saved = false;
    try { saved = localStorage.getItem(NIGHT_KEY) === "1"; } catch (e) {}
    if (saved) applyNight(true);
  }

  /* ---------- 页脚：运行天数 + 版权年份 ---------- */
  function renderUptime() {
    var days = Math.floor((Date.now() - SITE_START.getTime()) / 86400000);
    var el = document.getElementById("uptime");
    if (el) el.textContent = (lang === "zh") ? "已运行 " + days + " 天" : "Running For " + days + " Days";
    var y = document.getElementById("year");
    if (y) y.textContent = new Date().getFullYear();
  }

  /* ---------- 语言 ---------- */
  function readLang() {
    try {
      var v = localStorage.getItem(LANG_KEY);
      if (v === "en" || v === "zh") return v;
    } catch (e) {}
    return "en";
  }

  /* 切语言：写偏好 → 设 html[lang]（驱动 CSS 双语显隐）→ 刷新按钮标签与页脚 → 通知页面重渲染文案 */
  function setLang(next, persist) {
    lang = (next === "zh") ? "zh" : "en";
    document.documentElement.lang = (lang === "zh") ? "zh-CN" : "en";
    if (persist !== false) {
      try { localStorage.setItem(LANG_KEY, lang); } catch (e) {}
    }
    var lb = document.getElementById("lang-toggle");
    if (lb) {
      var lbl = (lang === "zh") ? "语言" : "Language";
      lb.setAttribute("aria-label", lbl);
      lb.title = lbl;
    }
    renderUptime();
    if (onLang) onLang(lang);
    return lang;
  }

  /* 初始化：绑定三个悬浮按钮 + 恢复偏好 + 应用语言 */
  function init(opts) {
    opts = opts || {};
    onLang = opts.onLang || null;
    initTop();
    initNight();
    var lb = document.getElementById("lang-toggle");
    if (lb) {
      lb.addEventListener("click", function () {
        setLang(lang === "en" ? "zh" : "en");
      });
    }
    lang = readLang();
    setLang(lang, false);
  }

  return {
    init: init,
    setLang: setLang,
    applyNight: applyNight,
    renderUptime: renderUptime,
    getLang: function () { return lang; }
  };
})();
