import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = "C:/Users/ADITYA/.gemini/antigravity/brain/70d2ebf3-dd7a-4f49-ad9c-fb5b2b7a4bb1/screenshots";

test.describe("Mock PLM Web Application - Core User Flows", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to base URL
    await page.goto("http://127.0.0.1:5173/");
    await page.waitForLoadState("networkidle");
  });

  test("Flow 1: Search a part and open detail page", async ({ page }) => {
    // 1. Navigate to Part Catalog Search
    await page.click('text="Part Catalog"');
    await expect(page).toHaveURL(/.*\/parts/);
    await expect(page.locator("main h1")).toContainText("Part Catalog Search");

    // 2. Search for part PMP-0001
    const searchInput = page.locator('[data-testid="part-search-input"]');
    await expect(searchInput).toBeVisible();
    await searchInput.fill("PMP-0001");
    await page.click('[data-testid="part-search-button"]');

    // 3. Verify results table shows PMP-0001
    const partLink = page.locator('a[href="/parts/PMP-0001"]').first();
    await expect(partLink).toBeVisible();

    // 4. Click part to open detail page
    await partLink.click();
    await expect(page).toHaveURL(/.*\/parts\/PMP-0001/);

    // 5. Verify detail page header and attributes
    await expect(page.locator("main h1")).toContainText("PMP-0001");
    await expect(page.locator("text=ApexFlow 1000 End-Suction Centrifugal Pump").first()).toBeVisible();

    // Verify tabs / sections render
    await expect(page.locator("text=Attributes & Specs").first()).toBeVisible();
    await expect(page.locator("text=Where-Used Tree").first()).toBeVisible();

    // Capture screenshot
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "e2e_1_search_and_detail.png"),
      fullPage: true,
    });
  });

  test("Flow 2: Expand BOM tree with lazy-loaded subassemblies", async ({ page }) => {
    // 1. Navigate to BOM Explorer for PMP-0001
    await page.goto("http://127.0.0.1:5173/bom?part=PMP-0001");
    await page.waitForLoadState("networkidle");

    // 2. Verify Root Assembly and BOM links table
    await expect(page.locator("main h1")).toContainText("Multi-Level BOM Explorer");
    await expect(page.locator("text=Product Hierarchy: PMP-0001")).toBeVisible();

    // 3. Find an assembly row with an expand chevron (PMP-0006 is direct child of PMP-0001)
    const expandButton = page.locator('button[aria-label^="Expand children for PMP-0006"]').first();
    await expect(expandButton).toBeVisible();

    // 4. Click expand chevron to lazy-load children
    await expandButton.click();

    // 5. Verify lazy-loaded subassembly breakdown renders
    const subassemblyBreakdown = page.locator("text=Lazy-loaded Subassembly: PMP-0006");
    await expect(subassemblyBreakdown).toBeVisible({ timeout: 10000 });

    // Capture screenshot
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "e2e_2_expand_bom.png"),
      fullPage: true,
    });
  });

  test("Flow 3: Compare two BOM structures (EBOM vs MBOM)", async ({ page }) => {
    // 1. Navigate to BOM Compare
    await page.click('text="BOM Compare"');
    await expect(page).toHaveURL(/.*\/bom\/compare/);
    await expect(page.locator("main h1")).toContainText("BOM Comparison & Reconciliation");

    // 2. Click EBOM vs MBOM preset
    const presetBtn = page.locator('button:has-text("EBOM vs MBOM (Planted #4)")');
    await expect(presetBtn).toBeVisible();
    await presetBtn.click();

    // 3. Click Compare button
    const compareBtn = page.locator('[data-testid="compare-boms-button"]');
    await expect(compareBtn).toBeVisible();
    await compareBtn.click();

    // 4. Verify delta metrics cards render
    await expect(page.locator("text=Added in Assembly B")).toBeVisible();
    await expect(page.locator("text=Removed from Assembly B")).toBeVisible();
    await expect(page.locator("text=Quantity / Spec Changes")).toBeVisible();

    // 5. Verify diff table rows render
    const diffTable = page.locator("table");
    await expect(diffTable.first()).toBeVisible();

    // Capture screenshot
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "e2e_3_compare_boms.png"),
      fullPage: true,
    });
  });

  test("Flow 4: Run change impact & blast-radius analysis", async ({ page }) => {
    // 1. Navigate to Impact Analysis
    await page.click('text="Impact Analysis"');
    await expect(page).toHaveURL(/.*\/impact/);
    await expect(page.locator("main h1")).toContainText("Change Impact & Blast-Radius Analysis");

    // 2. Fill in target part PMP-0010
    const impactInput = page.locator('[data-testid="impact-part-input"]');
    await expect(impactInput).toBeVisible();
    await impactInput.fill("PMP-0010");
    await page.click('[data-testid="evaluate-impact-button"]');

    // 3. Verify blast radius results render
    await expect(page.locator("text=Affected Assemblies").first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Engineering Documents").first()).toBeVisible();
    await expect(page.locator("text=Severity:").first()).toBeVisible();

    // Capture screenshot
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "e2e_4_impact_analysis.png"),
      fullPage: true,
    });
  });

  test("Flow 5: Propose draft ECR and confirm with two-step safety gate", async ({ page }) => {
    // 1. Navigate to Change Requests
    await page.click('text="Change Requests"');
    await expect(page).toHaveURL(/.*\/changes/);
    await expect(page.locator("main h1")).toContainText("Engineering Change Requests (ECR)");

    // 2. Open Draft ECR Modal
    const openDraftBtn = page.locator('[data-testid="open-draft-ecr-button"]');
    await expect(openDraftBtn).toBeVisible();
    await openDraftBtn.click();

    // 3. Fill in Draft ECR Form
    const titleInput = page.locator('[data-testid="ecr-title-input"]');
    await expect(titleInput).toBeVisible();
    await titleInput.fill("Upgrade Impeller to Inconel 718 for Cavitation Prevention");

    const partsInput = page.locator('[data-testid="ecr-parts-input"]');
    await partsInput.fill("PMP-0010");

    const reasonInput = page.locator('[data-testid="ecr-reason-input"]');
    await reasonInput.fill("Field vibration sensors and wear inspection show high cavitation degradation under peak hydraulic flow.");

    // 4. Submit Step 1: Generate Draft Preview (Dry-Run)
    const submitDraftBtn = page.locator('[data-testid="submit-draft-button"]');
    await submitDraftBtn.click();

    // 5. Verify Step 2 Safety Protocol Preview is displayed
    await expect(page.locator("text=SAFETY PROTOCOL: You are currently viewing an unpersisted draft")).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[role="dialog"]').getByText("Upgrade Impeller to Inconel 718 for Cavitation Prevention")).toBeVisible();

    // 6. Execute Step 2: Confirm & Commit ECR
    const confirmBtn = page.locator('[data-testid="confirm-ecr-button"]');
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // 7. Verify Success Confirmation view
    await expect(page.locator("text=Committed")).toBeVisible({ timeout: 10000 });

    // 8. Dismiss modal
    const doneBtn = page.locator('[data-testid="ecr-done-button"]');
    await expect(doneBtn).toBeVisible();
    await doneBtn.click();

    // Capture screenshot
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "e2e_5_draft_and_confirm_ecr.png"),
      fullPage: true,
    });
  });
});
