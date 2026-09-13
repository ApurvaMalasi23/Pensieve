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
  await new Promise((r) => setTimeout(r, 1000));

  // Focus the input textarea directly
  const textarea = await page.waitForSelector("textarea");
  await textarea.click();
  await new Promise((r) => setTimeout(r, 500));

  // Capture full page
  const fileFull = path.join(ARTIFACT_DIR, "screenshot_apple_hero.png");
  await page.screenshot({ path: fileFull });
  console.log("Captured full page with focused input:", fileFull);

  // Also capture a crop of the input bar specifically
  const formElement = await page.$("form");
  if (formElement) {
    const fileBar = path.join(ARTIFACT_DIR, "screenshot_input_focused.png");
    await formElement.screenshot({ path: fileBar });
    console.log("Captured focused bar:", fileBar);
  }

  await browser.close();
}

main().catch((err) => {
  console.error("Focus capture failed:", err);
  process.exit(1);
});
