import { expect, test, type Page } from "@playwright/test";
const now = new Date().toISOString();
const warning = { id: "fixture-alert", event: "TEST moderate rain", headline: "TEST ONLY: district warning, not a real flood report.", instruction: "TEST instruction: follow official updates.", area: "Chennai district", sender: "TEST IMD Chennai", severity: "Moderate", certainty: "Possible", sent_at: now, received_at: now, expires_at: new Date(Date.now() + 3600000).toISOString(), state: "active", url: "https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=100" };
const snapshot = { location: "Velachery", retrieved_at: now, feed: { stale: false, last_success: now, coverage: "TEST district-only coverage" }, alerts: [warning], reports: [] as any[], review_enabled: true };
async function boot(page: Page, initial = snapshot) {
  let state = structuredClone(initial);
  await page.route("https://tile.openstreetmap.org/**", route => route.fulfill({ contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=", "base64") }));
  await page.route("**/api/health", route => route.fulfill({ json: { default_provider: "groq", providers: { groq: { configured: false, model: "test" }, gemini: { configured: false, model: "test" }, openai: { configured: false, model: "test" } } } }));
  await page.route("**/api/context/**", route => route.fulfill({ json: { location: route.request().url().split("/").pop(), retrieved_at: now, outlook: null, sources: [], source_status: [], coverage_note: "Test fixture" } }));
  await page.route("**/api/operations/**", route => route.fulfill({ json: state }));
  await page.route("**/api/reports", route => {
    const data = route.request().postDataJSON();
    const report = { ...data, id: "fixture-report", status: "unreviewed", revision: 0, stale: false, review_history: [] };
    state.reports = [report];
    return route.fulfill({ status: 201, json: report });
  });
  await page.route("**/api/reports/*/review", route => {
    if (route.request().headers()["x-review-token"] !== "test-coordinator") return route.fulfill({ status: 403, json: { detail: "A valid coordinator review token is required." } });
    const review = route.request().postDataJSON();
    state.reports[0] = { ...state.reports[0], status: review.status, revision: 1, review_history: [{ ...review, reviewed_at: now }] };
    return route.fulfill({ json: state.reports[0] });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "On the ground in Velachery." })).toBeVisible();
}
test("official warning is visible without model access and opens original evidence", async ({ page }, info) => {
  await boot(page);
  await expect(page.getByRole("heading", { name: warning.event })).toBeVisible();
  await expect(page.getByText("Official feed checked", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Get recommendations", exact: true })).toBeDisabled();
  await page.getByText("Why? Read the official warning", { exact: false }).click();
  await expect(page.getByText(warning.headline, { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open original CAP record" })).toHaveAttribute("href", warning.url);
  await page.screenshot({ path: info.outputPath("official-alert-desktop.png"), fullPage: true });
});
test("mobile field report stays unreviewed until coordinator check is saved", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await boot(page);
  await page.getByRole("button", { name: "Add field report", exact: true }).click();
  await page.getByLabel("Street or landmark").fill("TEST railway entrance");
  await page.getByLabel("What is happening?").fill("TEST ONLY: water observed near the entrance.");
  await page.getByLabel("Assistance requested (optional)").fill("TEST request for drinking water");
  await page.getByRole("button", { name: "Submit unreviewed report" }).click();
  await expect(page.getByText("Unreviewed", { exact: true })).toBeVisible();
  await page.getByText("Coordinator review", { exact: true }).click();
  await page.getByLabel("Coordinator token").fill("wrong-token");
  await page.getByLabel("Reviewer name or ID").fill("TEST coordinator");
  await page.getByLabel("What did you check?").fill("TEST ONLY: confirmed observation with an on-site volunteer.");
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("valid coordinator review token");
  await expect(page.getByText("Unreviewed", { exact: true })).toBeVisible();
  await page.getByLabel("Coordinator token").fill("test-coordinator");
  await page.getByRole("button", { name: "Save review", exact: true }).click();
  await expect(page.getByText("Human-reviewed", { exact: true })).toBeVisible();
  await page.getByText("Why this status? Review trail").click();
  await expect(page.getByText("TEST ONLY: confirmed observation with an on-site volunteer.", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("field-review-mobile.png"), fullPage: true });
});
test("stale feed never advertises a current warning or an all-clear", async ({ page }) => {
  await boot(page, { ...snapshot, feed: { ...snapshot.feed, stale: true } });
  await expect(page.getByText("Official feed not current", { exact: true })).toBeVisible();
  await expect(page.getByText("May be outdated", { exact: true })).toBeVisible();
  await expect(page.getByText("Official feed checked", { exact: true })).toHaveCount(0);
});
