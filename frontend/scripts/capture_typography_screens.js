const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const ARTIFACTS_DIR = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368";

async function main() {
  console.log("Launching Puppeteer for System 1 Typography verification...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });

  try {
    const page = await browser.newPage();
    await page.goto("http://localhost:3000", { waitUntil: "networkidle0", timeout: 25000 });
    await new Promise((r) => setTimeout(r, 2000));

    // 1. Capture Hero Screen (System 1: Geist Sans ExtraBold + JetBrains Mono)
    const heroPath = path.join(ARTIFACTS_DIR, "screenshot_system1_hero.png");
    await page.screenshot({ path: heroPath });
    console.log(`Saved screenshot 1 (Hero System 1): ${heroPath}`);

    // 2. Select a Document in Catalog to show dynamic technical labels
    const docItems = await page.$$('[data-testid^="document-item-"]');
    if (docItems.length > 0) {
      await docItems[0].click();
      await new Promise((r) => setTimeout(r, 1200));

      const catalogPath = path.join(ARTIFACTS_DIR, "screenshot_system1_catalog.png");
      await page.screenshot({ path: catalogPath });
      console.log(`Saved screenshot 2 (Catalog System 1): ${catalogPath}`);
    }

    // 3. Click first inquiry and execute to show JetBrains Mono tabular figures
    const inquiryBtns = await page.$$('button[type="button"].group.relative');
    if (inquiryBtns.length > 0) {
      await inquiryBtns[0].click();
      await new Promise((r) => setTimeout(r, 400));

      const sendBtn = await page.$('[data-testid="send-query-button"]');
      if (sendBtn) {
        await sendBtn.click();
        console.log("Waiting for response with JetBrains Mono numbers...");
        await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 35000 });
        await new Promise((r) => setTimeout(r, 2000));

        const proofPath = path.join(ARTIFACTS_DIR, "screenshot_system1_proof.png");
        await page.screenshot({ path: proofPath });
        console.log(`Saved screenshot 3 (Proof Deck System 1): ${proofPath}`);
      }
    }
  } catch (err) {
    console.error("Puppeteer verification failed:", err);
  } finally {
    await browser.close();
    console.log("Puppeteer finished.");
  }
}

main();
