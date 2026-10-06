import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

// Explicit fixtures: these sources and model outputs are never app fallbacks.
const weatherSource = { id: "W1", kind: "weather", title: "Weather context and 24-hour rain outlook", publisher: "Open-Meteo", url: "https://api.open-meteo.com/v1/forecast?latitude=12.98&longitude=80.22", published_at: "2026-10-07T01:00:00+05:30", retrieved_at: "2026-10-06T19:45:00Z", excerpt: "Modelled forecast, not an incident observation.", scope: "locality_grid", content_scope: "modelled_weather", limitation: "Cannot confirm flooding or safe road access." };
const userSource = { id: "U1", kind: "user", title: "Your question or report", publisher: "User supplied", url: null, published_at: null, retrieved_at: "2026-10-06T19:45:00Z", excerpt: "We have 50 food kits and 6 volunteers.", scope: "locality", content_scope: "unverified_input", limitation: "User input is not independent confirmation." };
const newsSource = { id: "N1", kind: "news", title: "Fixture report: Chennai rain outlook", publisher: "Fixture publisher", url: "https://indianexpress.com/article/test-fixture", published_at: "2026-10-06T12:00:00Z", retrieved_at: "2026-10-06T19:45:00Z", excerpt: "This test fixture describes a city-wide weather outlook.", scope: "city_context", content_scope: "feed_excerpt", limitation: "City-wide coverage does not establish a locality incident." };
const context = { location: "Velachery", retrieved_at: "2026-10-06T19:45:00Z", outlook: { environment: { temperature_c: 28, wind_speed_kmph: 10, observed_at: weatherSource.published_at }, next_rain: { time: "2026-10-07T08:00:00+05:30", precipitation_mm: 0.3, probability_percent: 30 }, forecast_complete: true, hours: Array.from({ length: 24 }, (_, i) => ({ time: `2026-10-07T${String(i).padStart(2, "0")}:00:00+05:30`, precipitation_mm: i === 8 ? 0.3 : 0, probability_percent: 30 })) }, sources: [weatherSource, newsSource], source_status: [{ name: "Open-Meteo", status: "available" }, { name: "The Indian Express", status: "available" }, { name: "The Hindu", status: "unavailable" }], coverage_note: "Test fixture: limited publisher and weather coverage." };
const recommendation = { location: "Velachery", headline: "Verify needs before allocating the food kits", answer: "The modelled forecast does not establish a local emergency. Confirm needs with a local coordinator before allocating your 50 kits.", claims: [{ statement: "Local flooding is reported", category: "incident", status: "insufficient_evidence", explanation: "No locality incident record was retrieved.", source_ids: ["U1"] }], recommendations: [{ title: "Check local conditions first", explanation: "The forecast alone cannot confirm the report.", source_ids: ["W1"] }], affected_groups: [{ title: "Reported elderly residents", explanation: "Mentioned by the user, not independently verified.", source_ids: ["U1"] }], supplies: [{ title: "Keep food kits ready", explanation: "Prepare the kits while verifying demand.", source_ids: [] }], missing_information: ["Current street access", "Number of people requesting supplies"] };
async function boot(page: Page, configured = true, unavailable = false) {
  await page.route("**/api/health", route => route.fulfill({ json: { default_provider: "groq", providers: { groq: { configured, model: "openai/gpt-oss-120b" }, gemini: { configured: false, model: "test" }, openai: { configured: false, model: "test" } } } }));
  await page.route("**/api/context/**", route => route.fulfill({ json: unavailable ? { ...context, outlook: null, sources: [], source_status: [{ name: "The Indian Express", status: "unavailable" }] } : { ...context, location: route.request().url().includes("Tambaram") ? "Tambaram" : "Velachery" } }));
  await page.route("**/api/recommend", route => {
    const question = route.request().postDataJSON();
    return route.fulfill({ json: { question, recommendation, context: { ...context, sources: question.demo ? [userSource] : [...context.sources, userSource] }, metadata: { model: "test", generated_at: "2026-10-06T19:45:01Z", latency_ms: 2100 } } });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Closer to Velachery." })).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh context" })).toBeEnabled();
}
async function generate(page: Page) {
  await page.getByRole("button", { name: "Plan supplies", exact: true }).click();
  await page.getByRole("button", { name: "Get recommendations", exact: true }).click();
  await expect(page.getByRole("heading", { name: recommendation.headline })).toBeVisible();
}
test("hero asks a question, presents forecast and keeps provider details secondary", async ({ page }) => {
  await boot(page);
  await expect(page.getByRole("heading", { name: "Know where your help is needed." })).toBeVisible();
  await expect(page.getByText("30% precipitation probability", { exact: false })).toBeVisible();
  await expect(page.getByText("Generation settings")).toHaveCount(0);
});
test("recommendation opens exact evidence and exports the source bundle", async ({ page }) => {
  await boot(page);
  await generate(page);
  await page.getByRole("button", { name: "Why this recommendation?", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: weatherSource.title })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open original source" })).toHaveAttribute("href", weatherSource.url);
  await expect(page.getByRole("dialog").getByText(newsSource.title)).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Why this recommendation?", exact: true })).toBeFocused();
  const promise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Save briefing" }).click();
  const download = await promise;
  expect(JSON.parse(readFileSync((await download.path())!, "utf8")).context.sources).toHaveLength(3);
});
test("claim explains unverified input and exposes missing information", async ({ page }) => {
  await boot(page); await generate(page);
  await page.getByRole("button", { name: /Not enough evidence Local flooding is reported/ }).click();
  await expect(page.getByRole("dialog")).toContainText("No locality incident record was retrieved.");
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Unverified input");
  await expect(page.getByRole("dialog").getByRole("link", { name: "Open original source" })).toHaveCount(0);
  await page.getByRole("tab", { name: "Unknowns" }).click();
  await expect(page.getByRole("dialog")).toContainText("Number of people requesting supplies");
});
test("editing a question clears old recommendations; locality refreshes context", async ({ page }) => {
  await boot(page); await generate(page);
  await page.getByLabel("Your question", { exact: true }).fill("What does the rain forecast show?");
  await expect(page.getByRole("heading", { name: recommendation.headline })).toHaveCount(0);
  await page.getByLabel("Area", { exact: true }).selectOption("Tambaram");
  await expect(page.getByRole("heading", { name: "Closer to Tambaram." })).toBeVisible();
});
test("unavailable sources and absent keys do not fabricate recommendations", async ({ page }) => {
  await boot(page, false, true);
  await page.getByRole("button", { name: "Plan supplies", exact: true }).click();
  await expect(page.getByRole("button", { name: "Get recommendations", exact: true })).toBeDisabled();
  await expect(page.getByText("Weather unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("No recent matching report retrieved", { exact: true })).toBeVisible();
});
test("mobile evidence sheet fits viewport and supports keyboard closing", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await boot(page); await generate(page);
  await page.getByRole("button", { name: "Why this recommendation?", exact: true }).click();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const box = await page.getByRole("dialog").boundingBox(); expect(box!.width).toBeLessThanOrEqual(390);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("hypothetical mode labels the result and retains only unverified source input", async ({ page }) => {
  await boot(page);
  await page.getByRole("button", { name: "Try a hypothetical scenario" }).click();
  await expect(page.getByText("Hypothetical demonstration. Live sources are excluded from this answer.")).toBeVisible();
  await page.getByRole("button", { name: "Get recommendations", exact: true }).click();
  await expect(page.getByText("Synthetic demonstration — not a live incident.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Why this recommendation?", exact: true }).click();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("link", { name: "Open original source" })).toHaveCount(0);
});

test("uncited suggestions do not borrow sources and hero evidence stays live in demo mode", async ({ page }) => {
  await boot(page);
  await generate(page);
  await page.getByRole("button", { name: /Keep food kits ready/ }).click();
  await page.getByRole("tab", { name: "Evidence", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("link", { name: "Open original source" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Try a hypothetical scenario" }).click();
  await page.getByRole("button", { name: "Get recommendations", exact: true }).click();
  await expect(page.getByRole("heading", { name: recommendation.headline })).toBeVisible();
  await page.getByRole("button", { name: /Open-Meteo ·/ }).click();
  await expect(page.getByRole("dialog").getByRole("link", { name: "Open original source" })).toHaveAttribute("href", weatherSource.url);
});
