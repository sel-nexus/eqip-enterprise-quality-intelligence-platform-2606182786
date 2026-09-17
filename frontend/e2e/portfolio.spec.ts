import { expect, test } from "@playwright/test";

/** Drive the actual governed portfolio UI through the API proxy. */
test("renders a live empty state, validates locally, loads deterministically, and persists an application", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      browserErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));

  await page.route("**/api/v1/applications?limit=50&offset=0", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 300));
    await route.continue();
  });

  const initialList = page.waitForResponse(async (response) => {
    if (!response.url().includes("/api/v1/applications?limit=50&offset=0") || response.status() !== 200) {
      return false;
    }
    const body = await response.json() as { data: { items: unknown[]; total: number } };
    return Array.isArray(body.data.items) && typeof body.data.total === "number";
  });
  await page.goto("/");
  await expect(page.getByText("Loading governed applications…")).toBeVisible();
  await initialList;
  await expect(page.getByText("No governed applications are recorded yet.")).toBeVisible();

  await page.getByRole("button", { name: "Register application" }).click();
  await expect(page.getByRole("alert")).toHaveText(/Name, product, at least one owner/);
  await expect(page.getByText("No governed applications are recorded yet.")).toBeVisible();

  const applicationName = `E2E Claims Portal ${Date.now()}`;
  await page.getByLabel(/Application name/).fill(applicationName);
  await page.getByLabel(/Product/).fill("Claims");
  await page.getByLabel(/Owners/).fill("e2e-user");
  const creation = page.waitForResponse(async (response) => {
    if (!response.url().endsWith("/api/v1/applications") || response.status() !== 201) {
      return false;
    }
    const body = await response.json() as { data: { application_id: string; name: string; lifecycle: string } };
    return body.data.name === applicationName
      && /^APP-[A-F0-9]{12}$/.test(body.data.application_id)
      && body.data.lifecycle === "active";
  });
  await page.getByRole("button", { name: "Register application" }).click();
  await creation;

  const createdRow = page.getByRole("row", { name: new RegExp(applicationName) });
  await expect(createdRow.locator("td.mono")).toHaveText(/APP-[A-F0-9]{12}/);
  await expect(createdRow.getByText(applicationName)).toBeVisible();
  await page.screenshot({ path: "test-results/portfolio-complete.png", fullPage: true });

  await page.reload();
  await expect(page.getByRole("row", { name: new RegExp(applicationName) })).toBeVisible();
  expect(browserErrors).toEqual([]);
});

test("remains usable at a mobile viewport after live data loads", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      browserErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Application register" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Register application" })).toBeVisible();
  await page.screenshot({ path: "test-results/portfolio-mobile-complete.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

/** The production-mode backend rejects API traffic visibly without backend source changes. */
test("shows the production-auth API rejection in the browser", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    const isIntentionalUnauthorizedResource = message.type() === "error"
      && message.text() === "Failed to load resource: the server responded with a status of 401 (Unauthorized)";
    if (message.type() === "error" && !isIntentionalUnauthorizedResource) {
      browserErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));

  const rejectedList = page.waitForResponse(async (response) => {
    if (!response.url().includes("127.0.0.1:8001/api/v1/applications") || response.status() !== 401) {
      return false;
    }
    const body = await response.json() as { detail: string };
    return body.detail === "No production authentication adapter is configured.";
  });
  await page.goto("http://127.0.0.1:5174/");
  await rejectedList;
  await expect(page.getByRole("alert")).toContainText("No production authentication adapter is configured.");
  expect(browserErrors).toEqual([]);
});