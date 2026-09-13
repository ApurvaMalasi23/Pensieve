const puppeteer = require("puppeteer-core");
const path = require("path");
const fs = require("fs");

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

  // Helper function to submit query
  async function submitQuery(queryText) {
    console.log(`Submitting query: "${queryText}"`);
    const inputSelector = "textarea";
    await page.waitForSelector(inputSelector);
    await page.type(inputSelector, queryText);
    const sendButton = '[data-testid="send-query-button"]';
    await page.click(sendButton);
    // Wait for response: wait until loading disappears
    console.log("Waiting for response...");
    await page.waitForSelector("text/Retrieving context", { timeout: 3000 }).catch(() => {});
    await page.waitForFunction(
      () => !document.body.innerText.includes("Retrieving context") && !document.body.innerText.includes("Retrieving tables"),
      { timeout: 45000 }
    );
    await new Promise((r) => setTimeout(r, 1200)); // Allow settle animation to finish
  }

  // 1. Submit Clean Numeric Question (Deposits)
  await submitQuery("What were total traditional bank deposits as of December 31, 2024?");
  const fileVerified = path.join(ARTIFACT_DIR, "screenshot_verified.png");
  await page.screenshot({ path: fileVerified });
  console.log("Captured:", fileVerified);

  // 2. Open Citation Modal
  console.log("Clicking citation chip...");
  const citationChip = await page.waitForSelector('[data-testid^="citation-chip-"]');
  if (citationChip) {
    await citationChip.click();
    await page.waitForSelector('[data-testid="citation-modal"]', { timeout: 5000 });
    await new Promise((r) => setTimeout(r, 600));
    const fileModal = path.join(ARTIFACT_DIR, "screenshot_citation_modal.png");
    await page.screenshot({ path: fileModal });
    console.log("Captured:", fileModal);

    // Close modal
    const closeBtn = await page.waitForSelector('button[title="Close modal"]');
    if (closeBtn) {
      await closeBtn.click();
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  // 3. Submit Flagged Table Question (Page 89)
  await submitQuery("What is the impact of a 400 basis point rate change on net interest income?");
  const fileFlagged = path.join(ARTIFACT_DIR, "screenshot_flagged.png");
  await page.screenshot({ path: fileFlagged });
  console.log("Captured:", fileFlagged);

  // 4. Open Upload Modal
  console.log("Opening Upload Modal...");
  const uploadBtn = await page.waitForSelector('[data-testid="upload-document-button"]');
  if (uploadBtn) {
    await uploadBtn.click();
    await page.waitForSelector('[data-testid="upload-modal"]');
    await new Promise((r) => setTimeout(r, 500));
    const fileUpload = path.join(ARTIFACT_DIR, "screenshot_upload_modal.png");
    await page.screenshot({ path: fileUpload });
    console.log("Captured:", fileUpload);

    // Close modal
    await page.keyboard.press("Escape");
    await new Promise((r) => setTimeout(r, 500));
  }

  console.log("All UI flows captured successfully.");
  await browser.close();
}

main().catch((err) => {
  console.error("Capture failed:", err);
  process.exit(1);
});
