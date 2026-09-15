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

const MOCK_QUERY_RESPONSE = {
  answer: "### Audited Financial Performance Summary\n\nRevenue from operations and segment profitability for the evaluated periods demonstrate consistent margin resilience across domestic operations:\n\n| Financial Metric | FY 2023 (₹ Cr) | FY 2024 (₹ Cr) | YoY Growth (%) |\n| :--- | :--- | :--- | :--- |\n| Revenue from Operations | 5,124.80 | 5,892.40 | +14.98% |\n| Cost of Materials Consumed | 1,180.20 | 1,310.50 | +11.04% |\n| Employee Benefit Expenses | 982.40 | 1,094.20 | +11.38% |\n| Operating EBITDA Margin | 1,142.60 | 1,328.90 | +16.31% |\n| Net Profit After Tax (PAT) | 584.20 | 692.10 | +18.47% |\n\nAll financial figures have been mathematically cell-verified against audited disclosure matrices on page 48.",
  citations: [
    {
      marker: "[§1]",
      chunk_id: "chunk_jubilant_p48_01",
      doc_id: "doc_jubilant_2024",
      source_filename: "Jubilant_FoodWorks_FY24.pdf",
      company_name: "Jubilant FoodWorks",
      fiscal_year: "2024",
      page_start: 48,
      page_end: 48,
      excerpt: "| Financial Metric | FY 2023 (₹ Cr) | FY 2024 (₹ Cr) | YoY Growth (%) |\n| :--- | :--- | :--- | :--- |\n| Revenue from Operations | 5,124.80 | 5,892.40 | +14.98% |\n| Cost of Materials Consumed | 1,180.20 | 1,310.50 | +11.04% |\n| Employee Benefit Expenses | 982.40 | 1,094.20 | +11.38% |\n| Operating EBITDA Margin | 1,142.60 | 1,328.90 | +16.31% |\n| Net Profit After Tax (PAT) | 584.20 | 692.10 | +18.47% |",
      table_id: "table_0048_audited_pnl",
      risk_flag: false,
    },
  ],
  verification: {
    status: "verified",
    reason: "100% cell-level numeric grounding confirmed against audited statement of profit and loss (Table table_0048_audited_pnl).",
  },
  intent: "numeric",
};

async function main() {
  console.log("Launching Puppeteer for L'Écrin de Données verification...");
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
      if (req.method() === "OPTIONS") {
        req.respond({
          status: 200,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
          },
        });
        return;
      }

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
      } else if (url.includes("/ask")) {
        console.log("Intercepted /ask request! Returning mock luxury ledger payload...");
        req.respond({
          status: 200,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
          },
          contentType: "application/json",
          body: JSON.stringify(MOCK_QUERY_RESPONSE),
        });
      } else {
        req.continue();
      }
    });

    await page.goto("http://localhost:3000", { waitUntil: "networkidle0", timeout: 25000 });
    await new Promise((r) => setTimeout(r, 1500));

    // 1. Submit an inquiry to generate the luxury financial ledger response
    const textarea = await page.$("textarea");
    if (textarea) {
      await textarea.type("What was the audited revenue from operations and net profit margin for Jubilant FoodWorks in FY24?");
      const sendBtn = await page.$('[data-testid="send-query-button"]');
      if (sendBtn) {
        await sendBtn.click();
      }
    }

    console.log("Waiting for assistant message...");
    await page.waitForSelector('[data-testid="assistant-message"]', { timeout: 15000 });
    await new Promise((r) => setTimeout(r, 1500));

    // Capture Screenshot 1: Luxury Financial Ledger in Assistant Message
    const shot1Path = path.join(ARTIFACTS_DIR, "screenshot_ecrin_ledger_table.png");
    await page.screenshot({ path: shot1Path });
    console.log(`Saved screenshot 1 (Luxury Financial Ledger): ${shot1Path}`);

    // 2. Click the Citation Footnote Seal to open the Filing Inspector
    const chip = await page.$('[data-testid^="citation-chip-"]');
    if (chip) {
      console.log("Clicking footnote citation seal to open inspector...");
      await chip.click();
      await new Promise((r) => setTimeout(r, 1200));

      // Capture Screenshot 2: Filing Inspector with Ground Truth Matrix & Jeweler Tools
      const shot2Path = path.join(ARTIFACTS_DIR, "screenshot_ecrin_inspector_matrix.png");
      await page.screenshot({ path: shot2Path });
      console.log(`Saved screenshot 2 (Inspector Ground Truth Matrix): ${shot2Path}`);
    }
  } catch (err) {
    console.error("Error during L'Écrin de Données capture:", err);
  } finally {
    await browser.close();
    console.log("Done.");
  }
}

main();
