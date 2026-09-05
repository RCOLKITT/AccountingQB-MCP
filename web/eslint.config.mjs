// ESLint flat config (Next.js 16 removed `next lint`; the plugin now defaults to
// flat config). eslint-config-next already exports a flat-config array, so we
// spread it and scope ignores + severities.
//
// Gate philosophy (spine): BLOCK the rules that catch real bugs; keep the new,
// opinionated React-19.2 "compiler-era" rules VISIBLE as warnings until we clear
// them under the web e2e suite (they were added by the Next 16 flat config and
// are only strictly needed once `reactCompiler` is enabled, which it isn't). This
// is the tracked G9 backlog — see SPINE-STATUS.
import next from "eslint-config-next";

export default [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...next,
  {
    rules: {
      // Real correctness bugs → ERROR (block merges):
      "react-hooks/rules-of-hooks": "error",
      "react/no-unescaped-entities": "error",
      // React 19.2 compiler-era rules → WARN (visible backlog; clear under e2e):
      "react-hooks/immutability": "warn",
      "react-hooks/purity": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
];
