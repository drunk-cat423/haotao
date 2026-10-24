// 快手 __NS_hxfalcon 纯算签名器 —— 从站点 bundle 切出的真实函数, Node 本地运行
// 用法: node ks_sign.js "<path>" '<form_json>' '<requestBody_json>'
//   例: node ks_sign.js /rest/v/search/feed '{"keyword":"篮球","page":1}' '{}'
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const CORE = path.join(__dirname, "ks_sig_core.js");

function createEnv() {
  const store = {};
  const sandbox = {
    console,
    Int8Array, Uint8Array, Int16Array, Int32Array, Uint32Array,
    Array, Object, Number, String, Boolean, Math, Date, JSON,
    RegExp, Symbol, Promise, Error, TypeError, Map, Set,
    ArrayBuffer, DataView, parseInt, parseFloat, isNaN, NaN, Infinity,
    encodeURIComponent, decodeURIComponent, escape, unescape,
    Buffer, setTimeout, clearTimeout, setInterval, clearInterval,
    performance: { now: () => Date.now() },
    location: { origin: "https://www.kuaishou.com", href: "https://www.kuaishou.com/search/video?searchKey=x" },
    navigator: { sendBeacon: () => true, userAgent: "" },
    document: { scripts: { length: 12 }, cookie: "" },
    localStorage: {
      getItem: (k) => store[k] ?? null,
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    },
    fetch: async () => { throw new Error("no network in signer"); },
    XMLHttpRequest: function () {},
  };
  sandbox.globalThis = sandbox;
  sandbox.window = sandbox;
  sandbox.self = sandbox;
  sandbox.global = sandbox;
  return sandbox;
}

function loadCtx() {
  const sandbox = createEnv();
  vm.createContext(sandbox);
  // 需要 SECS 先存在? $encode 内部自己 set; Ne.collectDeviceInfo 读 window.SECS
  sandbox.SECS = { s: "", c: 0 };
  const code = fs.readFileSync(CORE, "utf8");
  vm.runInContext(code + ";this.Je=Je;this.we=we;", sandbox,
    { filename: "ks_sig_core.js" });
  return sandbox;
}

function sign(pathName, form, requestBody, caver) {
  const ctx = loadCtx();
  const input = {
    url: pathName,
    query: { caver: caver || "2" },
    form: form || {},
    requestBody: requestBody || {},
    projectInfo: { appKey: "q5yq4bjUut", radarId: "0abb8037ac" },
  };
  const out = ctx.Je.$encode(input);
  return {
    signRes: out.signRes,
    signInput: out.signInput,
    error: out.error,
  };
}

if (require.main === module) {
  const [pathName, formJson, bodyJson, caver] = process.argv.slice(2);
  const form = formJson ? JSON.parse(formJson) : {};
  const body = bodyJson ? JSON.parse(bodyJson) : {};
  const r = sign(pathName || "/rest/v/search/feed", form, body, caver || "2");
  console.log(JSON.stringify(r, null, 1));
}

module.exports = { sign, loadCtx };
