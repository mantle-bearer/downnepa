import { expect, test } from "@playwright/test";

const demoPassword = "DownNepaDemo!2026";

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  (page as typeof page & { capturedErrors: string[] }).capturedErrors = errors;
});

test.afterEach(async ({ page }) => {
  expect((page as typeof page & { capturedErrors: string[] }).capturedErrors).toEqual([]);
});

test("anonymous monitoring uses live status, history, incidents and responsive controls", async ({ page }, testInfo) => {
  await page.goto("/?area=yaba");
  await expect(page.getByRole("heading", { name: /Supply unstable|Power available|Outage verified/ })).toBeVisible();
  await expect(page.getByText("Last 7 days in Yaba")).toBeVisible();
  await expect(page.locator(".bars > div")).toHaveCount(7);
  await expect(page.locator(".incident-list article")).toHaveCount(4);

  await page.getByRole("button", { name: "View evidence →" }).click();
  await expect(page.getByRole("dialog", { name: "Yaba" })).toBeVisible();
  await page.getByRole("button", { name: "Close dialog" }).click();

  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
    await page.getByRole("button", { name: "Incidents", exact: true }).click();
    await expect(page.locator("#incidents")).toBeInViewport();
  }

  const metrics = await page.evaluate(() => {
    const viewport = document.documentElement.clientWidth;
    const textElements = Array.from(document.querySelectorAll("body *")).filter((element) => {
      const html = element as HTMLElement;
      const hasDirectText = Array.from(element.childNodes).some((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim());
      return hasDirectText && html.getBoundingClientRect().width > 0 && html.getBoundingClientRect().height > 0;
    }) as HTMLElement[];
    return {
      viewport,
      bodyWidth: document.documentElement.scrollWidth,
      smallestText: Math.min(...textElements.map((element) => Number.parseFloat(getComputedStyle(element).fontSize))),
      unnamedButtons: Array.from(document.querySelectorAll("button:not([disabled])")).filter((button) => !(button.textContent?.trim() || button.getAttribute("aria-label"))).length,
      smallTargets: Array.from(document.querySelectorAll("button:not([disabled]), a")).filter((node) => {
        const rect = (node as HTMLElement).getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && rect.height < 40;
      }).length,
    };
  });
  expect(metrics.bodyWidth).toBeLessThanOrEqual(metrics.viewport + 1);
  expect(metrics.smallestText).toBeGreaterThanOrEqual(12);
  expect(metrics.unnamedButtons).toBe(0);
  expect(metrics.smallTargets).toBe(0);
});

test("member can sign up, save an area, report restoration and see dashboard history", async ({ page }, testInfo) => {
  const email = `e2e-${testInfo.project.name}-${Date.now()}@example.com`;
  await page.goto("/?area=yaba");
  await page.getByRole("button", { name: "Sign up / Log in" }).click();
  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Display name").fill("E2E Resident");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[autocomplete="new-password"]').fill(demoPassword);
  await page.getByRole("button", { name: "Create my account" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: /Good to see you/ })).toBeVisible();

  await page.getByRole("button", { name: "+ Report power status" }).click();
  await expect(page).toHaveURL(/area=yaba/);
  await page.getByRole("button", { name: /Save Yaba/ }).click();
  await expect(page.getByRole("status")).toContainText("saved to your dashboard");
  await page.getByRole("button", { name: /Light don come/ }).click();
  const reportDialog = page.getByRole("dialog", { name: /What is happening in Yaba/ });
  await expect(reportDialog.getByRole("button", { name: /Light don come/, exact: true })).toHaveAttribute("aria-pressed", "true");
  await reportDialog.getByLabel("Optional context").fill("E2E restoration confirmation from the estate gate.");
  await reportDialog.getByRole("button", { name: "Submit observation" }).click();
  await expect(page.getByRole("status")).toContainText("Report received for Yaba");

  await page.goto("/dashboard");
  await expect(page.getByText("E2E restoration confirmation from the estate gate.")).toHaveCount(0);
  await expect(page.locator(".activity-list article")).toHaveCount(1);
  await expect(page.locator(".places article")).toHaveCount(1);
  await page.getByRole("button", { name: "Monitor →" }).click();
  await expect(page).toHaveURL(/area=yaba/);
  await expect(page.getByText("Last 7 days in Yaba")).toBeVisible();
});

test("admin can review evidence and run the trusted sample pipeline", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign up / Log in" }).click();
  await page.getByLabel("Email address").fill("admin@demo.downnepa.com");
  await page.locator('input[autocomplete="current-password"]').fill(demoPassword);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Evidence review" })).toBeVisible();
  const firstReport = page.locator(".admin-table > article").first();
  await expect(firstReport).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await firstReport.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByRole("status")).toContainText("marked verified");

  await page.getByRole("button", { name: "Data pipeline" }).click();
  await page.getByRole("button", { name: "Run verified sample" }).click();
  await expect(page.getByRole("status")).toContainText("Pipeline run");
  await expect(page.locator(".run-list article").first()).toContainText("completed");
  await page.getByRole("button", { name: "Audit trail" }).click();
  await expect(page.locator(".audit-list article").first()).toBeVisible();
});
