export type ThemeMode = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const THEME_KEY = "my_vllm_theme";

export function getThemeMode(): ThemeMode {
  const v = localStorage.getItem(THEME_KEY);
  if (v === "light" || v === "dark" || v === "system") return v;
  return "system";
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }
  return mode;
}

export function applyTheme(mode?: ThemeMode): ResolvedTheme {
  const themeMode = mode ?? getThemeMode();
  const resolved = resolveTheme(themeMode);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themeMode = themeMode;
  return resolved;
}

export function setThemeMode(mode: ThemeMode): void {
  localStorage.setItem(THEME_KEY, mode);
  applyTheme(mode);
}

/** 应用已保存主题并监听系统偏好变化；在 main.tsx 调用一次 */
export function initTheme(): () => void {
  applyTheme();
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => {
    if (getThemeMode() === "system") applyTheme();
  };
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}
