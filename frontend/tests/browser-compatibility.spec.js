import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // Keep browser checks deterministic and independent of a local MySQL/Django instance.
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let body = {};
    if (url.pathname.endsWith("/health")) body = { status: "ok" };
    else if (url.pathname.endsWith("/stations")) body = { stations: [] };
    else if (url.pathname.endsWith("/travel-classes")) body = { travel_classes: [] };
    else if (url.pathname.endsWith("/session")) body = { authenticated: false };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
});

test("application loads and primary navigation works", async ({ page }) => {
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(page).toHaveTitle(/Trackline/);
  await expect(page.locator("#root")).not.toBeEmpty();
  await expect(page.locator("header")).toBeVisible();
  await expect(page.getByRole("link", { name: /plan/i }).first()).toBeVisible();
  await expect(page.locator("main")).toBeVisible();
  expect(pageErrors).toEqual([]);
});

test("layout fits desktop and mobile viewports without horizontal overflow", async ({ page }) => {
  await page.goto("/");
  for (const viewport of [{ width: 1440, height: 900 }, { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 320, height: 720 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.locator("main")).toBeVisible();
  }
});

test("search form remains keyboard accessible", async ({ page }) => {
  await page.goto("/");
  const form = page.locator("form").first();
  await expect(form).toBeVisible();
  const controls = form.locator("input, select, button");
  expect(await controls.count()).toBeGreaterThan(0);
  await controls.first().focus();
  await expect(controls.first()).toBeFocused();
});
