import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

// Browser tests use explicit fixtures. The application itself has no mock provider.
const samples = Object.entries(
  JSON.parse(
    readFileSync(
      new URL("../../sample_data/crisis_examples.json", import.meta.url),
      "utf8",
    ),
  ),
).map(([id, input]) => ({ id, input }));
const assessment = {
  location: "Velachery",
  disaster_type: "urban_flooding",
  severity: "high",
  severity_evidence: [
    {
      statement: "The report describes stopped traffic.",
      source: "field_report",
    },
  ],
  affected_people: ["Commuters"],
  resources_required: ["Traffic management support"],
  recommended_actions: ["Verify the incident with human responders."],
  missing_information: ["Exact number of affected residents"],
  situation_report:
    "The supplied report describes traffic disruption near Velachery MRTS.",
};

async function boot(page: Page, configured = true, provider: "gemini" | "groq" = "gemini") {
  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: {
        status: "ok",
        default_provider: provider,
        providers: {
          gemini: { configured: configured && provider === "gemini", model: "test-model" },
          openai: { configured: false, model: "test-openai" },
          groq: { configured: configured && provider === "groq", model: "openai/gpt-oss-120b" },
        },
      },
    }),
  );
  await page.route("**/api/scenarios", (route) =>
    route.fulfill({ json: samples }),
  );
  await page.goto("/");
  await expect(page.getByText("Backend connected")).toBeVisible();
}

test("no configured provider means no fabricated assessment", async ({
  page,
}) => {
  await boot(page, false);
  await page.getByRole("button", { name: /Velachery Urban flooding/ }).click();
  await expect(
    page.getByRole("button", { name: "Generate assessment" }),
  ).toBeDisabled();
  await expect(page.getByText("API key needed on backend")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Why this severity?" }),
  ).toHaveCount(0);
});

test("Groq default selection submits to the same assessment pipeline", async ({ page }) => {
  await boot(page, true, "groq");
  await expect(page.getByLabel("Generation model")).toHaveValue("groq");
  await page.route("**/api/analyse", (route) => {
    const submitted = route.request().postDataJSON();
    expect(submitted.provider).toBe("groq");
    return route.fulfill({ json: { input: submitted.input, assessment,
      metadata: { provider: "groq", model: "openai/gpt-oss-120b", generated_at: "2026-10-06T04:00:00Z", latency_ms: 1200 } } });
  });
  await page.getByRole("button", { name: /Velachery Urban flooding/ }).click();
  await page.getByRole("button", { name: "Generate assessment" }).click();
  await expect(page.getByRole("heading", { name: "Why this severity?" })).toBeVisible();
});

test("generation renders API evidence, exports input and clears stale results on edit", async ({
  page,
}) => {
  await boot(page);
  let submitted: Record<string, any>;
  await page.route("**/api/analyse", (route) => {
    submitted = route.request().postDataJSON();
    return route.fulfill({
      json: {
        input: submitted.input,
        assessment,
        metadata: {
          provider: "gemini",
          model: "test-model",
          generated_at: "2026-10-06T04:00:00Z",
          latency_ms: 1200,
        },
      },
    });
  });
  await page.getByRole("button", { name: /Velachery Urban flooding/ }).click();
  await page.getByRole("button", { name: "Generate assessment" }).click();
  await expect(
    page.getByRole("heading", { name: "Why this severity?" }),
  ).toBeVisible();
  await expect(page.getByRole("note")).toContainText("Synthetic demonstration — not a live incident");
  await expect(page.getByRole("note")).toContainText("Weather values are synthetic demonstration inputs.");
  await expect(
    page.getByText(assessment.severity_evidence[0].statement),
  ).toBeVisible();
  expect(submitted!.input.environment.source_name).toBe(
    "Synthetic development scenario",
  );
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(
    /^crisislens-velachery-.*\.json$/,
  );
  const path = await download.path();
  expect(JSON.parse(readFileSync(path!, "utf8")).input).toEqual(
    submitted!.input,
  );
  await page
    .getByLabel("Field report", { exact: true })
    .fill("A revised report with unknown water depth.");
  await expect(
    page.getByRole("heading", { name: "Why this severity?" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Export JSON" })).toHaveCount(
    0,
  );
});

test("locality changes reset report and previous weather", async ({ page }) => {
  await boot(page);
  await page.getByRole("button", { name: /Velachery Urban flooding/ }).click();
  await page.getByLabel("Pilot locality").selectOption("Tambaram");
  await expect(page.getByLabel("Field report", { exact: true })).toHaveValue(
    "",
  );
  await expect(
    page.getByRole("button", { name: "Generate assessment" }),
  ).toBeDisabled();
  await expect(
    page.getByText("Unavailable measurements remain unknown", { exact: false }),
  ).toBeVisible();
});

test("weather failure retains labelled context and displays an error", async ({
  page,
}) => {
  await boot(page);
  await page.route("**/api/weather/*", (route) =>
    route.fulfill({
      status: 503,
      json: {
        detail:
          "Weather unavailable. Retry or explicitly use unknown/manual context.",
      },
    }),
  );
  await page.getByRole("button", { name: /Velachery Urban flooding/ }).click();
  await page.getByRole("button", { name: "Fetch weather" }).click();
  await expect(page.getByRole("alert")).toContainText("Weather unavailable");
  await expect(
    page.getByText("Synthetic sample", { exact: true }),
  ).toBeVisible();
});

test("mobile workspace has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await boot(page);
  await expect(
    page.getByRole("heading", { name: "Clarity when it matters." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("live weather does not relabel a synthetic incident as real", async ({ page }) => {
  await boot(page);
  await page.route("**/api/weather/*", (route) => route.fulfill({ json: {
    rainfall_1h_mm: 0, rainfall_24h_mm: 0, temperature_c: 30,
    water_level_m: null, source_name: "Open-Meteo modelled weather",
    source_kind: "gridded_weather_fallback", observed_at: "2026-10-07T00:00:00+05:30",
  } }));
  await page.route("**/api/analyse", (route) => {
    const submitted = route.request().postDataJSON();
    expect(submitted.input.source_label).toBe("development_example_not_live_data");
    expect(submitted.input.environment.rainfall_1h_mm).toBe(0);
    expect(submitted.input.environment.water_level_m).toBeNull();
    return route.fulfill({ json: { input: submitted.input, assessment,
      metadata: { provider: "gemini", model: "test-model", generated_at: "2026-10-07T00:01:00+05:30", latency_ms: 1000 } } });
  });
  await page.getByRole("button", { name: /Velachery Urban flooding/ }).click();
  await page.getByRole("button", { name: "Fetch weather" }).click();
  await expect(page.getByText("Gridded fallback", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Generate assessment" }).click();
  await expect(page.getByRole("note")).toContainText("The incident report is fictional.");
  await expect(page.getByRole("note")).toContainText("Weather is modelled context from Open-Meteo");
});
