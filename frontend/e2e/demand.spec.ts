import { expect, test } from "@playwright/test";

/** Exercise the real demand transition route and its persisted response. */
test("transitions a live demand and shows the workflow result", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      browserErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));

  await page.goto("/");
  await page.getByLabel("Demand ID").fill("DEM-READINESS-01");
  const transitionResponse = page.waitForResponse(async (response) => {
    if (!response.url().endsWith("/api/v1/demands/DEM-READINESS-01/transitions") || response.status() !== 200) {
      return false;
    }
    const body = await response.json() as { data: { demand_id: string; state: string; version: number; history: unknown[] } };
    return body.data.demand_id === "DEM-READINESS-01"
      && body.data.state === "triaged"
      && body.data.version === 1
      && Array.isArray(body.data.history);
  });
  await page.getByRole("button", { name: "Transition demand" }).click();
  await transitionResponse;
  await expect(page.getByText("DEM-READINESS-01 is triaged at version 1.")).toBeVisible();
  await page.screenshot({ path: "test-results/demand-complete.png", fullPage: true });

  await page.reload();
  await expect(page.getByLabel("Demand ID")).toHaveValue("DEM-READINESS-01");
  expect(browserErrors).toEqual([]);
});