import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function register(page: Page) {
  await page.goto("/");
  await page.getByLabel("Your name", { exact: true }).fill("Evaluation Engineer");
  await page.getByLabel("Company name", { exact: true }).fill("Evaluation Plant");
  await page.getByLabel("Work email", { exact: true }).fill(`evaluation-${Date.now()}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("evaluation-password-2026");
  await page.getByRole("button", { name: "Create my workspace" }).click();
  await expect(page.getByRole("button", { name: "Register equipment", exact: true })).toBeVisible();
  const me = await page.request.get("/api/v1/industrial/auth/me");
  expect(me.status()).toBe(200);
  const profile = await me.json();
  return `/api/v1/industrial/companies/${profile.companies[0].id}`;
}

async function accessibility(page: Page, name: string) {
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  await test.info().attach(`${name}-accessibility`, { body: JSON.stringify(result.violations, null, 2), contentType: "application/json" });
  expect(result.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) }))).toEqual([]);
}

test("authentication layout accessibility and keyboard entry", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Build your operating picture." })).toBeVisible();
  await page.getByLabel("Your name", { exact: true }).focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Company name", { exact: true })).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await accessibility(page, "authentication");
  await page.screenshot({ path: `../output/testing/evidence/auth-${test.info().project.name}.png`, fullPage: true });
  expect(errors).toEqual([]);
});

test("invalid login shows an actionable error and remains usable", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("Work email", { exact: true }).fill("does-not-exist@example.com");
  await page.getByLabel("Password", { exact: true }).fill("evaluation-password-2026");
  await page.getByRole("button", { name: "Sign in", exact: true }).last().click();
  await expect(page.getByRole("alert").filter({ hasText: "Email or password is incorrect" })).toContainText("Email or password is incorrect");
  await expect(page.getByRole("button", { name: "Sign in", exact: true }).last()).toBeEnabled();
});

test("registration equipment sensor CSV alert maintenance and logout", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  const base = await register(page);
  await page.getByRole("button", { name: "Register equipment", exact: true }).click();
  await page.getByLabel("Site name", { exact: true }).fill("Evaluation Site");
  await page.getByRole("button", { name: "Add site", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Site registered");
  await page.getByRole("combobox", { name: "Site", exact: true }).selectOption({ label: "Evaluation Site" });
  await page.getByLabel("Asset tag", { exact: true }).fill("EVAL-PUMP");
  await page.getByLabel("Machine name", { exact: true }).fill("Evaluation pump");
  await page.getByRole("combobox", { name: "Equipment category", exact: true }).fill("Pump");
  await page.getByRole("button", { name: "Register machine", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Machine registered");
  await page.getByRole("button", { name: "Evaluation pump EVAL-PUMP / Pump", exact: true }).click();
  await page.getByLabel("Sensor key", { exact: true }).fill("temperature");
  await page.getByLabel("Display name", { exact: true }).fill("Bearing temperature");
  await page.getByLabel("Measurement unit", { exact: true }).fill("degC");
  await page.getByLabel("Warning above", { exact: true }).fill("80");
  await page.getByRole("button", { name: "Add sensor", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Sensor registered");
  await page.getByRole("button", { name: "Data connections", exact: true }).click();
  const rows = [3, 2, 1].map(i => `temperature,${new Date(Date.now() - i * 60000).toISOString()},90,degC`);
  await page.getByLabel("Telemetry CSV", { exact: true }).setInputFiles({ name: "evaluation.csv", mimeType: "text/csv", buffer: Buffer.from("sensor_key,timestamp,value,unit\n" + rows.join("\n")) });
  await page.getByRole("button", { name: "Validate & import", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "3 accepted" })).toBeVisible();
  const alerts = await (await page.request.get(`${base}/alerts`)).json();
  expect(alerts).toHaveLength(1);
  await page.getByRole("button", { name: "Maintenance", exact: true }).click();
  await page.getByRole("combobox", { name: "Machine", exact: true }).selectOption({ label: "EVAL-PUMP / Evaluation pump" });
  await page.getByLabel("Work title", { exact: true }).fill("Inspect pump bearing");
  await page.getByRole("button", { name: "Create work order", exact: true }).click();
  await expect(page.getByRole("button", { name: "Inspect pump bearing", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Operations overview", exact: true }).click();
  await accessibility(page, "workspace");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.evaluate(() => { window.scrollTo(0, 0); document.querySelector(".ix-sidebar")?.scrollTo(0, 0); });
  await page.screenshot({ path: `../output/testing/evidence/workspace-${test.info().project.name}.png`, fullPage: true });
  await page.reload();
  await expect(page.getByRole("button", { name: "Register equipment", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Build your operating picture." })).toBeVisible();
  expect((await page.request.get("/api/v1/industrial/auth/me")).status()).toBe(401);
  expect(errors).toEqual([]);
});

test("research demo renders without runtime errors and has accessible controls", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto("/demo");
  await expect(page.locator("h1")).toBeVisible();
  await accessibility(page, "research");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: `../output/testing/evidence/demo-${test.info().project.name}.png`, fullPage: true });
  expect(errors).toEqual([]);
});

test("research sample import training prediction and inspection complete", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto("/demo");
  await page.getByRole("button", { name: "Run sample demo", exact: true }).click();
  await expect(page.getByText("Synthetic demo completed. Ready for inspection.", { exact: true })).toBeVisible({ timeout: 100000 });
  await expect(page.getByRole("status")).toContainText("succeeded");
  const models = await (await page.request.get("http://127.0.0.1:8001/api/v1/models")).json();
  expect(models.length).toBeGreaterThan(0);
  const predictions = await (await page.request.get(`http://127.0.0.1:8001/api/v1/predictions?model_version_id=${models[0].id}`)).json();
  expect(predictions.length).toBeGreaterThan(0);
  expect(predictions.every((p: { predicted_rul: number; lower_bound: number; upper_bound: number }) => Number.isFinite(p.predicted_rul) && p.lower_bound <= p.upper_bound)).toBe(true);
});
