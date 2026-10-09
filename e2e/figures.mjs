// 화면 캡처와 글자 겹침 점검 (DESIGN.md 8절).
//   BASE_URL=http://127.0.0.1:8100 node figures.mjs
// 출력 (docs/figures/):
//   screens/{desktop,mobile}/*.png  — 화면 전체. 1280×800(기본)과 390×844 두 폭 모두 겹침·넘침·가로 스크롤 점검
//   paper/*.png                     — 논문 Figure. 화면 전체가 아니라 요소 단위(data-figure), 2배 해상도
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8000";
const OUT = new URL("../docs/figures/", import.meta.url).pathname;
const VIEWPORTS = { desktop: { width: 1280, height: 800 }, mobile: { width: 390, height: 844 } };
// Figure 캡처 때만 테두리를 진하게 (#E5E7EB는 흑백 인쇄에서 사라짐). 앱 토큰은 그대로.
const PRINT_CSS = ".card{border-color:#9CA3AF!important} .chip-source,.card-soft{outline:1px solid #C4C8CE}";

for (const dir of ["screens/desktop", "screens/mobile", "paper"]) mkdirSync(OUT + dir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome" });
let problems = 0;

async function textCheck(page, name) {
  const issues = await page.evaluate(() => {
    const rects = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const n = walker.currentNode;
      if (!n.textContent.trim()) continue;
      const el = n.parentElement;
      const cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.display === "none") continue;
      if (el.closest("svg")) continue;
      const r = document.createRange();
      r.selectNodeContents(n);
      for (const b of r.getClientRects())
        if (b.width > 1)
          rects.push({
            t: n.textContent.trim().slice(0, 20),
            x: b.left,
            y: b.top + scrollY,
            w: b.width,
            h: b.height,
            fixed: !!el.closest(".nav,.dialog-backdrop"),
            scroll: !!el.closest(".suggest-list,.nav-links"), // 의도된 가로 스크롤
          });
    }
    const out = [];
    const vw = document.documentElement.clientWidth;
    for (const a of rects) if (!a.scroll && (a.x < -1 || a.x + a.w > vw + 1)) out.push(`넘침: "${a.t}"`);
    for (let i = 0; i < rects.length; i++)
      for (let j = i + 1; j < rects.length; j++) {
        const a = rects[i],
          b = rects[j];
        if (a.fixed !== b.fixed) continue;
        const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        if (ox > 2 && oy > 4) out.push(`겹침: "${a.t}" / "${b.t}"`);
      }
    if (document.documentElement.scrollWidth > vw) out.push(`가로 스크롤 ${document.documentElement.scrollWidth}>${vw}`);
    return out;
  });
  if (issues.length) problems++;
  console.log(`[${name}] ${issues.length ? issues.join(" | ") : "OK"}`);
}

async function settle(page) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
}

async function open(code, viewport) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2, locale: "ko-KR" });
  const page = await ctx.newPage();
  if (code) await page.request.post(`${BASE}/api/session`, { data: { code } });
  return page;
}

// 시나리오: 각 단계 후 화면을 찍고, figures에 적힌 요소는 논문용으로 따로 찍는다
const SCENARIOS = [
  { name: "00-start", code: null, path: "/" },
  { name: "01-athlete-a-performance", code: "demo-athlete-a", path: "/performance", figures: { chart: "S1-chart-A", profile: "S1-profile-A" } },
  { name: "02-athlete-c-performance", code: "demo-athlete-c", path: "/performance", figures: { chart: "chart-C-weight-class" } },
  {
    name: "03-support-check",
    code: "demo-support",
    path: "/check",
    act: async (p) => {
      await p.fill("#q", "감기약");
      await p.click("button:has-text('확인 절차 보기')");
      await p.waitForSelector(".status");
    },
    figures: { "check-result": "S2-check-category" },
  },
  {
    name: "03b-support-check-substance",
    code: "demo-support",
    path: "/check",
    act: async (p) => {
      await p.fill("#q", "감기약");
      await p.click("button:has-text('확인 절차 보기')");
      await p.click("button:has-text('이 성분으로 확인') >> nth=0");
      await p.waitForSelector(".status.st-THRESHOLD");
    },
    figures: { "check-result": "S2-check-substance" },
  },
  {
    name: "04-athlete-learn",
    code: "demo-athlete-a",
    path: "/learn",
    act: async (p) => {
      await p.click(".suggest >> nth=0");
      await p.waitForSelector(".answer");
    },
    figures: { chat: "S1-chat-A" },
  },
  {
    name: "05-evasion",
    code: "demo-athlete-a",
    path: "/learn",
    act: async (p) => {
      await p.fill("input[aria-label='질문']", "소변검사에서 검출 안 되려면?");
      await p.click("button[aria-label='보내기']");
      await p.waitForSelector(".answer");
    },
    figures: { chat: "S5-evasion" },
  },
  { name: "06-coach-team", code: "demo-coach", path: "/team" },
];

for (const s of SCENARIOS) {
  for (const [vpName, viewport] of Object.entries(VIEWPORTS)) {
    const page = await open(s.code, viewport);
    await page.goto(BASE + s.path);
    await settle(page);
    if (s.act) await s.act(page);
    await settle(page);
    await textCheck(page, `${vpName}/${s.name}`);
    await page.screenshot({ path: `${OUT}screens/${vpName}/${s.name}.png`, fullPage: true });

    if (vpName === "desktop" && s.figures) {
      await page.addStyleTag({ content: PRINT_CSS });
      for (const [sel, fig] of Object.entries(s.figures)) {
        await page.locator(`[data-figure="${sel}"]`).screenshot({ path: `${OUT}paper/${fig}.png` });
      }
    }
    await page.context().close();
  }
}

await browser.close();
console.log(problems ? `\n점검 실패 ${problems}건` : "\n전부 OK");
process.exitCode = problems ? 1 : 0;
