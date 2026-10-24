#!/usr/bin/env node
// dy_abogus_signer.js —— 真·纯算 a_bogus 签名器
// 原理: bdms.js 内含完整 JSVM (解释器 d + ~796 个程序), 其中程序 107/689 计算 a_bogus.
// 独立运行, 零浏览器, 零握手, 零网络.
// 用法:
//   node dy_abogus_signer.js sign '<unsigned_url>'   -> 打印签名后 URL
//   node dy_abogus_signer.js                          -> stdin/stdout 守护模式 (每行一个URL, 输出签名URL)
// 需要: ../pure/local/session.secrets.json (ua/webid/uifid/verifyFp/fp) + ../pure/run/cookie.txt (cookie, 取 msToken)

const fs = require("fs");
const vm = require("vm");
const path = require("path");
const readline = require("readline");

const ROOT = __dirname;
const secrets = JSON.parse(fs.readFileSync(path.join(ROOT, "../pure/local/session.secrets.json"), "utf8"));
const cookie = fs.readFileSync(path.join(ROOT, "../pure/run/cookie.txt"), "utf8").trim();

const noop = function () {};
const store = {};

function mkXHR() {
  function XHR() {
    this._h = {};
    this.upload = { addEventListener: noop, removeEventListener: noop, dispatchEvent: () => true };
    for (const h of ["onabort", "onerror", "onload", "onloadstart", "onloadend", "onprogress", "onreadystatechange", "ontimeout"])
      this[h] = null;
  }
  XHR.prototype.open = function (m, u, a) { this.method = m; this.url = u; };
  XHR.prototype.send = function () {
    this.readyState = 4; this.status = 200;
    if (this.onreadystatechange) this.onreadystatechange();
    if (this.onload) this.onload();
  };
  XHR.prototype.setRequestHeader = function (k, v) { this._h[k] = v; };
  XHR.prototype.getAllResponseHeaders = () => "";
  XHR.prototype.getResponseHeader = () => null;
  XHR.prototype.addEventListener = noop;
  XHR.prototype.removeEventListener = noop;
  XHR.prototype.dispatchEvent = () => true;
  XHR.prototype.abort = noop;
  return XHR;
}

function makeCtx() {
  const XHR = mkXHR();
  const sandbox = {
    console: { log: noop, error: noop, warn: noop, info: noop, debug: noop },
    Math, Date, JSON, URL, URLSearchParams, Object, Array, String,
    Number, Boolean, RegExp, Error, TypeError, Symbol, Promise,
    Int8Array, Uint8Array, Int16Array, Int32Array, ArrayBuffer, DataView,
    Map, Set, WeakMap, parseInt, parseFloat, isNaN, isFinite,
    encodeURIComponent, decodeURIComponent, encodeURI, decodeURI, escape, unescape,
    setTimeout: (f) => setTimeout(f, 0), clearTimeout, setInterval, clearInterval,
    queueMicrotask, requestAnimationFrame: (f) => setTimeout(f, 0), cancelAnimationFrame: clearTimeout,
    atob: (s) => Buffer.from(s, "base64").toString("binary"),
    btoa: (s) => Buffer.from(s, "binary").toString("base64"),
    Reflect, Proxy,
    AbortController: function () { this.signal = { aborted: false, addEventListener: noop }; this.abort = noop; },
    Blob: function () {}, FormData: function () { this.append = noop; }, FileReader: function () {},
    Image: function () { this.src = ""; }, WebSocket: function () {}, Worker: function () {},
    MutationObserver: function () { this.observe = noop; this.disconnect = noop; },
    IntersectionObserver: function () { this.observe = noop; this.disconnect = noop; },
    ResizeObserver: function () { this.observe = noop; this.disconnect = noop; },
    getComputedStyle: () => ({ getPropertyValue: () => "" }),
    location: {
      href: "https://www.douyin.com/", origin: "https://www.douyin.com",
      protocol: "https:", host: "www.douyin.com", hostname: "www.douyin.com",
      pathname: "/", search: "",
    },
    navigator: {
      userAgent: secrets.ua, language: "zh-CN", languages: ["zh-CN"], platform: "Win32",
      hardwareConcurrency: 16, deviceMemory: 8, webdriver: false,
      plugins: { length: 3 }, mimeTypes: { length: 2 },
      cookieEnabled: true, sendBeacon: () => true, maxTouchPoints: 0,
      vendor: "Google Inc.", appVersion: secrets.ua, doNotTrack: null,
      connection: { effectiveType: "4g" },
    },
    document: {
      cookie: cookie + "; uifid=" + secrets.uifid,
      scripts: { length: 12 }, documentElement: {}, readyState: "complete",
      referrer: "", hidden: false, visibilityState: "visible", domain: "www.douyin.com",
      createElement: () => ({ getContext: () => null, setAttribute: () => {}, style: {}, appendChild: () => {}, addEventListener: noop }),
      addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => true,
      getElementById: () => null, querySelector: () => null, querySelectorAll: () => [],
      body: { appendChild: noop }, head: { appendChild: noop },
    },
    screen: { width: 1920, height: 1080, availWidth: 1920, availHeight: 1040, colorDepth: 24, pixelDepth: 24 },
    localStorage: {
      getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; }, key: () => null, length: 0,
    },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    performance: {
      now: () => Date.now() % 100000, timeOrigin: Date.now() - 1000,
      timing: { navigationStart: Date.now() - 1000 }, getEntriesByType: () => [],
    },
    crypto: require("crypto").webcrypto,
    XMLHttpRequest: XHR,
    fetch: async () => { throw new Error("no net"); },
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => true,
    innerWidth: 1366, innerHeight: 768, outerWidth: 1366, outerHeight: 768,
    devicePixelRatio: 1, history: {}, frameElement: null,
    CSS: { supports: () => true },
    indexedDB: { open: () => ({ onsuccess: null, onerror: null, result: null }) },
    EventTarget: function () {},
  };
  sandbox.window = sandbox; sandbox.self = sandbox; sandbox.globalThis = sandbox;
  sandbox.top = sandbox; sandbox.parent = sandbox; sandbox.frames = [];
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(ROOT, "bdms.js"), "utf8"), sandbox, { filename: "bdms.js" });
  sandbox.bdms.init({
    aid: 6383, pageId: 11881,
    paths: ["^/webcast/", "^/aweme/v1/", "^/aweme/v2/", "/v1/message/send", "^/live/", "^/captcha/", "^/ecom/"],
    boe: false, ddrt: 8.5, ic: 8.5,
  });
  return { sandbox, XHR };
}

