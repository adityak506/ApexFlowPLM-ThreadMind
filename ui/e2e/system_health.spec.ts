import { test, expect } from "@playwright/test";
import path from "path";

const SCREENSHOT_DIR = "C:/Users/ADITYA/.gemini/antigravity/brain/70d2ebf3-dd7a-4f49-ad9c-fb5b2b7a4bb1/screenshots";

test.describe("Frontend Observability & System Health", () => {
  test("Verifies system health, W3C traceparent propagation, error capture, and live probe", async ({ page }) => {
    // 1. Intercept network requests to verify W3C traceparent header propagation
    let observedTraceparent: string | null = null;
    let observedRequestId: string | null = null;

    page.on("request", (req) => {
      if (req.url().includes("/health") || req.url().includes("/parts")) {
        const headers = req.headers();
        if (headers["traceparent"]) {
          observedTraceparent = headers["traceparent"];
        }
        if (headers["x-request-id"]) {
          observedRequestId = headers["x-request-id"];
        }
      }
    });

    // 2. Navigate to System Health page
    await page.goto("http://127.0.0.1:5173/system-health");
    await page.waitForLoadState("networkidle");

    // 3. Verify page header and status cards
    await expect(page.locator("h1")).toContainText("System Health & Observability");
    await expect(page.locator("text=Mock (SQLite)").first()).toBeVisible();
    await expect(page.locator("text=Healthy").first()).toBeVisible();

    // 4. Verify W3C Distributed Trace Context Active banner
    await expect(page.locator("text=W3C Distributed Trace Context Active")).toBeVisible();
    await expect(page.locator("text=Traceparent Propagated")).toBeVisible();

    // 5. Verify W3C traceparent header was indeed sent over HTTP
    expect(observedTraceparent).not.toBeNull();
    expect(observedTraceparent).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/);
    expect(observedRequestId).not.toBeNull();

    // 6. Test error capture via Simulate Error button
    await page.click('button:has-text("Simulate Error")');
    await page.waitForTimeout(300);

    // Verify error row rendered in the Captured Client Errors table
    await expect(page.locator("text=Simulated frontend exception triggered").first()).toBeVisible();
    await expect(page.locator("text=simulation_trigger").first()).toBeVisible();

    // 7. Test Ping API button
    await page.click('button:has-text("Ping API")');
    await page.waitForTimeout(500);

    // Verify recent API table contains /health
    await expect(page.locator("text=/health").first()).toBeVisible();

    // 8. Capture verified screenshot of the active dashboard with simulated error and API metrics
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "screenshot_system_health.png"),
      fullPage: true,
    });
  });
});

