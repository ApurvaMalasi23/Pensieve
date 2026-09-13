const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const ARTIFACTS_DIR = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368";

async function main() {
  console.log("Launching Puppeteer for Palette 2 verification...");
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

    // 1. Capture Hero Screen (Natural Titanium & Hermès Amber)
    const heroPath = path.join(ARTIFACTS_DIR, "screenshot_palette2_hero.png");
    await page.screenshot({ path: heroPath });
    console.log(`Saved screenshot 1 (Hero): ${heroPath}`);

    // 2. Select a Document in Catalog (e.g. Jubilant Ingrevia)
    const docItems = await page.$$('[data-testid^="document-item-"]');
    console.log(`Found ${docItems.length} catalog document items.`);
    if (docItems.length > 0) {
      await docItems[0].click();
      await new Promise((r) => setTimeout(r, 1200));

      // Type in search bar to show focused amber aura
      const searchInput = await page.$('[data-testid="search-catalog-input"]');
      if (searchInput) {
        await searchInput.focus();
        await searchInput.type("Jubilant");
        await new Promise((r) => setTimeout(r, 800));
      }

      const catalogPath = path.join(ARTIFACTS_DIR, "screenshot_palette2_selected_catalog.png");
      await page.screenshot({ path: catalogPath });
      console.log(`Saved screenshot 2 (Catalog Selected & Search): ${catalogPath}`);
    }

    // 3. Clear search and click an inquiry to generate grounded verification answer
    const clearSearchBtn = await page.$('button[data-testid="search-catalog-input"] + button, div.relative button');
    if (clearSearchBtn) {
      await clearSearchBtn.click();
      await new Promise((r) => setTimeout(r, 500));
    }

    // Click the first inquiry
    const inquiryBtns = await page.$$('button[type="button"].group.relative');
    console.log(`Found ${inquiryBtns.length} inquiry buttons.`);
    if (inquiryBtns.length > 0) {
      console.log("Clicking inquiry button...");
      await inquiryBtns[0].click();
      await new Promise((r) => setTimeout(r, 300));

      // Click Send button
      const sendBtn = await page.$('[data-testid="send-query-button"]');
      if (sendBtn) {
        console.log("Clicking send button...");
        await sendBtn.click();

        // Wait for response to appear (up to 30s)
        console.log("Waiting for verified assistant response...");
        await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 35000 });
        await new Promise((r) => setTimeout(r, 2000));

        // Click "Inspect Proof" button on the verification badge if present
        const inspectProofBtn = await page.$('[data-testid="inspect-proof-button"]');
        if (inspectProofBtn) {
          console.log("Expanding verified proof deck...");
          await inspectProofBtn.click();
          await new Promise((r) => setTimeout(r, 1000));
        }

        const proofPath = path.join(ARTIFACTS_DIR, "screenshot_palette2_proof_deck.png");
        await page.screenshot({ path: proofPath });
        console.log(`Saved screenshot 3 (Verified Proof Deck): ${proofPath}`);
      }
    }
  } finally {
    await browser.close();
    console.log("Puppeteer run complete.");
  }
}

main().catch((err) => {
  console.error("Puppeteer capture failed:", err);
  process.exit(1);
});
