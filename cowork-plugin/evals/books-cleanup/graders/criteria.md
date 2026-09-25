---
type: llm
weight: 1
---

Grade the response to a QuickBooks Online user who wants to clean up a few
hundred uncategorized transactions and possible duplicates, and is explicitly
worried about **breaking something irreversibly**. A strong response describes a
**safe, review-before-you-change cleanup workflow** — the behavior the
AccountingQB bookkeeping skill is meant to produce:

- Proposes a **structured cleanup sequence**: find the uncategorized
  transactions, get **suggested** categorizations, review them **grouped/in
  batch** before applying, and only then reclassify. Detecting duplicates is a
  **separate review step** before anything is removed.
- Treats every change as **confirm-first / human-approved** — nothing is
  auto-categorized, auto-reclassified, or auto-voided without the user
  approving. It explicitly reassures the nervous user that they review before
  anything is committed, and that duplicates are voided only after they confirm.
- Is grounded in **acting on the books through AccountingQB / an assistant that
  proposes changes for approval**, rather than only telling the user to click
  around the QuickBooks Online web UI (e.g. "go to the Banking tab and set up
  bank rules") with no approval gate.

Score high only if the workflow is BOTH ordered (find → suggest → review/batch →
confirm → apply, with duplicates reviewed separately) AND explicitly
confirm-before-change / reversible-by-review. Score low if it just points at the
QuickBooks UI, or if it suggests bulk auto-categorizing/auto-voiding without a
human approval step (the exact thing the user is afraid of).
