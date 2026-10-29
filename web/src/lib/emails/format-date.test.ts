import { describe, it, expect } from "vitest";
import { formatDate } from "./send-email";

// The same instant must render as the SAME calendar date on every surface,
// regardless of where the code runs (UTC server for emails, user-local browser
// for the dashboard/settings). A trial ending 2026-11-05T01:28Z once showed
// "November 5" in the email but "November 4" on the settings page — a user
// wrote in asking which was real. formatDate pins timeZone: "UTC"; this locks
// that it stays pinned no matter the host timezone.

describe("formatDate is timezone-deterministic", () => {
  it("renders the UTC calendar date, not the host-local one", () => {
    // 01:28 UTC = the previous evening in every US/Canada timezone — the exact
    // shape of the reported discrepancy.
    expect(formatDate("2026-11-05T01:28:01.622Z")).toBe(
      "Thursday, November 5, 2026",
    );
  });

  it("accepts Date objects the same way", () => {
    expect(formatDate(new Date("2026-11-05T01:28:01.622Z"))).toBe(
      "Thursday, November 5, 2026",
    );
  });

  it("midnight UTC never slides to the prior day", () => {
    expect(formatDate("2027-01-01T00:00:00.000Z")).toBe(
      "Friday, January 1, 2027",
    );
  });
});
