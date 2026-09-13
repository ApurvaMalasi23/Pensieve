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

  // 1. Open Command Palette via Header trigger button
  const triggerBtn = await page.$('[data-testid="command-palette-trigger"]');
  if (triggerBtn) {
    console.log("Clicking command palette trigger...");
    await triggerBtn.click();
    await page.waitForSelector('[data-testid="command-palette-modal"]', { timeout: 5000 });
    await new Promise((r) => setTimeout(r, 500));

    const filePalette = path.join(ARTIFACT_DIR, "screenshot_p2_command_palette.png");
    await page.screenshot({ path: filePalette });
    console.log("Captured:", filePalette);

    // 2. Type search filter
    console.log("Typing filter query in command palette...");
    await page.type('[data-testid="command-palette-input"]', "Republic");
    await new Promise((r) => setTimeout(r, 400));

    const fileFiltered = path.join(ARTIFACT_DIR, "screenshot_p2_command_palette_filtered.png");
    await page.screenshot({ path: fileFiltered });
    console.log("Captured:", fileFiltered);

    // 3. Press Escape to close palette
    await page.keyboard.press("Escape");
    await new Promise((r) => setTimeout(r, 400));
  } else {
    console.log("Command palette trigger button not found");
  }

  // 4. Collapse sidebar
  const collapseBtn = await page.$('[data-testid="collapse-sidebar-button"]');
  if (collapseBtn) {
    console.log("Collapsing sidebar...");
    await collapseBtn.click();
    await page.waitForSelector('[data-testid="document-panel-collapsed"]', { timeout: 5000 });
    await new Promise((r) => setTimeout(r, 600));

    const fileCollapsed = path.join(ARTIFACT_DIR, "screenshot_p2_sidebar_collapsed.png");
    await page.screenshot({ path: fileCollapsed });
    console.log("Captured:", fileCollapsed);

    // 5. Expand sidebar again
    const expandBtn = await page.$('[data-testid="expand-sidebar-button"]');
    if (expandBtn) {
      console.log("Expanding sidebar back...");
      await expandBtn.click();
      await page.waitForSelector('[data-testid="document-panel"]', { timeout: 5000 });
      await new Promise((r) => setTimeout(r, 400));
    }
  } else {
    console.log("Collapse button not found");
  }

  await browser.close();
  console.log("Priority 2 test completed successfully.");
}

main().catch((err) => {
  console.error("Error in P2 test:", err);
  process.exit(1);
});
