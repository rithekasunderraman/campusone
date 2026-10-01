import { test, expect, type Browser, type Page } from "@playwright/test";

/**
 * The full OD demo flow in a real browser, with each role in its own browser
 * session so cross-user, no-refresh propagation is actually exercised:
 *
 *   student submits -> class advisor approves -> student sees it without reloading
 *   long request -> advisor recommends -> HOD approves -> analytics + audit log
 *   clarification round trip -> rejection with reason
 *   AI assistant answers OD questions from the same data
 */

const PASSWORDS: Record<string, string> = { student1: "student123", faculty1: "faculty123", admin2: "admin123", admin: "admin123" };
const run = Date.now().toString(36).slice(-5);
const weekOffset = Number(process.env.E2E_WEEK_OFFSET || "1");

/** A weekday `n` weeks ahead (0 = Monday), formatted for <input type="datetime-local">. */
function day(weekday: number, weeks = weekOffset): string {
  const d = new Date();
  d.setDate(d.getDate() + ((weekday + 7 - ((d.getDay() + 6) % 7)) % 7) + 7 * weeks);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function login(browser: Browser, username: string): Promise<Page> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/login");
  await page.getByPlaceholder("e.g. student1").fill(username);
  await page.locator('input[type="password"]').fill(PASSWORDS[username]);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();
  return page;
}

async function apply(student: Page, opts: { name: string; date: string; start: string; end: string; hours: string; withDocument?: boolean }) {
  await student.getByRole("link", { name: "On-Duty (OD)" }).click();
  await student.getByRole("link", { name: "Apply for OD" }).click();
  await student.getByLabel("Event name").fill(opts.name);
  await student.getByLabel("Organiser").fill("IEEE Student Branch");
  await student.getByLabel("Venue").fill("Main Auditorium");
  await student.getByLabel("Starts").fill(`${opts.date}T${opts.start}`);
  await student.getByLabel("Ends").fill(`${opts.date}T${opts.end}`);
  await student.getByLabel("OD hours needed").fill(opts.hours);
  await student.getByLabel("Purpose").fill("Presenting our project at the event.");
  await student.getByRole("button", { name: "Continue" }).click();

  if (opts.withDocument) {
    await student.getByLabel("Choose a file").setInputFiles({
      name: "invitation.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(`INVITATION\nEvent: ${opts.name}\nOrganised by: IEEE Student Branch\nDate: ${opts.date}\nVenue: Main Auditorium\n`),
    });
    await expect(student.getByText("invitation.txt")).toBeVisible();
  }
  await student.getByRole("button", { name: "Continue" }).click();

  await expect(student.getByText("You can submit this request.")).toBeVisible();
  await student.getByRole("button", { name: "Continue" }).click();
  await expect(student.getByText("Eligible", { exact: true })).toBeVisible();
  await student.getByRole("button", { name: "Submit request" }).click();
  await expect(student.getByRole("heading", { name: "OD request" })).toBeVisible();
  await expect(student.getByText(opts.name).first()).toBeVisible();
}

async function openInQueue(page: Page, navLabel: string, eventName: string) {
  await page.getByRole("link", { name: navLabel }).click();
  await page.getByPlaceholder("Search student, reg. no. or event").fill(eventName);
  await page.getByRole("button", { name: eventName }).click();
}

test.describe.configure({ mode: "serial" });

// A cold Vite dev server can take a minute or more to pre-bundle dependencies on
// first load; absorb that here so it does not eat into the first test's time.
test.beforeAll(async ({ browser, request }) => {
  test.setTimeout(300_000);
  // Safety interlock: a local run must be talking to the throwaway test backend,
  // never to the real one. (Against a deployment, E2E_BASE_URL is set on purpose.)
  if (!process.env.E2E_BASE_URL) {
    const health = await (await request.get("/api/health")).json();
    if (health.instance !== "e2e") {
      throw new Error(`Refusing to run: the backend behind this page is "${health.instance || "the real application"}", not the e2e test instance.`);
    }
  }
  const page = await browser.newPage();
  await page.goto("/login", { timeout: 240_000 });
  await expect(page.getByRole("heading", { name: "Sign in to your portal" })).toBeVisible({ timeout: 240_000 });
  await page.close();
});

