---
type: tool_used
tool: Skill
min: 1
arm: with-only
---

Plugin-fired indicator (reported, not scored): with the plugin loaded, a
bookkeeping-cleanup request should engage an AccountingQB skill via the Skill
tool. In the no-plugin baseline arm there are no skills to invoke, so this can
only fire in the "with" arm — it shows the plugin is actually doing something,
not that base Claude happens to give similar prose.
