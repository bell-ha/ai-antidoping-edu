import { chromium } from "playwright-core";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8000";
const OUT = new URL("../docs/figures/", import.meta.url).pathname;
const browser = await chromium.launch({ channel: "chrome" });

// 텍스트 Range 좌표로 겹침·가로 넘침 찾기
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
      if (el.closest("svg")) continue; // 차트 글자는 따로 봄
      const r = document.createRange();
      r.selectNodeContents(n);
      for (const b of r.getClientRects()) if (b.width > 1) rects.push({ t: n.textContent.trim().slice(0, 20), x: b.left, y: b.top + scrollY, w: b.width, h: b.height, fixed: !!el.closest(".tabbar,.topbar,.composer,.sheet-backdrop"), scroll: !!el.closest(".chips-scroll") });
    }
    const out = [];
    const vw = document.documentElement.clientWidth;
    for (const a of rects) if (!a.scroll && (a.x < -1 || a.x + a.w > vw + 1)) out.push(`넘침: "${a.t}"`);
    for (let i = 0; i < rects.length; i++)
      for (let j = i + 1; j < rects.length; j++) {
        const a = rects[i], b = rects[j];
        if (a.fixed !== b.fixed) continue;
        const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
        const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
        if (ox > 2 && oy > 4) out.push(`겹침: "${a.t}" / "${b.t}"`);
      }
    if (document.documentElement.scrollWidth > vw) out.push(`가로 스크롤 ${document.documentElement.scrollWidth}>${vw}`);
    return out;
  });
  console.log(`[${name}] ${issues.length ? issues.join(" | ") : "OK"}`);
}

async function shot(page, name) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await textCheck(page, name);
  // 전체 페이지 캡처에서는 fixed 요소가 캡처 시점 뷰포트 하단에 박히므로 흐름 안으로 되돌린다 (앱 코드는 그대로)
  await page.addStyleTag({ content: ".tabbar,.composer{position:static!important;transform:none!important} .main{padding-bottom:0!important} [style*='height: 76px']{display:none}" });
  await page.screenshot({ path: `${OUT}${name}.png`, fullPage: true });
  await page.screenshot({ path: `${OUT}${name}-viewport.png` });
}

async function as(code, viewport = { width: 390, height: 844 }) {
  const ctx = await browser.newContext({ viewport, deviceScaleFactor: 2, locale: "ko-KR" });
  const page = await ctx.newPage();
  await page.goto(BASE);
  if (code) {
    await page.request.post(`${BASE}/api/session`, { data: { code } });
    await page.goto(BASE);
  }
  return page;
}

let p = await as(null);
await shot(p, "00-start");

p = await as("demo-athlete-a");
await page_goto(p, "/performance");
await shot(p, "01-athlete-a-performance");

p = await as("demo-athlete-c");
await page_goto(p, "/performance");
await shot(p, "02-athlete-c-performance");

p = await as("demo-support");
await page_goto(p, "/check");
await p.fill("#q", "감기약");
await p.click("button:has-text('확인 절차 보기')");
try {
  await p.waitForSelector(".status", { timeout: 5000 });
} catch {
  console.log("[03-support-check] 판정 결과 없음 (조회표 작업 중)");
}
await shot(p, "03-support-check");
await p.click("button:has-text('이 성분으로 확인') >> nth=0");
await p.waitForSelector(".status.st-THRESHOLD");
await shot(p, "03b-support-check-substance");

p = await as("demo-athlete-a");
await page_goto(p, "/learn");
await p.click(".chips-scroll .chip >> nth=0");
await p.waitForSelector(".answer");
await shot(p, "04-athlete-learn");

p = await as("demo-athlete-a");
await page_goto(p, "/learn");
await p.fill("input[aria-label='질문']", "소변검사에서 검출 안 되려면?");
await p.click("button[aria-label='보내기']");
await p.waitForSelector(".answer");
await shot(p, "05-evasion");

p = await as("demo-coach");
await page_goto(p, "/team");
await shot(p, "06-coach-team");

p = await as("demo-athlete-a", { width: 1280, height: 800 });
await page_goto(p, "/performance");
await shot(p, "07-desktop");

await browser.close();

async function page_goto(page, path) {
  await page.goto(BASE + path);
}
