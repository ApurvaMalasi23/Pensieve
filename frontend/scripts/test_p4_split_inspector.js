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

  // 1. Click recommended inquiry 02
  const buttons = await page.$$("button");
  for (const b of buttons) {
    const txt = await page.evaluate((el) => el.textContent, b);
    if (txt && txt.includes("What were total traditional bank deposits")) {
      console.log("Clicking numeric inquiry button...");
      await b.click();
      break;
    }
  }

  await new Promise((r) => setTimeout(r, 600));

  // 2. Submit query
  console.log("Clicking send query button...");
  await page.click('[data-testid="send-query-button"]');

  // 3. Wait for final assistant response to arrive and settle
  console.log("Waiting for response to complete and settle...");
  await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 45000 });
  await new Promise((r) => setTimeout(r, 1500));

  // 4. Click citation chip to dock the Split Inspector on the right
  const citationChip = await page.$('[data-testid^="citation-chip-"]');
  if (citationChip) {
    console.log("Clicking citation chip to open Split Inspector...");
    await citationChip.click();
    await page.waitForSelector('[data-testid="filing-inspector-pane"]', { timeout: 6000 });
    await new Promise((r) => setTimeout(r, 800));

    // Capture side-by-side Table view
    const fileSplitTable = path.join(ARTIFACT_DIR, "screenshot_p4_split_inspector_table.png");
    await page.screenshot({ path: fileSplitTable });
    console.log("Captured:", fileSplitTable);

    // 5. Switch to PDF Bounding Box tab
    console.log("Switching to PDF BBox tab...");
    await page.click('[data-testid="tab-bbox-view"]');
    await new Promise((r) => setTimeout(r, 600));

    const fileSplitBBox = path.join(ARTIFACT_DIR, "screenshot_p4_split_inspector_bbox.png");
    await page.screenshot({ path: fileSplitBBox });
    console.log("Captured:", fileSplitBBox);

    // 6. Test Excel TSV copy button
    console.log("Clicking Copy TSV (Excel) button...");
    await page.click('[data-testid="copy-tsv-button"]');
    await new Promise((r) => setTimeout(r, 400));

    // 7. Toggle Fullscreen mode
    console.log("Toggling inspector fullscreen...");
    await page.click('[data-testid="toggle-inspector-fullscreen"]');
    await new Promise((r) => setTimeout(r, 600));

    const fileFullscreen = path.join(ARTIFACT_DIR, "screenshot_p4_inspector_fullscreen.png");
    await page.screenshot({ path: fileFullscreen });
    console.log("Captured:", fileFullscreen);

    // 8. Press Escape to dismiss
    console.log("Dismissing inspector via Escape...");
    await page.keyboard.press("Escape");
    await new Promise((r) => setTimeout(r, 400));
  } else {
    console.log("Citation chip not found");
  }

  await browser.close();
  console.log("Priority 4 test completed successfully.");
}

main().catch((err) => {
  console.error("Error in P4 test:", err);
  process.exit(1);
});
