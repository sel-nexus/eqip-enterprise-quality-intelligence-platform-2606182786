import { expect, test } from "@playwright/test";

/** Exercise persisted release readiness through the live UI and assert its API envelope. */
test("renders the persisted API readiness recommendation", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      browserErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));

  const releaseId = `REL-E2E-${Date.now()}`;
  await page.goto("/");
  await page.getByLabel("Release ID").fill(releaseId);
  await page.getByLabel("Unwaived gate failures").fill("1");
  const readinessResponse = page.waitForResponse(async (response) => {
    if (!response.url().endsWith(`/api/v1/releases/${releaseId}/readiness`) || response.status() !== 200) {
      return false;
    }
    const body = await response.json() as {
      data: { release_id: string; version: number; recommendation: string; weights: Record<string, number> };
    };
    return body.data.release_id === releaseId
      && body.data.version === 1
      && body.data.recommendation === "Blocked"
      && body.data.weights.gates === 0.4;
  });
  await page.getByRole("button", { name: "Calculate readiness" }).click();
  await readinessResponse;

  await expect(page.getByText("Blocked — weighted score")).toBeVisible();
  await expect(page.getByText(new RegExp(`Persisted release ${releaseId}, version 1`))).toBeVisible();
  await expect(page.getByText("Gates 40% · Tests 30% · Defects 15% · Automation 15%")).toBeVisible();
  await page.screenshot({ path: "test-results/readiness-complete.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});