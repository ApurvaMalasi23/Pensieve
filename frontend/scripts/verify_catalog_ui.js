const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const SCREENSHOT_PATH = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368\\screenshot_5_docs_catalog.png";

async function main() {
  console.log("Connecting to Chrome and navigating to http://localhost:3000 ...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });

  try {
    const page = await browser.newPage();
    await page.goto("http://localhost:3000", { waitUntil: "networkidle0", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 2000));

    // Get all document names displayed
    const docTitles = await page.$$eval('[data-testid^="document-item-"]', (els) =>
      els.map((el) => {
        const titleEl = el.querySelector("h4");
        return titleEl ? titleEl.innerText.trim() : el.innerText.trim();
      })
    );

    console.log(`Visible Document Cards Count: ${docTitles.length}`);
    docTitles.forEach((t, i) => console.log(`  ${i + 1}. ${t}`));

    // Check header status badge
    const headerStatus = await page.$eval("header", (el) => el.innerText);
    console.log("Header status text includes Operational:", headerStatus.includes("Operational"));

    await page.screenshot({ path: SCREENSHOT_PATH });
    console.log(`Saved screenshot to: ${SCREENSHOT_PATH}`);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("Verification failed:", err);
  process.exit(1);
});
