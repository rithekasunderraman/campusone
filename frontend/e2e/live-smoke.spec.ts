import { test, expect, type Browser, type Page } from "@playwright/test";

/**
 * Read-only smoke test of a LIVE deployment: each role signs in through the
 * real site and must see populated data from the migrated database.
 *
 *   $env:E2E_BASE_URL = "https://campusone-web.onrender.com"; npx playwright test e2e/live-smoke.spec.ts
 *
 * The expected figures are those of the seeded CampusOne dataset.
 */
test.skip(!process.env.E2E_BASE_URL, "live smoke test: set E2E_BASE_URL to a deployed site");

const PASSWORDS: Record<string, string> = { student1: "student123", faculty1: "faculty123", admin: "admin123" };

async function login(browser: Browser, username: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  const calls: string[] = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/")) calls.push(`${r.status()} ${new URL(r.url()).host}${new URL(r.url()).pathname}`);
  });
  (page as any).apiCalls = calls;
  await page.goto("/login");
  await page.getByPlaceholder("e.g. student1").fill(username);
  await page.locator('input[type="password"]').fill(PASSWORDS[username]);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible({ timeout: 90_000 }); // free tier may be waking up
  return page;
}

/** The stat card with this label shows exactly this value. */
async function card(page: Page, label: string, value: string | RegExp) {
  const box = page.locator("div.card").filter({ has: page.getByText(label, { exact: true }) }).first();
  await expect(box).toContainText(value);
}

function assertApiHost(page: Page, testInfo: any) {
  const calls: string[] = (page as any).apiCalls;
  const site = new URL(process.env.E2E_BASE_URL!).host;
  testInfo.attach("api-calls", { body: calls.join("\n"), contentType: "text/plain" });
  expect(calls.length).toBeGreaterThan(3);
  expect(calls.filter((c) => !c.startsWith("200 ") && !c.startsWith("201 "))).toEqual([]);
  expect(calls.filter((c) => c.includes(` ${site}/`))).toEqual([]); // API calls go to the backend host, not the static site
}

test("student1 sees populated data", async ({ browser }, testInfo) => {
  const page = await login(browser, "student1");
  await card(page, "Overall Attendance", "87.6%");
  await card(page, "Current CGPA", "8.42");
  await card(page, "Fees Status", "Paid");
  await expect(page.getByText("Manish Kumar").first()).toBeVisible();
  await testInfo.attach("student-dashboard", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });

  await page.getByRole("link", { name: "Attendance" }).click();
  await expect(page.getByText("Data Structures and Algorithms").first()).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(5);

  await page.getByRole("link", { name: "Placement" }).click();
  await expect(page.getByText("TechNova Solutions").first()).toBeVisible();

  await page.getByRole("link", { name: "Campus Life" }).click();
  await expect(page.getByText("Football Club").first()).toBeVisible();

  await page.getByRole("link", { name: "On-Duty (OD)" }).click();
  await card(page, "Available to request", /\d+(\.\d+)?h/);
  await card(page, "Attendance", /8\d(\.\d)?%/);
  await expect(page.getByText("Class advisor: Dr. Anand Subramaniam")).toBeVisible();
  await testInfo.attach("student-od", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
  assertApiHost(page, testInfo);
  await page.context().close();
});

test("faculty1 sees populated data", async ({ browser }, testInfo) => {
  const page = await login(browser, "faculty1");
  await card(page, "Subjects Taught", "3");
  await card(page, "Students Taught", "1667");
  await card(page, "Avg. Class Performance", /7\d(\.\d)?%/);
  await testInfo.attach("faculty-dashboard", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });

  await page.getByRole("link", { name: "Students" }).click();
  await expect(page.getByText("Showing 1–25 of 1667")).toBeVisible();

  await page.getByRole("link", { name: "OD Approvals" }).click();
  await card(page, "Awaiting my decision", /^Awaiting my decision[4-9]/); // 4 imported requests (+ any new ones)
  await expect(page.locator("tbody tr").first()).toBeVisible();
  assertApiHost(page, testInfo);
  await page.context().close();
});

test("admin sees populated data", async ({ browser }, testInfo) => {
  const page = await login(browser, "admin");
  await card(page, "Total Students", "5000");
  await card(page, "Total Faculty", "1000");
  await card(page, "Overall Attendance", "75.2%");
  await card(page, "Offers Made", "1427");
  await testInfo.attach("admin-dashboard", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });

  await page.getByRole("link", { name: "Placement Portal" }).click();
  await card(page, "Total Applications", "7273");
  await expect(page.getByText(/Applications \(7,273\)/)).toBeVisible();

  await page.getByRole("link", { name: "OD Oversight" }).click();
  await page.getByRole("tab", { name: "Analytics" }).click();
  await card(page, "Requests this term", /10,50\d/);
  await expect(page.getByText("Department summary")).toBeVisible();
  await testInfo.attach("admin-od-analytics", { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
  assertApiHost(page, testInfo);
  await page.context().close();
});
