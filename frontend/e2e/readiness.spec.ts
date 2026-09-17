import { expect, test } from "@playwright/test";

/** Exercise demand transition and persisted release readiness through the live UI. */
test("transitions a demand and renders the persisted API readiness recommendation", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));

  const demandId = `DEM-E2E-${Date.now()}`;
  const releaseId = `REL-E2E-${Date.now()}`;
  await page.goto("/");
  await page.getByLabel("Demand ID").fill(demandId);
  await page.getByRole("button", { name: "Transition demand" }).click();
  await expect(page.getByText(new RegExp(`${demandId} is triaged at version 1`))).toBeVisible();

  await page.getByLabel("Release ID").fill(releaseId);
  await page.getByLabel("Unwaived gate failures").fill("1");
  await page.getByRole("button", { name: "Calculate readiness" }).click();
  await expect(page.getByText("Blocked — weighted score")).toBeVisible();
  await expect(page.getByText(new RegExp(`Persisted release ${releaseId}, version 1`))).toBeVisible();
  await expect(page.getByText("Gates 40% · Tests 30% · Defects 15% · Automation 15%")).toBeVisible();
  expect(browserErrors).toEqual([]);
});
