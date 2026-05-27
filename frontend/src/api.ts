import { authHeaders } from "./auth";
import type {
  AuthResponse,
  ChatConfig,
  ConversationDetail,
  ConversationSummary,
} from "./types";
import { friendlyError } from "./utils";

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const auth = authHeaders();
  for (const [k, v] of Object.entries(auth)) {
    headers.set(k, v);
  }
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(path, { ...init, headers });
}

async function parseError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const j = JSON.parse(text) as { detail?: string; error?: string };
    return friendlyError(j.detail ?? j.error ?? text);
  } catch {
    return friendlyError(text);
  }
}

export async function fetchConfig(): Promise<ChatConfig> {
  const res = await fetch("/api/config");
  if (!res.ok) throw new Error("无法加载配置");
  return res.json();
}

export async function waitForBackend(
  onProgress?: (msg: string) => void
): Promise<ChatConfig> {
  const maxAttempts = 300;
  for (let i = 0; i < maxAttempts; i++) {
    onProgress?.(
      i === 0
        ? "正在连接后端…"
        : `等待后端就绪…（${i + 1}/${maxAttempts}）`
    );
    try {
      const health = await fetch("/health", { signal: AbortSignal.timeout(8000) });
      if (!health.ok) {
        await new Promise((r) => setTimeout(r, 1000));
        continue;
      }
      const h = (await health.json()) as {
        status?: string;
        engine?: string;
        engine_error?: string | null;
      };
      if (h.status !== "ok") {
        await new Promise((r) => setTimeout(r, 1000));
        continue;
      }
      const engine = h.engine ?? "ready";
      if (engine === "error") {
        throw new Error(
          h.engine_error ?? "模型加载失败，请查看 .local/uvicorn.log"
        );
      }
      if (engine === "loading") {
        onProgress?.(
          i === 0
            ? "正在加载模型，首次启动约需 1～3 分钟…"
            : `模型加载中…（${i + 1}/${maxAttempts}）`
        );
        await new Promise((r) => setTimeout(r, 1000));
        continue;
      }
      if (engine !== "ready") {
        await new Promise((r) => setTimeout(r, 1000));
        continue;
      }
      onProgress?.("后端已就绪");
      return await fetchConfig();
    } catch (e) {
      if (e instanceof Error && !(e.name === "AbortError" || e.name === "TimeoutError")) {
        const msg = e.message;
        if (
          msg.includes("模型加载失败") ||
          msg.includes("引擎初始化") ||
          msg.includes("未安装 vllm") ||
          msg.includes("显存不足")
        ) {
          throw e;
        }
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
  throw new Error(
    "后端未就绪（含模型加载超时）。请确认已执行 ./scripts/start-dev.sh，并查看 .local/uvicorn.log"
  );
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function register(
  email: string,
  password: string
): Promise<AuthResponse> {
  const res = await apiFetch("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchMe() {
  const res = await apiFetch("/api/auth/me");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const res = await apiFetch("/api/conversations");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createConversation(
  title = "新对话"
): Promise<ConversationSummary> {
  const res = await apiFetch("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchConversation(
  id: string
): Promise<ConversationDetail> {
  const res = await apiFetch(`/api/conversations/${id}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export interface VoiceInput {
  base64?: string;
  data?: string;
  format?: string;
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await apiFetch(`/api/conversations/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function sendChat(
  message: string,
  conversationId: string | null,
  stream: boolean,
  onDelta?: (text: string) => void,
  media?: { imageUrls?: string[]; voiceInputs?: VoiceInput[] }
): Promise<{ reply: string; conversationId: string }> {
  const body: Record<string, unknown> = {
    message,
    conversation_id: conversationId,
    stream,
    max_tokens: 512,
  };
  if (media?.imageUrls?.length) {
    body.image_urls = media.imageUrls;
  }
  if (media?.voiceInputs?.length) {
    body.voice_inputs = media.voiceInputs;
  }

  const res = await apiFetch("/api/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  const newConvId = res.headers.get("X-Conversation-Id") ?? conversationId;
  if (!newConvId) throw new Error("服务器未返回对话 ID");

  const contentType = res.headers.get("content-type") ?? "";
  if (stream && !contentType.includes("text/event-stream")) {
    throw new Error(await parseError(res));
  }

  if (!stream) {
    const data = (await res.json()) as {
      choices?: { message?: { content?: string } }[];
    };
    const reply = data.choices?.[0]?.message?.content ?? "";
    if (!reply.trim()) throw new Error("模型未返回内容");
    return { reply, conversationId: newConvId };
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("浏览器不支持流式响应");

  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const data = trimmed.slice(5).trim();
      if (data === "[DONE]") continue;
      try {
        const json = JSON.parse(data) as {
          error?: { message?: string } | string;
          choices?: { delta?: { content?: string } }[];
        };
        if (json.error) {
          const msg =
            typeof json.error === "object"
              ? json.error.message
              : String(json.error);
          throw new Error(friendlyError(msg ?? json.error));
        }
        const delta = json.choices?.[0]?.delta?.content;
        if (delta) {
          full += delta;
          if (onDelta) {
            onDelta(full);
            await new Promise<void>((resolve) => {
              requestAnimationFrame(() => resolve());
            });
          }
        }
      } catch (e) {
        if (e instanceof SyntaxError) continue;
        throw e;
      }
    }
  }

  if (!full.trim()) throw new Error("模型未返回内容");
  return { reply: full, conversationId: newConvId };
}
