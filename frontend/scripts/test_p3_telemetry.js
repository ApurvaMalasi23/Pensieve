const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const ARTIFACT_DIR = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368";

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.goto("http://localhost:3000", { waitUntil: "networkidle0" });
  await new Promise((r) => setTimeout(r, 1500));

  // 1. Click recommended inquiry 01
  const buttons = await page.$$("button");
  for (const b of buttons) {
    const txt = await page.evaluate((el) => el.textContent, b);
    if (txt && txt.includes("What are Republic Bancorp's primary lending activities")) {
      console.log("Clicking inquiry button...");
      await b.click();
      break;
    }
  }

  await new Promise((r) => setTimeout(r, 600));

  // 2. Submit query
  console.log("Clicking send query button...");
  await page.click('[data-testid="send-query-button"]');

  // 3. Immediately wait for thinking-telemetry component
  console.log("Waiting for thinking telemetry pipeline to mount...");
  await page.waitForSelector('[data-testid="thinking-telemetry"]', { timeout: 8000 });
  await new Promise((r) => setTimeout(r, 2200)); // Allow stopwatch to tick & stage to progress

  const fileTelemetry = path.join(ARTIFACT_DIR, "screenshot_p3_thinking_telemetry.png");
  await page.screenshot({ path: fileTelemetry });
  console.log("Captured:", fileTelemetry);

  // 4. Wait for final assistant response to arrive and settle
  console.log("Waiting for response to complete and settle...");
  await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 45000 });
  await new Promise((r) => setTimeout(r, 1200));

  const fileSettled = path.join(ARTIFACT_DIR, "screenshot_p3_final_settled.png");
  await page.screenshot({ path: fileSettled });
  console.log("Captured:", fileSettled);

  await browser.close();
  console.log("Priority 3 test completed successfully.");
}

main().catch((err) => {
  console.error("Error in P3 test:", err);
  process.exit(1);
});
