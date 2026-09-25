---
type: tool_used
tool: Skill
min: 1
arm: with-only
---

Plugin-fired indicator (reported, not scored): a tax-prep request should engage
an AccountingQB skill via the Skill tool when the plugin is loaded. Only fires
in the "with" arm (the baseline has no skills), so it distinguishes
plugin-driven behavior from base-model prose.
