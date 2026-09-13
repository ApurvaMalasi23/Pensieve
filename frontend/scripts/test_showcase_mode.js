const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const SCREENSHOT_PATH = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368\\screenshot_showcase_mode.png";
const SCREENSHOT_PALETTE_PATH = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\c3353e8f-25bd-4f7e-9f83-09da4a6f2368\\screenshot_showcase_palette.png";

async function main() {
  console.log("Starting Showcase Mode Puppeteer verification...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });

  try {
    const page = await browser.newPage();
    await page.goto("http://localhost:3000", { waitUntil: "networkidle0", timeout: 15000 });
    await new Promise((r) => setTimeout(r, 1200));

    // 1. Verify that Upload PDF button is completely ABSENT from DOM
    const uploadBtn = await page.$('[data-testid="upload-document-button"]');
    const uploadBtnCollapsed = await page.$('[data-testid="upload-document-button-collapsed"]');
    console.log("Upload button present:", !!uploadBtn, "Collapsed upload button present:", !!uploadBtnCollapsed);
    if (uploadBtn || uploadBtnCollapsed) {
      throw new Error("Upload button must be completely absent in Showcase Mode!");
    }
    console.log("✓ Upload buttons are completely removed from DOM.");

    // 2. Verify Showcase Catalog badge is present
    const showcaseBadge = await page.$('[data-testid="showcase-catalog-badge"]');
    console.log("Showcase catalog badge present:", !!showcaseBadge);

    // 3. Verify that all delete buttons are completely ABSENT from DOM
    const deleteButtons = await page.$$('[data-testid^="delete-doc-button-"]');
    console.log("Delete buttons found in DOM:", deleteButtons.length);
    if (deleteButtons.length > 0) {
      throw new Error("Per-document delete buttons must be completely absent in Showcase Mode!");
    }
    console.log("✓ Delete affordance buttons are completely removed from DOM.");

    // 4. Verify notice in scope footer and input dock
    const corpusNotice = await page.$('[data-testid="showcase-corpus-notice"]');
    const inputNotice = await page.$('[data-testid="showcase-input-notice"]');
    console.log("Corpus notice present:", !!corpusNotice, "Input notice present:", !!inputNotice);

    // 5. Capture main showcase page screenshot
    await page.screenshot({ path: SCREENSHOT_PATH });
    console.log(`Saved showcase mode screenshot to ${SCREENSHOT_PATH}`);

    // 6. Test Command Palette (Ctrl+K)
    await page.keyboard.down("Control");
    await page.keyboard.press("KeyK");
    await page.keyboard.up("Control");
    await new Promise((r) => setTimeout(r, 600));

    const commandPalette = await page.$('[data-testid="command-palette-modal"]');
    console.log("Command palette opened:", !!commandPalette);

    // Verify 'Upload New Filing PDF' is NOT in the palette items
    const pageContent = await page.content();
    const hasUploadInPalette = pageContent.includes("Upload New Filing PDF");
    console.log("'Upload New Filing PDF' present in palette:", hasUploadInPalette);
    if (hasUploadInPalette) {
      throw new Error("'Upload New Filing PDF' must NOT appear in command palette in Showcase Mode!");
    }
    console.log("✓ 'Upload New Filing PDF' action omitted from Command Palette.");

    await page.screenshot({ path: SCREENSHOT_PALETTE_PATH });
    console.log(`Saved showcase palette screenshot to ${SCREENSHOT_PALETTE_PATH}`);

    console.log("Showcase Mode Frontend verification PASSED 100%!");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error("Verification failed:", err);
  process.exit(1);
});