test("student applies, class advisor approves, student sees it without reloading", async ({ browser }) => {
  const name = `Tech Symposium ${run}`;
  const student = await login(browser, "student1");
  await apply(student, { name, date: day(0), start: "09:00", end: "12:00", hours: "3", withDocument: true });
  await expect(student.getByText("Under faculty review").first()).toBeVisible();
  await expect(student.getByText("invitation.txt")).toBeVisible();

  const faculty = await login(browser, "faculty1");
  await openInQueue(faculty, "OD Approvals", name);
  await expect(faculty.getByText("Manish Kumar").first()).toBeVisible();
  await expect(faculty.getByText("Student's OD balance")).toBeVisible();
  await faculty.getByLabel("Comment (required to reject or ask for clarification)").fill("Approved - all the best.");
  await faculty.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(faculty.getByText("Request approved (Approved).")).toBeVisible();

  // The student's page was left open and is NOT reloaded: polling must surface the decision.
  await expect(student.getByText("Approved", { exact: true }).first()).toBeVisible({ timeout: 20_000 });
  await expect(student.getByText("Approved - all the best.").first()).toBeVisible();
  await expect(student.getByText("Attendance credited")).toBeVisible();

  await student.getByRole("link", { name: "Back to my requests" }).click();
  await expect(student.getByText("3h").first()).toBeVisible(); // "Used" stat card
  await student.context().close();
  await faculty.context().close();
});

test("long request goes to the HOD; admin sees analytics and the audit log", async ({ browser }) => {
  const name = `National Hackathon ${run}`;
  const student = await login(browser, "student1");
  await apply(student, { name, date: day(1), start: "08:00", end: "18:00", hours: "10" });
  await expect(student.getByText("Class advisor, then HOD").first()).toBeVisible();

  const faculty = await login(browser, "faculty1");
  await openInQueue(faculty, "OD Approvals", name);
  await faculty.getByRole("button", { name: "Recommend to HOD" }).click();
  await expect(faculty.getByText("Recommended and sent to HOD (Under HOD review).")).toBeVisible();
  await expect(student.getByText("Under HOD review").first()).toBeVisible({ timeout: 20_000 });

  const hod = await login(browser, "admin2"); // heads CSE
  await hod.getByRole("link", { name: "OD Oversight" }).click();
  await expect(hod.getByText("Your department: CSE")).toBeVisible();
  await hod.getByPlaceholder("Search student, reg. no. or event").fill(name);
  await hod.getByRole("button", { name }).click();
  await hod.getByLabel("Comment (required to reject)").fill("Approved by HOD.");
  await hod.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(hod.getByText("Request approved.")).toBeVisible();
  await expect(student.getByText("Approved", { exact: true }).first()).toBeVisible({ timeout: 20_000 });

  // Audit log: every step, in order, with the actor.
  await hod.getByRole("tab", { name: "All requests" }).click();
  await hod.getByPlaceholder("Search student, reg. no. or event").fill(name);
  await hod.getByRole("button", { name }).click();
  await hod.getByRole("button", { name: "View audit log" }).click();
  const audit = hod.locator("table").last();
  for (const step of ["Draft created", "Submitted", "Sent to class advisor", "Recommended and sent to HOD", "Approved"]) {
    await expect(audit.getByText(step, { exact: true }).first()).toBeVisible();
  }
  await expect(audit.getByText("admin2 · admin")).toBeVisible();

  // Analytics
  await hod.getByRole("tab", { name: "Analytics" }).click();
  await expect(hod.getByText("Requests by department")).toBeVisible();
  await expect(hod.getByText("Department summary")).toBeVisible();
  await expect(hod.getByText("Average turnaround")).toBeVisible();

  for (const p of [student, faculty, hod]) await p.context().close();
});

