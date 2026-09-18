import { expect, test, type Page } from "@playwright/test";

/** Widget answers for the fake-LLM onboarding conversation (LLD §10.2). */
const ANSWERS: Record<string, (page: Page) => Promise<void>> = {
  text: async (page) => {
    const box = page.getByTestId("widget-text").locator("input, textarea").first();
    await box.fill((await box.getAttribute("placeholder")) === "Your first name" ? "Priya" : "avoid sugar");
    await page.getByRole("button", { name: "Continue" }).click();
  },
  date: async (page) => {
    await page.getByTestId("widget-date").locator("input").fill("1995-04-02");
    await page.getByRole("button", { name: "Continue" }).click();
  },
  number: async (page) => {
    const input = page.getByTestId("widget-number").locator("input");
    await input.fill((await input.getAttribute("max")) === "250" ? "165" : "58");
    await page.getByRole("button", { name: "Continue" }).click();
  },
  single_select: async (page) => {
    await page.getByTestId("widget-single_select").getByRole("button").first().click();
    await page.getByRole("button", { name: "Continue" }).click();
  },
  multi_select: async (page) => {
    await page.getByTestId("widget-multi_select").getByRole("button").first().click();
    await page.getByRole("button", { name: "Continue" }).click();
  },
  chips: async (page) => {
    const chips = page.getByTestId("widget-chips");
    if ((await chips.getByRole("button", { name: "PCOS" }).count()) > 0) {
      await chips.getByRole("button", { name: "type 2 diabetes" }).click();
      await page.getByRole("button", { name: "Continue" }).click();
    } else {
      await page.getByRole("button", { name: "None, continue" }).click();
    }
  },
};

test("first run: sign up, onboard, stock the pantry, get a plan, swap, feedback, shop", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto("/sign-up");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("larder-pass-123");
  await page.getByRole("button", { name: "Create account" }).click();

  await page.waitForURL(/\/onboarding/);
  const progress = async () =>
    (await page.getByTestId("review-card").count()) > 0 ? "done" : await page.getByText(/of \d+ answered/).innerText();
  for (let i = 0; i < 20; i++) {
    if ((await page.getByTestId("review-card").count()) > 0) break;
    const widget = page.locator("[data-testid^='widget-']").first();
    await expect(widget).toBeVisible();
    const type = (await widget.getAttribute("data-testid"))!.replace("widget-", "");
    const before = await progress();
    await ANSWERS[type](page);
    // the previous widget stays on screen until the agent replies; wait for the turn to land
    await expect.poll(progress, { timeout: 30_000 }).not.toBe(before);
  }
  await page.getByTestId("confirm-profile").click();

  await page.waitForURL(/\/pantry\/setup/);
  await page.getByTestId("bulk-add").fill("spinach, paneer, rice, toor dal, onion");
  await page.getByTestId("bulk-add-submit").click();
  await expect(page.getByText(/in your pantry/)).toBeVisible();
  await page.getByTestId("pantry-continue").click();

  await page.waitForURL(/\/today/);
  await expect(page.getByTestId("today-entries").getByTestId("plan-entry")).toHaveCount(4, { timeout: 60_000 });
  const dinner = page.getByTestId("plan-entry").last();
  const before = await dinner.locator("h3").innerText();
  await dinner.getByTestId("swap").click();
  await page.getByRole("button", { name: "Too heavy" }).click();
  await page.getByTestId("swap-confirm").click();
  await expect
    .poll(async () => page.getByTestId("plan-entry").last().locator("h3").innerText(), { timeout: 60_000 })
    .not.toBe(before);
  await page.getByTestId("plan-entry").first().getByLabel("Thumbs up").click();
  await expect(page.getByTestId("plan-entry").first().getByLabel("Thumbs up")).toHaveAttribute("aria-pressed", "true");

  await page.goto("/shopping");
  await expect(page.getByRole("heading", { name: "Shopping" })).toBeVisible();
  await expect(page.locator("section[aria-label]").first()).toBeVisible({ timeout: 20_000 });
});
