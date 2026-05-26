export function friendlyError(raw: unknown): string {
  const s = (
    typeof raw === "string" ? raw : JSON.stringify(raw ?? "")
  ).toLowerCase();
  if (
    /context|token|length|max_model|maximum|too long|超出|过长|上下文|窗口/.test(
      s
    )
  ) {
    return "对话内容已接近或超过模型上下文上限。建议新建对话，或删除较早的消息后再试。";
  }
  if (
    /ngrok|err_ngrok|gateway error|incomplete http response|service unavailable/i.test(
      s
    )
  ) {
    return "隧道/网关超时或后端无响应（常见于推理过久）。请确认 FastAPI 在运行；若经 ngrok 访问，请稍后重试或暂时关闭「流式响应」。";
  }
  if (/connection refused|connect|timeout|无法连接|502|503|network error|failed to fetch/i.test(
    s
  )) {
    return "无法连接后端，请确认已执行 ./scripts/run.sh";
  }
  if (/<!doctype\s+html|<html[\s>]/i.test(s)) {
    return "服务器返回了错误页面而非 API 数据，请检查后端是否崩溃或 ngrok/Nginx 是否超时。";
  }
  if (typeof raw === "object" && raw !== null) {
    const o = raw as Record<string, unknown>;
    const err = o.error as Record<string, unknown> | string | undefined;
    if (err && typeof err === "object" && err.message) {
      return friendlyError(err.message);
    }
    if (o.detail) return friendlyError(String(o.detail));
    if (o.error) return friendlyError(String(o.error));
  }
  return typeof raw === "string" && raw.trim() ? raw : "请求失败，请稍后重试。";
}

export function estimateTokens(text: string): number {
  let n = 0;
  for (const ch of text) {
    n += ch.charCodeAt(0) > 127 ? 1.5 : 0.35;
  }
  return Math.ceil(n);
}

export function groupLabel(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const that = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diff = (today.getTime() - that.getTime()) / 86400000;
  if (diff === 0) return "今天";
  if (diff === 1) return "昨天";
  if (diff < 7) return "近 7 天";
  return "更早";
}

export function uid(): string {
  return (
    crypto.randomUUID?.() ||
    `c-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  );
}