test("clarification round trip, then rejection with a reason", async ({ browser }) => {
  const name = `Robotics Workshop ${run}`;
  const student = await login(browser, "student1");
  await apply(student, { name, date: day(2), start: "10:00", end: "12:00", hours: "2" });

  const faculty = await login(browser, "faculty1");
  await openInQueue(faculty, "OD Approvals", name);
  const comment = faculty.getByLabel("Comment (required to reject or ask for clarification)");
  await comment.fill("Please attach the registration confirmation.");
  await faculty.getByRole("button", { name: "Ask for clarification" }).click();
  await expect(faculty.getByText("Clarification requested (Clarification requested).")).toBeVisible();

  await expect(student.getByText("Your class advisor needs more information")).toBeVisible({ timeout: 20_000 });
  await student.getByLabel("Your response").fill("Registration is on the spot; no confirmation is issued.");
  await student.getByRole("button", { name: "Send response" }).click();
  await expect(student.getByText("Resubmitted").first()).toBeVisible();

  await faculty.getByRole("tab", { name: "Awaiting my decision" }).click();
  await faculty.getByPlaceholder("Search student, reg. no. or event").fill(name);
  await faculty.getByRole("button", { name }).click();
  await expect(faculty.getByText("Registration is on the spot; no confirmation is issued.").first()).toBeVisible();
  await comment.fill("Cannot verify participation.");
  await faculty.getByRole("button", { name: "Reject" }).click();
  await expect(faculty.getByText("Request rejected (Rejected).")).toBeVisible();

  await expect(student.getByText("Reason for rejection")).toBeVisible({ timeout: 20_000 });
  await expect(student.getByText("Cannot verify participation.").first()).toBeVisible();
  await student.context().close();
  await faculty.context().close();
});

test("overlapping request is blocked at the eligibility step", async ({ browser }) => {
  const student = await login(browser, "student1");
  await student.getByRole("link", { name: "On-Duty (OD)" }).click();
  await student.getByRole("link", { name: "Apply for OD" }).click();
  await student.getByLabel("Event name").fill(`Clashing Event ${run}`);
  await student.getByLabel("Starts").fill(`${day(0)}T10:00`);
  await student.getByLabel("Ends").fill(`${day(0)}T11:00`);
  await student.getByLabel("OD hours needed").fill("1");
  await student.getByLabel("Purpose").fill("Clash check");
  await student.getByRole("button", { name: "Continue" }).click();
  await student.getByRole("button", { name: "Continue" }).click();
  await expect(student.getByText("This request cannot be submitted yet.")).toBeVisible();
  await expect(student.getByText(/Overlaps your request/).first()).toBeVisible();
  await student.getByRole("button", { name: "Continue" }).click();
  await expect(student.getByRole("button", { name: "Submit request" })).toBeDisabled();
  await student.context().close();
});

test("AI assistant answers OD questions from the same data, for each role", async ({ browser }) => {
  const ask = async (page: Page, question: string) => {
    await page.getByPlaceholder("Type your question…").fill(question);
    await page.getByPlaceholder("Type your question…").press("Enter");
  };

  const student = await login(browser, "student1");
  await student.getByRole("link", { name: "AI Assistant" }).click();
  await ask(student, "How many OD hours do I have left?");
  // Test 1 approved 3h and test 2 approved 10h for this student.
  await expect(student.getByText(/used 13 OD hours and have 27 hours remaining out of 40/)).toBeVisible();
  await ask(student, "Why was my last OD application rejected?");
  await expect(student.getByText(/Reason: Cannot verify participation\./)).toBeVisible();
  await ask(student, "Can I apply for OD tomorrow?");
  await expect(student.getByText(/you can apply for OD tomorrow|You already have an OD request tomorrow/)).toBeVisible();

  const faculty = await login(browser, "faculty1");
  await faculty.getByRole("link", { name: "AI Assistant" }).click();
  await ask(faculty, "How many OD requests have I approved this month?");
  await expect(faculty.getByText(/This month you approved 1 OD request\(s\), recommended 1 to the HOD, rejected 1/)).toBeVisible();

  const admin = await login(browser, "admin");
  await admin.getByRole("link", { name: "AI Assistant" }).click();
  await ask(admin, "Show department-wise OD statistics");
  await expect(admin.getByText(/Department-wise OD statistics for this term/)).toBeVisible();
  await expect(admin.getByText(/- MECH: /)).toBeVisible();

  for (const p of [student, faculty, admin]) await p.context().close();
});
