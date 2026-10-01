import { test, expect, type Browser, type Page } from "@playwright/test";

/** Large lists are paginated and searched on the server; OD pages work on a phone-sized screen. */

const PASSWORDS: Record<string, string> = { student1: "student123", faculty1: "faculty123", admin: "admin123" };

async function login(browser: Browser, username: string, viewport?: { width: number; height: number }): Promise<Page> {
  const context = await browser.newContext(viewport ? { viewport } : {});
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByPlaceholder("e.g. student1").fill(username);
  await page.locator('input[type="password"]').fill(PASSWORDS[username]);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(new RegExp(`/${username.replace(/\d+$/, "")}`));
  return page;
}

test.beforeAll(async ({ request }) => {
  if (!process.env.E2E_BASE_URL) {
    const health = await (await request.get("/api/health")).json();
    if (health.instance !== "e2e") throw new Error("Refusing to run: not the e2e test backend.");
  }
});

test("admin lists are paginated and searchable", async ({ browser }) => {
  const admin = await login(browser, "admin");

  await admin.getByRole("link", { name: "Students" }).click();
  await expect(admin.getByText("5,000 students enrolled")).toBeVisible();
  await expect(admin.getByText("Showing 1–25 of 5000")).toBeVisible();
  await expect(admin.locator("tbody tr")).toHaveCount(25);
  await admin.getByRole("button", { name: "Next" }).click();
  await expect(admin.getByText("Page 2 of 200")).toBeVisible();
  await admin.getByLabel("Search students").fill("21CSE1042");
  await expect(admin.getByText("1 student match your search")).toBeVisible();
  await expect(admin.getByRole("cell", { name: "Manish Kumar" })).toBeVisible();
  await admin.getByLabel("Search students").fill("no-such-student-xyz");
  await expect(admin.getByText("No students found.")).toBeVisible();

  await admin.getByRole("link", { name: "Faculty", exact: true }).click();
  await expect(admin.getByText("1,000 faculty members")).toBeVisible();
  await expect(admin.getByText("Page 1 of 42")).toBeVisible();

  await admin.getByRole("link", { name: "Placement Portal" }).click();
  await expect(admin.getByText(/Applications \(7,2\d\d\)/)).toBeVisible();
  await admin.getByLabel("Search applications").fill("Manish Kumar");
  await expect(admin.locator("tbody tr").first()).toContainText("Manish Kumar");
  await admin.context().close();
});

test("faculty attendance entry is paginated and still saves", async ({ browser }) => {
  const faculty = await login(browser, "faculty1");
  await faculty.getByRole("link", { name: "Attendance" }).click();
  await expect(faculty.getByText("Showing 1–25 of 1667")).toBeVisible();
  await faculty.getByLabel("Search students").fill("Manish Kumar");
  const row = faculty.locator("tbody tr").filter({ hasText: "21CSE1042" });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Save" }).click();
  await expect(faculty.getByText("Updated attendance for Manish Kumar.")).toBeVisible();
  await faculty.context().close();
});

test("OD pages work on a phone-sized screen", async ({ browser }, testInfo) => {
  const student = await login(browser, "student1", { width: 390, height: 800 });
  const noSidewaysScroll = async () =>
    expect(await student.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

  // The sidebar is a drawer on small screens.
  await expect(student.getByRole("link", { name: "On-Duty (OD)" })).toBeHidden();
  await student.getByRole("button", { name: "Open navigation menu" }).click();
  await student.getByRole("link", { name: "On-Duty (OD)" }).click();
  await expect(student.getByRole("heading", { name: "On-Duty (OD)" })).toBeVisible();
  await expect(student.getByRole("link", { name: "On-Duty (OD)" })).toBeHidden(); // drawer closed after navigating
  await expect(student.getByText("Available to request")).toBeVisible();
  await noSidewaysScroll();
  await testInfo.attach("od-dashboard-mobile", { body: await student.screenshot({ fullPage: true }), contentType: "image/png" });

  await student.getByRole("link", { name: "Apply for OD" }).click();
  await expect(student.getByLabel("Event name")).toBeVisible();
  await noSidewaysScroll();
  await testInfo.attach("od-apply-mobile", { body: await student.screenshot({ fullPage: true }), contentType: "image/png" });
  await student.context().close();
});
