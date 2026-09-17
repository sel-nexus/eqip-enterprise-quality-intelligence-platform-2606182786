import { expect, test } from "@playwright/test";

/** Drive the actual governed portfolio UI through the API proxy. */
test("creates an application and renders the persisted business record", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") browserErrors.push(message.text()); });
  page.on("pageerror", (error) => browserErrors.push(error.message));

  const applicationName = `E2E Claims Portal ${Date.now()}`;
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Application register" })).toBeVisible();
  await page.getByLabel(/Application name/).fill(applicationName);
  await page.getByLabel(/Product/).fill("Claims");
  await page.getByLabel(/Owners/).fill("e2e-user");
  await page.getByRole("button", { name: "Register application" }).click();

  const createdRow = page.getByRole("row", { name: new RegExp(applicationName) });
  await expect(createdRow.locator("td.mono")).toHaveText(/APP-[A-F0-9]{12}/);
  await expect(createdRow.getByText(applicationName)).toBeVisible();
  expect(browserErrors).toEqual([]);
});
