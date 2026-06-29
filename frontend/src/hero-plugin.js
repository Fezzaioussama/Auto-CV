// Adapter so Tailwind v4's `@plugin` directive can load HeroUI's v3-style
// plugin. The package exports `{ heroui }` as a named function; we wrap it
// here and re-export the configured plugin as the module default.
import { heroui } from "@heroui/react";

export default heroui({
  themes: {
    light: {
      colors: {
        primary: { DEFAULT: "#2563eb", foreground: "#ffffff" },
        secondary: { DEFAULT: "#0f766e", foreground: "#ffffff" },
      },
    },
  },
});
