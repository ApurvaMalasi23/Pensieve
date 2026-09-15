const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const ARTIFACTS_DIR = "C:\\Users\\apurv\\.gemini\\antigravity-ide\\brain\\acc0aeec-2958-460c-9b7b-94476ffd9e5b";

const MOCK_HEALTH = {
  status: "ok",
  qdrant_connected: true,
  collection: "financial_filings",
  points_count: 5320,
  active_generation_model: "gemini-2.5-pro",
  showcase_mode: true,
};

const MOCK_DOCUMENTS = [
  {
    doc_id: "doc_jubilant_2024",
    company_name: "Jubilant FoodWorks",
    fiscal_year: "2024",
    reporting_period_type: "annual",
    num_pages: 142,
    narrative_chunks: 312,
    table_chunks: 48,
    table_chunks_flagged: 0,
  },
  {
    doc_id: "doc_ravindra_2024",
    company_name: "Ravindra Energy",
    fiscal_year: "2024",
    reporting_period_type: "annual",
    num_pages: 88,
    narrative_chunks: 194,
    table_chunks: 32,
    table_chunks_flagged: 0,
  },
  {
    doc_id: "doc_republic_2024",
    company_name: "Republic Bancorp",
    fiscal_year: "2024",
    reporting_period_type: "annual",
    num_pages: 176,
    narrative_chunks: 420,
    table_chunks: 64,
    table_chunks_flagged: 2,
  },
  {
    doc_id: "doc_lux_2026",
    company_name: "Lux Industries",
    fiscal_year: "2026",
    reporting_period_type: "annual",
    num_pages: 110,
    narrative_chunks: 260,
    table_chunks: 40,
    table_chunks_flagged: 0,
  },
  {
    doc_id: "doc_ntpc_2024",
    company_name: "NTPC Green Energy",
    fiscal_year: "2024",
    reporting_period_type: "annual",
    num_pages: 198,
    narrative_chunks: 480,
    table_chunks: 72,
    table_chunks_flagged: 0,
  },
];

async function main() {
  console.log("Launching Puppeteer for L'Épure Architecturale screenshots...");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1440,900"],
    defaultViewport: { width: 1440, height: 900 },
  });

  try {
    const page = await browser.newPage();
    await page.setRequestInterception(true);

    page.on("request", (req) => {
      const url = req.url();
      if (url.includes("/health")) {
        req.respond({
          status: 200,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
          },
          contentType: "application/json",
          body: JSON.stringify(MOCK_HEALTH),
        });
      } else if (url.includes("/documents")) {
        req.respond({
          status: 200,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
          },
          contentType: "application/json",
          body: JSON.stringify(MOCK_DOCUMENTS),
        });
      } else {
        req.continue();
      }
    });

    await page.goto("http://localhost:3000", { waitUntil: "networkidle0", timeout: 25000 });
    await new Promise((r) => setTimeout(r, 2000));

    // Screenshot 1: Overview with Archival Catalog Ledger, Gossamer Hairlines & French Hero
    const shot1Path = path.join(ARTIFACTS_DIR, "screenshot_epure_architecturale.png");
    await page.screenshot({ path: shot1Path });
    console.log(`Saved screenshot 1 (Catalog Ledger & Hero): ${shot1Path}`);

    // Click third document item (Republic Bancorp with risk audit indicator)
    const docItems = await page.$$('[data-testid^="document-item-"]');
    console.log(`Found ${docItems.length} catalog items.`);
    if (docItems.length > 2) {
      console.log("Selecting Republic Bancorp filing...");
      await docItems[2].click();
      await new Promise((r) => setTimeout(r, 1200));
    }

    // Focus on the input dock to reveal the acoustic frosted monolith focus halo
    const textarea = await page.$("textarea");
    if (textarea) {
      await textarea.focus();
      await new Promise((r) => setTimeout(r, 600));
    }

    const shot2Path = path.join(ARTIFACTS_DIR, "screenshot_epure_scoped_dock.png");
    await page.screenshot({ path: shot2Path });
    console.log(`Saved screenshot 2 (Scoped & Focused Dock): ${shot2Path}`);
  } catch (err) {
    console.error("Error capturing screenshots:", err);
  } finally {
    await browser.close();
    console.log("Done.");
  }
}

main();
