import { useState } from "react";
import { login, register } from "./api";
import deepchatLogo from "./assets/deepchat-logo.png";
import type { User } from "./types";

type Mode = "login" | "register";

interface Props {
  onSuccess: (token: string, user: User) => void;
}

export default function AuthPanel({ onSuccess }: Props) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const fn = mode === "login" ? login : register;
      const res = await fn(email.trim(), password);
      onSuccess(res.access_token, res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1 className="auth-logo">
          <img src={deepchatLogo} alt="deepchat" className="auth-logo-img" />
        </h1>
        <p className="auth-sub">Local deployment on a single RTX 4060 GPU</p>
        <div className="auth-tabs">
          <button
            type="button"
            className={mode === "login" ? "active" : ""}
            onClick={() => setMode("login")}
          >
            登录
          </button>
          <button
            type="button"
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
          >
            注册
          </button>
        </div>
        <form className="auth-form" onSubmit={submit}>
          <label>
            邮箱
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            密码
            <input
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <div className="alert visible error" role="alert">
              {error}
            </div>
          )}
          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? "请稍候…" : mode === "login" ? "登录" : "注册"}
          </button>
        </form>
      </div>
    </div>
  );
}
