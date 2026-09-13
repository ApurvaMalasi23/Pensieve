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

  // Click on inquiry 02 (Numeric Grounding)
  const buttons = await page.$$("button");
  for (const b of buttons) {
    const txt = await page.evaluate((el) => el.textContent, b);
    if (txt && txt.includes("What were total traditional bank deposits")) {
      console.log("Clicking numeric inquiry button...");
      await b.click();
      break;
    }
  }

  await new Promise((r) => setTimeout(r, 800));

  // Submit the inquiry form via data-testid send-query-button
  console.log("Clicking send query button...");
  await page.click('[data-testid="send-query-button"]');

  // Wait for assistant response to render
  await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 60000 });
  await new Promise((r) => setTimeout(r, 2000));

  // Find and click the 'Inspect Proof' button
  const proofBtn = await page.$('[data-testid="inspect-proof-button"]');
  if (proofBtn) {
    console.log("Clicking Inspect Proof button...");
    await proofBtn.click();
    await new Promise((r) => setTimeout(r, 800));
  } else {
    console.log("Inspect proof button not found");
  }

  const fileProof = path.join(ARTIFACT_DIR, "screenshot_p1_verified_proof.png");
  await page.screenshot({ path: fileProof });
  console.log("Captured:", fileProof);

  // Now hover over the first citation chip to trigger popover
  const citationChip = await page.$('[data-testid^="citation-chip-"]');
  if (citationChip) {
    console.log("Hovering over citation chip...");
    await citationChip.hover();
    await new Promise((r) => setTimeout(r, 800));

    const filePopover = path.join(ARTIFACT_DIR, "screenshot_p1_citation_popover.png");
    await page.screenshot({ path: filePopover });
    console.log("Captured:", filePopover);
  } else {
    console.log("Citation chip not found");
  }

  await browser.close();
  console.log("Completed successfully.");
}

main().catch((err) => {
  console.error("Error running test:", err);
  process.exit(1);
});
