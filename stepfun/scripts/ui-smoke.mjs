import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
const evidence = [];
for (const [channel, disabled] of [
  ["chrome", false],
  ["msedge", true],
]) {
  const browser = await chromium.launch({
    channel,
    headless: true,
    args: disabled ? ["--disable-gpu", "--disable-software-rasterizer"] : ["--enable-unsafe-webgpu"],
  });
  const page = await browser.newPage();
  const requests = [];
  await page.route("**/*", (r) => {
    if (new URL(r.request().url()).hostname !== "127.0.0.1") {
      requests.push(r.request().url());
      return r.abort();
    }
    return r.continue();
  });
  await page.goto("http://127.0.0.1:5173");
  await page.locator("#kb").fill(`ui_${channel}_${Date.now()}`);
  await page.locator("#connect").click();
  await page.waitForFunction(
    () => document.querySelector("#status").textContent === "知识库已打开",
  );
  await page
    .locator("#text")
    .fill(
      "Zephyrquartz browser UI verification. Local inference protects privacy and seekdb performs database hybrid search.",
    );
  await page.locator("#import").click();
  await page.waitForFunction(
    () =>
      document.querySelector("#status").textContent.includes("索引刷新完成"),
    null,
    { timeout: 90000 },
  );
  await page.locator("#query").fill("Zephyrquartz local inference privacy");
  await page.locator("#search button").click();
  await page.waitForSelector(".result", { timeout: 90000 });
  const backend = await page.locator("#backend").textContent();
  if (disabled && !backend.includes("WASM"))
    throw new Error("Automatic fallback failed");
  evidence.push({
    channel,
    browser: browser.version(),
    webgpuDisabled: disabled,
    backend,
    requests,
    result: await page.locator(".result").first().innerText(),
  });
  await page.screenshot({ path: `evidence/ui-${channel}.png`, fullPage: true });
  await browser.close();
}
await writeFile("evidence/ui-smoke.json", JSON.stringify(evidence, null, 2));
console.log(evidence);
