import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // `components/ui` and `components/assistant-ui` are vendored kits (shadcn/ui,
  // assistant-ui) copied in as-is, plus shadcn's `use-mobile` hook. New React 19
  // rules flag their internals; keeping them byte-for-byte upstream lets us
  // re-pull them later, so lint ours and leave theirs alone.
  {
    files: [
      "components/ui/**",
      "components/assistant-ui/**",
      "hooks/use-mobile.ts",
    ],
    rules: {
      "react-hooks/refs": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/exhaustive-deps": "off",
      "react/no-unescaped-entities": "off",
      "@next/next/no-img-element": "off",
      "jsx-a11y/alt-text": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
