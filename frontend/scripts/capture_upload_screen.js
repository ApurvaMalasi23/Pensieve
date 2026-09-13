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
  await new Promise((r) => setTimeout(r, 1000));

  const uploadBtn = await page.waitForSelector('[data-testid="upload-document-button"]');
  await uploadBtn.click();
  await page.waitForSelector('[data-testid="upload-modal"]');
  await new Promise((r) => setTimeout(r, 600));

  const fileUpload = path.join(ARTIFACT_DIR, "screenshot_rich_black_upload_modal.png");
  await page.screenshot({ path: fileUpload });
  console.log("Captured:", fileUpload);

  await browser.close();
}

main().catch((err) => {
  console.error("Upload modal capture failed:", err);
  process.exit(1);
});
