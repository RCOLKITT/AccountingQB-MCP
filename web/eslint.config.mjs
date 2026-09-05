// ESLint flat config (Next.js 16 removed `next lint`; the plugin now defaults to
// flat config). eslint-config-next already exports a flat-config array, so we
// spread it and scope ignores. Lint is not a CI gate yet — making it blocking is
// the dedicated G9 hardening item (see SPINE-STATUS).
import next from "eslint-config-next";

export default [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...next,
];
