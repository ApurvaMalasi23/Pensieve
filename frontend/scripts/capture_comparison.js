const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const ARTIFACT_DIR = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368";

async function main() {
  console.log("Launching local Chrome...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  page.on("console", (msg) => console.log("BROWSER CONSOLE:", msg.text()));
  page.on("pageerror", (err) => console.log("BROWSER ERROR:", err.message));

  console.log("Navigating to http://localhost:3000...");
  await page.goto("http://localhost:3000", { waitUntil: "networkidle0" });
  await new Promise((r) => setTimeout(r, 1000));

  // Click on the 4th recommended inquiry directly: Cross Comparison
  console.log("Clicking inquiry row 04 (Cross Comparison)...");
  const buttons = await page.$$("button");
  for (const btn of buttons) {
    const text = await page.evaluate((el) => el.innerText, btn);
    if (text && text.includes("Cross Comparison")) {
      await btn.click();
      break;
    }
  }

  await new Promise((r) => setTimeout(r, 500));
  console.log("Pressing Enter to submit comparison inquiry...");
  await page.keyboard.press("Enter");

  console.log("Waiting for comparison response...");
  await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 60000 });
  await new Promise((r) => setTimeout(r, 1500));

  const fileComparison = path.join(ARTIFACT_DIR, "screenshot_rich_black_comparison.png");
  await page.screenshot({ path: fileComparison, fullPage: false });
  console.log("Captured:", fileComparison);

  await browser.close();
}

main().catch((err) => {
  console.error("Comparison capture failed:", err);
  process.exit(1);
});