// 业务 URL 模板 (与 buildUnsignedUrl 同构) — 所有参数来自 secrets/cookie, 静态
function buildSearchUrl(keyword, offset, count, msToken) {
  const s = secrets;
  const q = new URLSearchParams({
    device_platform: "webapp", aid: "6383", channel: "channel_pc_web",
    search_channel: "aweme_general", search_source: "normal_search",
    version_code: "190600", version_name: "19.6.0",
    keyword, offset: String(offset), count: String(count),
    pc_client_type: "1", pc_libra_divert: "Windows", support_h265: "1", support_dash: "0",
    cpu_core_num: "16", cookie_enabled: "true",
    screen_width: "1920", screen_height: "1080",
    browser_language: "zh-CN", browser_platform: "Win32", browser_name: "Chrome",
    browser_version: "120.0.0.0", browser_online: "true",
    engine_name: "Blink", engine_version: "120.0.0.0",
    os_name: "Windows", os_version: "10", device_memory: "8", platform: "PC",
    downlink: "10", effective_type: "4g", round_trip_time: "50",
    webid: s.webid, uifid: s.uifid,
  });
  if (s.verify_fp) q.set("verifyFp", s.verify_fp);
  if (s.fp) q.set("fp", s.fp);
  if (msToken) q.set("msToken", msToken);
  return "https://www.douyin.com/aweme/v1/web/general/search/single/?" + q.toString();
}

function cookieMsToken() {
  const m = /msToken=([^;]+)/.exec(cookie);
  return m ? m[1] : (secrets.msToken || "");
}

const { sandbox, XHR } = makeCtx();

function sign(url) {
  const x = new XHR();
  x.open("GET", url, true);
  x.setRequestHeader("uifid", secrets.uifid);
  x.send();
  return String(x.url || url);
}

// 签名就绪延迟 (bdms 内部异步初始化)
function ready(cb) {
  let tries = 0;
  const tick = () => {
    tries++;
    const t = sign("https://www.douyin.com/aweme/v1/x/?a=1");
    if (/a_bogus/.test(t) || tries > 50) return cb();
    setTimeout(tick, 100);
  };
  setTimeout(tick, 200);
}

const args = process.argv.slice(2);
if (args[0] === "sign" && args[1]) {
  ready(() => {
    let url = args[1];
    if (url === "-") url = buildSearchUrl(args[2] || "篮球", args[3] || 0, args[4] || 12, cookieMsToken());
    console.log(sign(url));
    process.exit(0);
  });
} else if (args[0] === "search") {
  ready(() => {
    const kw = args[1] || "篮球", off = Number(args[2] || 0), cnt = Number(args[3] || 12);
    console.log(sign(buildSearchUrl(kw, off, cnt, cookieMsToken())));
    process.exit(0);
  });
} else {
  // 守护模式: 每行读一个URL, 输出签名URL; 特殊行 "SEARCH <kw> <off> <cnt>"
  ready(() => {
    const rl = readline.createInterface({ input: process.stdin });
    rl.on("line", (line) => {
      line = line.trim();
      if (!line) return;
      if (line.startsWith("SEARCH ")) {
        const [, kw, off, cnt] = line.split(" ");
        console.log(sign(buildSearchUrl(kw, off || 0, cnt || 12, cookieMsToken())));
      } else {
        console.log(sign(line));
      }
    });
    console.error("[signer ready]");
  });
}
