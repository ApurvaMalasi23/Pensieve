const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const ARTIFACT_DIR = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368";

async function main() {
  console.log("Launching local Chrome via puppeteer-core...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();

  console.log("Navigating to http://localhost:3000...");
  await page.goto("http://localhost:3000", { waitUntil: "networkidle0" });
  await new Promise((r) => setTimeout(r, 1200));

  // 1. Capture Main Screen
  const fileMain = path.join(ARTIFACT_DIR, "screenshot_rich_black_main.png");
  await page.screenshot({ path: fileMain });
  console.log("Captured:", fileMain);

  // 2. Open Delete Confirmation Dialog on a filing card
  console.log("Testing delete affordance...");
  const firstCard = await page.waitForSelector('[data-testid^="document-item-"]');
  if (firstCard) {
    await firstCard.hover();
    await new Promise((r) => setTimeout(r, 400));

    const deleteBtn = await page.waitForSelector('[data-testid^="delete-doc-button-"]');
    if (deleteBtn) {
      await deleteBtn.click();
      await page.waitForSelector('[data-testid="delete-confirmation-dialog"]');
      await new Promise((r) => setTimeout(r, 500));

      const fileDelete = path.join(ARTIFACT_DIR, "screenshot_rich_black_delete_dialog.png");
      await page.screenshot({ path: fileDelete });
      console.log("Captured:", fileDelete);

      // Close modal using Escape
      await page.keyboard.press("Escape");
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  // 3. Submit Clean Numeric Question (Deposits) by pressing Enter in textarea
  console.log("Submitting numeric grounding inquiry...");
  const inputSelector = "textarea";
  await page.waitForSelector(inputSelector);
  await page.click(inputSelector);
  await page.type(inputSelector, "What were total traditional bank deposits as of December 31, 2024?");
  await new Promise((r) => setTimeout(r, 300));
  await page.keyboard.press("Enter");

  console.log("Waiting for answer and verification badge...");
  await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 45000 });
  await page.waitForSelector('[data-testid="verification-badge-verified"]', { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1200)); // Allow settle animation

  const fileVerified = path.join(ARTIFACT_DIR, "screenshot_rich_black_verified.png");
  await page.screenshot({ path: fileVerified });
  console.log("Captured:", fileVerified);

  // 4. Open Citation Modal
  console.log("Opening Citation Modal...");
  const citationChip = await page.waitForSelector('[data-testid^="citation-chip-"]', { timeout: 10000 });
  if (citationChip) {
    await citationChip.click();
    await page.waitForSelector('[data-testid="citation-modal"]', { timeout: 5000 });
    await new Promise((r) => setTimeout(r, 800));

    const fileCitation = path.join(ARTIFACT_DIR, "screenshot_rich_black_citation.png");
    await page.screenshot({ path: fileCitation });
    console.log("Captured:", fileCitation);

    // Close modal via Escape
    await page.keyboard.press("Escape");
    await new Promise((r) => setTimeout(r, 600));
  }

  // 5. Submit Comparison Query
  console.log("Submitting comparison query...");
  await page.click(inputSelector);
  await page.type(inputSelector, "Compare total revenue or income of Republic Bancorp in 2024 and Lux Industries in 2025-26");
  await new Promise((r) => setTimeout(r, 300));
  await page.keyboard.press("Enter");

  console.log("Waiting for comparison response...");
  await page.waitForSelector('[data-testid="comparison-view"]', { timeout: 60000 });
  await new Promise((r) => setTimeout(r, 1500));

  const fileComparison = path.join(ARTIFACT_DIR, "screenshot_rich_black_comparison.png");
  await page.screenshot({ path: fileComparison });
  console.log("Captured:", fileComparison);

  console.log("All rich black screens captured successfully!");
  await browser.close();
}

main().catch((err) => {
  console.error("Capture script failed:", err);
  process.exit(1);
});
