import type { ThemeMode } from "./theme";
import { MoonIcon, MonitorIcon, SunIcon } from "./icons";
import type { User } from "./types";

interface Props {
  user: User;
  streamEnabled: boolean;
  themeMode: ThemeMode;
  onStreamChange: (enabled: boolean) => void;
  onThemeChange: (mode: ThemeMode) => void;
  onLogout: () => void;
  onClose: () => void;
}

const THEME_OPTIONS: {
  mode: ThemeMode;
  label: string;
  icon: typeof SunIcon;
}[] = [
  { mode: "light", label: "浅色", icon: SunIcon },
  { mode: "dark", label: "深色", icon: MoonIcon },
  { mode: "system", label: "跟随系统", icon: MonitorIcon },
];

export default function UserAccountPanel({
  user,
  streamEnabled,
  themeMode,
  onStreamChange,
  onThemeChange,
  onLogout,
  onClose,
}: Props) {
  return (
    <>
      <div className="account-overlay" onClick={onClose} />
      <div
        className="account-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-panel-title"
      >
        <header className="account-panel-header">
          <h2 id="account-panel-title" className="account-panel-title">
            账户设置
          </h2>
          <button
            type="button"
            className="account-panel-close"
            aria-label="关闭"
            onClick={onClose}
          >
            ✕
          </button>
        </header>

        <div className="account-panel-body">
          <section className="account-section">
            <div className="account-avatar" aria-hidden>
              {user.email.charAt(0).toUpperCase()}
            </div>
            <div className="account-info">
              <span className="account-label">登录邮箱</span>
              <span className="account-email">{user.email}</span>
            </div>
          </section>

          <section className="account-section account-settings">
            <h3 className="account-section-title">外观</h3>
            <div className="theme-selector" role="radiogroup" aria-label="主题">
              {THEME_OPTIONS.map(({ mode, label, icon: Icon }) => (
                <button
                  key={mode}
                  type="button"
                  role="radio"
                  aria-checked={themeMode === mode}
                  className={`theme-option${themeMode === mode ? " active" : ""}`}
                  onClick={() => onThemeChange(mode)}
                >
                  <Icon />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="account-section account-settings">
            <h3 className="account-section-title">对话偏好</h3>
            <label className="account-setting-row">
              <div className="account-setting-text">
                <span className="account-setting-name">流式响应</span>
                <span className="account-setting-desc">
                  开启后助手回复将逐字显示；关闭则等待完整回复后一次性展示
                </span>
              </div>
              <input
                type="checkbox"
                className="account-toggle"
                checked={streamEnabled}
                onChange={(e) => onStreamChange(e.target.checked)}
              />
            </label>
          </section>

          <button
            type="button"
            className="account-logout-btn"
            onClick={() => {
              onClose();
              onLogout();
            }}
          >
            退出登录
          </button>
        </div>
      </div>
    </>
  );
}
