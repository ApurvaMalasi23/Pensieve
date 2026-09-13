const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const ARTIFACTS_DIR = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368";

async function main() {
  console.log("Launching Puppeteer for Palette 2 Proof Deck capture...");
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

    // Select Jubilant
    const docItems = await page.$$('[data-testid^="document-item-"]');
    if (docItems.length > 0) {
      await docItems[0].click();
      await new Promise((r) => setTimeout(r, 1000));
    }

    // Click Inquiry 02 (Numeric Grounding for Jubilant)
    const inquiryBtns = await page.$$('button[type="button"].group.relative');
    if (inquiryBtns.length > 1) {
      console.log("Clicking Numeric Grounding inquiry...");
      await inquiryBtns[1].click();
      await new Promise((r) => setTimeout(r, 400));
    }

    // Submit query
    const sendBtn = await page.$('[data-testid="send-query-button"]');
    if (sendBtn) {
      console.log("Submitting numeric query...");
      await sendBtn.click();

      console.log("Waiting for verified assistant response with 65s timeout...");
      await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 65000 });
      await new Promise((r) => setTimeout(r, 2000));

      // Expand proof deck if button exists
      const inspectProofBtn = await page.$('[data-testid="inspect-proof-button"]');
      if (inspectProofBtn) {
        console.log("Expanding verified proof deck...");
        await inspectProofBtn.click();
        await new Promise((r) => setTimeout(r, 1200));
      }

      const proofPath = path.join(ARTIFACTS_DIR, "screenshot_palette2_proof_deck.png");
      await page.screenshot({ path: proofPath });
      console.log(`Saved screenshot 3 (Verified Proof Deck): ${proofPath}`);
    }
  } finally {
    await browser.close();
    console.log("Proof capture complete.");
  }
}

main().catch((err) => {
  console.error("Proof capture failed:", err);
  process.exit(1);
});
