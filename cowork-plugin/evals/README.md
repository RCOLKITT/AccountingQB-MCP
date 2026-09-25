# Cowork plugin evals

Behavioral eval suite for the AccountingQB Cowork plugin, run with:

```bash
claude plugin eval ./cowork-plugin --ablation with-without --trust-plugin
```

`--ablation with-without` runs each case twice — **with** the plugin loaded and
**without** it (baseline Claude) — and reports the score delta (Δ). A positive Δ
means the plugin improved the outcome; Δ ≈ 0 means the plugin matched baseline;
Δ < 0 means it regressed. Every case runs 3× per arm (variance control).

## Cases

| Case | What it checks | Type |
|---|---|---|
| `region-detection` | Canadian (Ontario) tax question → CRA/T2125/GST-HST terms + not-a-CPA disclaimer | should-fire, outcome |
| `jurisdiction-trap` | Ontario user *explicitly asks for* Schedule C + 1040-ES → skill must **correct** to the Canadian regime, not comply | should-fire, outcome |
| `books-cleanup` | Nervous user with uncategorized txns + duplicates → safe, **confirm-before-change**, ordered cleanup workflow (not "click around the QBO UI") | should-fire, outcome |
| `off-topic-no-fire` | Podcast recommendation → the AccountingQB skills must **not** fire (over-trigger guard) | should-NOT-fire |

Each should-fire case also carries a non-scored `tool_used: Skill` **indicator**
(`arm: with-only`) that confirms the plugin actually engaged a skill — it can
only fire in the "with" arm, so it separates plugin-driven behavior from base
Claude happening to write similar prose.

## What these results mean (read this before trusting a Δ)

Against a strong base model (Opus 4.8), **baseline Claude already handles these
text-only tax/bookkeeping questions well**, so the expected Δ on this suite is
**≈ 0** — that is not a failure of the plugin. The plugin's real value is in
things this suite does *not* measure end-to-end:

1. **Tool execution** — actually calling `qb_*` tools and returning grounded
   numbers from the user's books. Measuring lift here requires the eval harness's
   record/replay **MCP mocks**, which record responses from the *real* connector
   (i.e. against live QuickBooks OAuth). That is a separate, credentialed step;
   until then these cases run with the MCP server **not started** (skill
   instructions load, but `qb_*` tools are unavailable).
2. **Activation** — the `tool_used: Skill` indicators show the plugin engages on
   the right prompts and stays out of the way on off-topic ones.

**This suite's demonstrated payoff so far:** it caught a real regression. The
`jurisdiction-trap` case initially scored **Δ −0.33** — with the plugin loaded,
the tax-prep skill sometimes *followed* the user's wrong US framing (Schedule C /
1040-ES) for a Canadian business, because Step 0 region detection depended on
`qb_company_info`, which was unavailable without tools. Hardening the skill to
(a) fall back to user-stated region and (b) correct a wrong-jurisdiction request
took `jurisdiction-trap` from **0.67 → 1.00** (Δ back to 0.00). That is the
"Never Wrong-Jurisdiction Numbers" invariant, now enforced at the skill layer.

## Notes for maintainers

- `books-cleanup`'s outcome grader is deliberately strict (ordered
  find→suggest→review→confirm→apply, confirm-before-change) and is therefore
  higher-variance; both arms score similarly against it.
- Run artifacts (`evals/results/`) are git-ignored — commit cases + graders only.
- Grader front-matter: `type: llm | regex | tool_used | tool_order | file_exists
  | baseline`. `tool_used` takes `tool`, `min`, `max`, `arm`
  (`with-only` | `both`); a must-NOT-fire check is `min: 0, max: 0, arm: both`.
