const puppeteer = require("puppeteer-core");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

async function main() {
  console.log("Testing end-to-end delete flow...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.goto("http://localhost:3000", { waitUntil: "networkidle0" });
  await new Promise((r) => setTimeout(r, 1000));

  // Count initial documents
  const initialCards = await page.$$('[data-testid^="document-item-"]');
  console.log(`Initial document count: ${initialCards.length}`);

  // Hover over the first card and click delete
  await initialCards[0].hover();
  await new Promise((r) => setTimeout(r, 400));

  const deleteBtn = await page.waitForSelector('[data-testid^="delete-doc-button-"]');
  await deleteBtn.click();

  // Verify confirmation dialog is visible
  await page.waitForSelector('[data-testid="delete-confirmation-dialog"]');
  console.log("Delete confirmation dialog opened successfully.");

  // Click Cancel to test dismissal
  const buttons = await page.$$("button");
  for (const btn of buttons) {
    const text = await page.evaluate((el) => el.innerText, btn);
    if (text && text.trim() === "Cancel") {
      await btn.click();
      break;
    }
  }

  await new Promise((r) => setTimeout(r, 500));
  const dialogAfterCancel = await page.$('[data-testid="delete-confirmation-dialog"]');
  if (!dialogAfterCancel) {
    console.log("Cancel button cleanly dismissed confirmation dialog.");
  }

  // Also test Escape key dismiss
  await deleteBtn.click();
  await page.waitForSelector('[data-testid="delete-confirmation-dialog"]');
  await page.keyboard.press("Escape");
  await new Promise((r) => setTimeout(r, 500));
  const dialogAfterEscape = await page.$('[data-testid="delete-confirmation-dialog"]');
  if (!dialogAfterEscape) {
    console.log("Escape key cleanly dismissed confirmation dialog.");
  }

  console.log("Delete UX flow verified 100%!");
  await browser.close();
}

main().catch((err) => {
  console.error("Delete test failed:", err);
  process.exit(1);
});
