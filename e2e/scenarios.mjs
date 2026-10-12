// 테스트 시나리오(data/demo_examples.json)를 화면에서 하나씩 불러와 계산하고 기대 태그와 비교한다 (docs/TESTING.md).
//   BASE_URL=http://127.0.0.1:8101 node scenarios.mjs   # 합성 모델
//   BASE_URL=http://127.0.0.1:8102 node scenarios.mjs   # 연구진 RNN (private/models)
// 화면은 저장하지 않는다(실모델 결과가 레포에 남지 않도록). 불일치·가로 넘침이 있으면 종료 코드 1.
import { chromium } from "playwright-core";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:8101";
const browser = await chromium.launch({ channel: "chrome" });
let failed = 0;

for (const width of [1280, 390]) {
  const ctx = await browser.newContext({ viewport: { width, height: 800 }, locale: "ko-KR" });
  const page = await ctx.newPage();
  await page.request.post(`${BASE}/api/session`, { data: { code: "demo-athlete-a" } });
  await page.goto(`${BASE}/performance`);
  await page.click("[data-test=scenarios] summary");
  const ids = await page.$$eval("#scenario option", (o) => o.map((x) => x.value));
  for (const id of ids) {
    await page.selectOption("#scenario", id);
    await page.click("button:has-text('입력란에 불러오기')");
    await page.waitForFunction(() => document.querySelector("#birth-year")?.value);
    await page.click("button:has-text('교육 프로파일 만들기')");
    await page.waitForSelector("[data-test=scenario-result], .notice-caution[role=alert]");
    const warned = Boolean(await page.$(".notice-caution[role=alert]"));
    if (warned) await page.click("button:has-text('확인했어요')");
    await page.waitForSelector("[data-test=scenario-result]");
    const result = (await page.textContent("[data-test=scenario-result]")).trim();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    const ok = result.includes("결과와 일치") && !overflow;
    if (!ok) failed++;
    console.log(`${ok ? "OK  " : "FAIL"} @${width} ${id}${warned ? " (경고 확인 후)" : ""} ${result}${overflow ? " · 가로 넘침" : ""}`);
  }
  await ctx.close();
}
await browser.close();
console.log(failed ? `${failed}건 실패` : "모두 일치");
process.exit(failed ? 1 : 0);
