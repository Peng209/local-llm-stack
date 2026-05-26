import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { marked } from "marked";
import AuthPanel from "./AuthPanel";
import BootScreen from "./BootScreen";
import UserAccountPanel from "./UserAccountPanel";
import { clearAuth, getStoredUser, getToken, setAuth } from "./auth";
import type { ChatConfig, ChatStore, Conversation, Message, User } from "./types";
import { estimateTokens, groupLabel } from "./utils";
import { fileToDataUrl, VoiceRecorder } from "./media";
import { getStreamEnabled, setStreamEnabled } from "./preferences";
import { getThemeMode, setThemeMode, type ThemeMode } from "./theme";
import {
  createConversation,
  deleteConversation,
  fetchConversation,
  fetchConversations,
  fetchMe,
  sendChat,
  waitForBackend,
} from "./api";
import { BrandLogo, BrandIcon, PlusIcon, SendIcon, ImageIcon, MicIcon, WhaleIcon } from "./icons";
import "./index.css";

const SUGGESTIONS = [
  "用 Python 写一段快速排序并解释思路",
  "帮我润色这封邮件，语气专业友好",
  "解释量子纠缠，用通俗比喻",
  "制定一份一周健身计划",
];

function summaryToConv(
  s: { id: string; title: string; created_at: number; updated_at: number },
  messages: Message[] = []
): Conversation {
  return {
    id: s.id,
    title: s.title,
    messages,
    createdAt: s.created_at,
    updatedAt: s.updated_at,
  };
}

function renderMarkdown(text: string): string {
  try {
    return marked.parse(text, { breaks: true }) as string;
  } catch {
    return text;
  }
}

export default function App() {
  const [bootReady, setBootReady] = useState(false);
  const [bootMessage, setBootMessage] = useState("正在连接后端…");
  const [bootError, setBootError] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(() => getStoredUser());
  const [authChecked, setAuthChecked] = useState(false);
  const [store, setStore] = useState<ChatStore>({ conversations: [], activeId: null });
  const [config, setConfig] = useState<ChatConfig>({
    model: "Qwen/Qwen2-VL-2B-Instruct",
    maxContextTokens: 2048,
  });
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamEnabled, setStreamEnabledState] = useState(getStreamEnabled);
  const [themeMode, setThemeModeState] = useState<ThemeMode>(getThemeMode);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [alert, setAlert] = useState<{ msg: string; type: "error" | "warn" } | null>(
    null
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [loadingConvs, setLoadingConvs] = useState(false);
  const [pendingImages, setPendingImages] = useState<string[]>([]);
  const [pendingVoice, setPendingVoice] = useState<{
    base64: string;
    format: string;
  } | null>(null);
  const [recording, setRecording] = useState(false);
  const chatAreaRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const voiceRecorderRef = useRef(new VoiceRecorder());

  const loadConversations = useCallback(async () => {
    setLoadingConvs(true);
    try {
      const list = await fetchConversations();
      const conversations = list.map((s) => summaryToConv(s));
      setStore((prev) => ({
        conversations,
        activeId: prev.activeId && conversations.some((c) => c.id === prev.activeId)
          ? prev.activeId
          : conversations[0]?.id ?? null,
      }));
    } catch (e) {
      setAlert({
        msg: e instanceof Error ? e.message : "加载对话失败",
        type: "error",
      });
    } finally {
      setLoadingConvs(false);
    }
  }, []);

  const boot = useCallback(async () => {
    setBootError(null);
    setBootReady(false);
    setAuthChecked(false);
    try {
      const cfg = await waitForBackend(setBootMessage);
      setConfig(cfg);
      setBootReady(true);
    } catch (e) {
      setBootError(e instanceof Error ? e.message : "后端未就绪");
    }
  }, []);

  useEffect(() => {
    void boot();
  }, [boot]);

  useEffect(() => {
    if (!bootReady) return;
    const token = getToken();
    if (!token) {
      setAuthChecked(true);
      return;
    }
    fetchMe()
      .then((u: User) => {
        setUser(u);
        return loadConversations();
      })
      .catch(() => {
        clearAuth();
        setUser(null);
      })
      .finally(() => setAuthChecked(true));
  }, [bootReady, loadConversations]);

  const handleStreamChange = (enabled: boolean) => {
    setStreamEnabledState(enabled);
    setStreamEnabled(enabled);
  };

  const handleThemeChange = (mode: ThemeMode) => {
    setThemeModeState(mode);
    setThemeMode(mode);
  };

  useEffect(() => {
    if (streamingText === null || !chatAreaRef.current) return;
    chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
  }, [streamingText]);

  const activeConv = useMemo(
    () => store.conversations.find((c) => c.id === store.activeId) ?? null,
    [store]
  );

  const tokenHint = useMemo(() => {
    if (!activeConv?.messages.length) {
      return { text: `上下文上限约 ${config.maxContextTokens} tokens`, warn: false };
    }
    const est = activeConv.messages.reduce(
      (s, m) => s + estimateTokens(m.content),
      0
    );
    const ratio = est / config.maxContextTokens;
    if (ratio >= 0.85) {
      return {
        text: `对话较长（约 ${est}/${config.maxContextTokens} tokens），继续对话可能超出上下文`,
        warn: true,
      };
    }
    if (ratio >= 0.6) {
      return { text: `已用约 ${est}/${config.maxContextTokens} tokens`, warn: false };
    }
    return { text: `上下文上限约 ${config.maxContextTokens} tokens`, warn: false };
  }, [activeConv, config.maxContextTokens]);

  const handleAuth = (token: string, u: User) => {
    setAuth(token, u);
    setUser(u);
    loadConversations();
  };

  const logout = () => {
    clearAuth();
    setUser(null);
    setStore({ conversations: [], activeId: null });
  };

  const newConv = useCallback(async () => {
    try {
      const s = await createConversation();
      const c = summaryToConv(s);
      setStore((prev) => ({
        conversations: [c, ...prev.conversations],
        activeId: c.id,
      }));
      setSidebarOpen(false);
      setAlert(null);
    } catch (e) {
      setAlert({
        msg: e instanceof Error ? e.message : "创建对话失败",
        type: "error",
      });
    }
  }, []);

  const switchConv = async (id: string) => {
    setStore((prev) => ({ ...prev, activeId: id }));
    setSidebarOpen(false);
    setAlert(null);
    const existing = store.conversations.find((c) => c.id === id);
    if (existing && existing.messages.length > 0) return;
    try {
      const detail = await fetchConversation(id);
      const messages: Message[] = detail.messages.map((m) => ({
        role: m.role as Message["role"],
        content: m.content,
      }));
      setStore((prev) => ({
        ...prev,
        conversations: prev.conversations.map((c) =>
          c.id === id ? { ...c, messages, title: detail.title } : c
        ),
      }));
    } catch (e) {
      setAlert({
        msg: e instanceof Error ? e.message : "加载消息失败",
        type: "error",
      });
    }
  };

  const deleteConv = async (id: string) => {
    if (sending) {
      setAlert({ msg: "正在生成回复，请稍后再删除", type: "warn" });
      return;
    }
    try {
      await deleteConversation(id);
      setStore((prev) => {
        const conversations = prev.conversations.filter((c) => c.id !== id);
        let activeId = prev.activeId;
        if (activeId === id) activeId = conversations[0]?.id ?? null;
        return { conversations, activeId };
      });
    } catch (e) {
      setAlert({
        msg: e instanceof Error ? e.message : "删除失败",
        type: "error",
      });
    }
  };

  const clearMedia = () => {
    setPendingImages([]);
    setPendingVoice(null);
  };

  const handleImagePick = async (files: FileList | null) => {
    if (!files?.length) return;
    try {
      const urls: string[] = [];
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
        if (file.size > 8 * 1024 * 1024) {
          setAlert({ msg: "单张图片不能超过 8MB", type: "warn" });
          continue;
        }
        urls.push(await fileToDataUrl(file));
      }
      if (urls.length) {
        setPendingImages((prev) => [...prev, ...urls].slice(0, 4));
        setAlert(null);
      }
    } catch (e) {
      setAlert({
        msg: e instanceof Error ? e.message : "读取图片失败",
        type: "error",
      });
    } finally {
      if (imageInputRef.current) imageInputRef.current.value = "";
    }
  };

  const toggleVoice = async () => {
    const rec = voiceRecorderRef.current;
    if (rec.recording) {
      setRecording(false);
      const clip = await rec.stop();
      if (clip) {
        setPendingVoice(clip);
        setAlert(null);
      } else {
        setAlert({ msg: "未录到有效语音", type: "warn" });
      }
      return;
    }
    try {
      await rec.start();
      setRecording(true);
      setAlert(null);
    } catch {
      setAlert({ msg: "无法访问麦克风，请检查浏览器权限", type: "error" });
    }
  };

  const displayUserContent = (
    text: string,
    images: string[],
    hasVoice: boolean
  ): string => {
    const parts: string[] = [];
    if (text.trim()) parts.push(text.trim());
    if (images.length) parts.push(`[图片×${images.length}]`);
    if (hasVoice) parts.push("[语音×1]");
    return parts.join("\n") || "新消息";
  };

  const sendMessage = async (textOverride?: string) => {
    const text = (textOverride ?? input).trim();
    const images = pendingImages;
    const voice = pendingVoice;
    const hasMedia = images.length > 0 || voice !== null;
    if ((!text && !hasMedia) || sending) return;

    let activeId = store.activeId;
    if (!activeId) {
      try {
        const s = await createConversation();
        activeId = s.id;
        setStore((prev) => ({
          conversations: [summaryToConv(s), ...prev.conversations],
          activeId: s.id,
        }));
      } catch (e) {
        setAlert({
          msg: e instanceof Error ? e.message : "创建对话失败",
          type: "error",
        });
        return;
      }
    }

    setInput("");
    clearMedia();
    setSending(true);
    setAlert(null);
    if (streamEnabled) {
      setStreamingText("");
    } else {
      setStreamingText(null);
    }

    const userDisplay = displayUserContent(text, images, voice !== null);

    setStore((prev) => ({
      ...prev,
      conversations: prev.conversations.map((c) => {
        if (c.id !== activeId) return c;
        const title =
          c.title === "新对话"
            ? userDisplay.slice(0, 32) + (userDisplay.length > 32 ? "…" : "")
            : c.title;
        return {
          ...c,
          messages: [
            ...c.messages,
            { role: "user" as const, content: userDisplay },
          ],
          title,
          updatedAt: Date.now(),
        };
      }),
    }));

    const currentConv = store.conversations.find((c) => c.id === activeId);
    const est =
      (currentConv?.messages.reduce((s, m) => s + estimateTokens(m.content), 0) ??
        0) + estimateTokens(text);
    if (est > config.maxContextTokens * 0.95) {
      setAlert({
        msg: "当前对话已非常接近上下文上限，发送可能失败。建议新建对话后再继续。",
        type: "warn",
      });
    }

    try {
      const { reply, conversationId } = await sendChat(
        text,
        activeId,
        streamEnabled,
        streamEnabled
          ? (text) => flushSync(() => setStreamingText(text))
          : undefined,
        {
          imageUrls: images.length ? images : undefined,
          voiceInputs: voice
            ? [{ base64: voice.base64, format: voice.format }]
            : undefined,
        }
      );
      const convId = conversationId;
      setStore((prev) => {
        let conversations = prev.conversations.map((c) =>
          c.id === activeId || c.id === convId
            ? {
                ...c,
                id: convId,
                messages: [
                  ...c.messages,
                  { role: "assistant" as const, content: reply },
                ],
                updatedAt: Date.now(),
              }
            : c
        );
        if (!conversations.some((c) => c.id === convId)) {
          conversations = [
            {
              id: convId,
              title: userDisplay.slice(0, 32) + (userDisplay.length > 32 ? "…" : ""),
              messages: [
                { role: "user", content: userDisplay },
                { role: "assistant", content: reply },
              ],
              createdAt: Date.now(),
              updatedAt: Date.now(),
            },
            ...conversations,
          ];
        }
        return {
          conversations,
          activeId: convId,
        };
      });
    } catch (e) {
      setStore((prev) => ({
        ...prev,
        conversations: prev.conversations.map((c) =>
          c.id === activeId
            ? { ...c, messages: c.messages.slice(0, -1) }
            : c
        ),
      }));
      setAlert({
        msg: e instanceof Error ? e.message : "请求失败",
        type: "error",
      });
    } finally {
      setStreamingText(null);
      setSending(false);
    }
  };

  const grouped = useMemo(() => {
    const sorted = [...store.conversations].sort((a, b) => b.updatedAt - a.updatedAt);
    const map = new Map<string, Conversation[]>();
    for (const c of sorted) {
      const label = groupLabel(c.updatedAt);
      if (!map.has(label)) map.set(label, []);
      map.get(label)!.push(c);
    }
    return map;
  }, [store.conversations]);

  if (!bootReady) {
    return (
      <BootScreen
        message={bootMessage}
        error={bootError}
        onRetry={() => void boot()}
      />
    );
  }

  if (!authChecked) {
    return <BootScreen message="正在加载账户…" />;
  }

  if (!user) {
    return <AuthPanel onSuccess={handleAuth} />;
  }

  return (
    <>
      <div
        className={`overlay${sidebarOpen ? " visible" : ""}`}
        onClick={() => setSidebarOpen(false)}
      />
      <div className="app">
        <aside className={`sidebar${sidebarOpen ? " open" : ""}`}>
          <header className="sidebar-header">
            <div className="logo">
              <BrandLogo iconSize={28} />
            </div>
            <button
              type="button"
              className="sidebar-toggle"
              aria-label="关闭侧边栏"
              onClick={() => setSidebarOpen(false)}
            >
              ✕
            </button>
          </header>
          <button type="button" className="new-chat-btn" onClick={() => void newConv()}>
            <PlusIcon />
            开启新对话
          </button>
          <nav className="conv-list" aria-label="对话列表">
            {loadingConvs && (
              <div className="conv-group-label">加载对话…</div>
            )}
            {[...grouped.entries()].map(([label, items]) => (
              <div key={label}>
                <div className="conv-group-label">{label}</div>
                {items.map((c) => (
                  <div
                    key={c.id}
                    className={`conv-item${c.id === store.activeId ? " active" : ""}`}
                    onClick={() => void switchConv(c.id)}
                  >
                    <span className="conv-item-title">{c.title || "新对话"}</span>
                    <button
                      type="button"
                      className="conv-delete"
                      title="删除"
                      aria-label="删除对话"
                      disabled={sending}
                      onClick={(e) => {
                        e.stopPropagation();
                        void deleteConv(c.id);
                      }}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            ))}
          </nav>
          <footer className="sidebar-footer">
            <button
              type="button"
              className="account-btn"
              title="账户设置"
              onClick={() => setAccountOpen(true)}
            >
              <span className="account-btn-avatar" aria-hidden>
                {user.email.charAt(0).toUpperCase()}
              </span>
              <span className="account-btn-email">{user.email}</span>
            </button>
          </footer>
        </aside>

        <main className="main">
          <header className="main-header">
            <button
              type="button"
              className="sidebar-toggle"
              aria-label="打开侧边栏"
              onClick={() => setSidebarOpen(true)}
            >
              ☰
            </button>
            <div className="logo">
              <BrandLogo iconSize={24} />
            </div>
          </header>

          <div className="chat-area" id="chatArea" ref={chatAreaRef}>
            {alert && (
              <div className={`alert visible ${alert.type}`} role="alert">
                {alert.msg}
              </div>
            )}
            <div className="chat-inner">
              {!activeConv?.messages.length && streamingText === null ? (
                <div className="empty-state">
                  <div className="empty-logo">
                    <BrandIcon size={64} />
                  </div>
                  <h2 className="empty-title">今天有什么可以帮到你？</h2>
                  <p className="empty-sub">
                    多轮对话保存在服务器；上下文过长时请新建对话
                  </p>
                  <div className="suggestions">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className="suggestion"
                        onClick={() => void sendMessage(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  {activeConv?.messages.map((m, i) => (
                    <div key={i} className={`message ${m.role}`}>
                      <div className="msg-avatar">
                        {m.role === "assistant" ? (
                          <WhaleIcon size={18} />
                        ) : (
                          "我"
                        )}
                      </div>
                      <div className="msg-body">
                        {m.role === "assistant" ? (
                          <div
                            className="msg-content"
                            dangerouslySetInnerHTML={{
                              __html: renderMarkdown(m.content),
                            }}
                          />
                        ) : (
                          <div className="msg-content">{m.content}</div>
                        )}
                      </div>
                    </div>
                  ))}
                  {streamingText !== null && (
                    <div className="message assistant">
                      <div className="msg-avatar">
                        <WhaleIcon size={18} />
                      </div>
                      <div className="msg-body">
                        {streamingText === "" ? (
                          <div className="typing-indicator">
                            <span />
                            <span />
                            <span />
                          </div>
                        ) : (
                          <div
                            className="msg-content"
                            dangerouslySetInnerHTML={{
                              __html: renderMarkdown(streamingText),
                            }}
                          />
                        )}
                      </div>
                    </div>
                  )}
                  {sending && !streamEnabled && streamingText === null && (
                    <div className="message assistant">
                      <div className="msg-avatar">
                        <WhaleIcon size={18} />
                      </div>
                      <div className="msg-body">
                        <div className="typing-indicator">
                          <span />
                          <span />
                          <span />
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <div className="input-area">
            <div className="input-wrap">
              <div className="input-box">
                {(pendingImages.length > 0 || pendingVoice || recording) && (
                  <div className="input-attachments">
                    {pendingImages.map((url, i) => (
                      <div key={i} className="attach-thumb">
                        <img src={url} alt="" />
                        <button
                          type="button"
                          className="attach-remove"
                          aria-label="移除图片"
                          onClick={() =>
                            setPendingImages((prev) =>
                              prev.filter((_, idx) => idx !== i)
                            )
                          }
                        >
                          ×
                        </button>
                      </div>
                    ))}
                    {pendingVoice && (
                      <span className="attach-voice-tag">
                        语音已就绪
                        <button
                          type="button"
                          className="attach-remove-inline"
                          aria-label="移除语音"
                          onClick={() => setPendingVoice(null)}
                        >
                          ×
                        </button>
                      </span>
                    )}
                    {recording && (
                      <span className="attach-recording">正在录音…</span>
                    )}
                  </div>
                )}
                <textarea
                  rows={1}
                  placeholder="发送消息，可附加图片或语音；Shift+Enter 换行"
                  value={input}
                  disabled={sending}
                  onChange={(e) => {
                    setInput(e.target.value);
                    e.target.style.height = "auto";
                    e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`;
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      void sendMessage();
                    }
                  }}
                />
                <div className="input-toolbar">
                  <div className="input-actions">
                    <input
                      ref={imageInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      hidden
                      onChange={(e) => void handleImagePick(e.target.files)}
                    />
                    <button
                      type="button"
                      className="input-action-btn"
                      aria-label="添加图片"
                      disabled={sending || pendingImages.length >= 4}
                      onClick={() => imageInputRef.current?.click()}
                    >
                      <ImageIcon />
                    </button>
                    <button
                      type="button"
                      className={`input-action-btn${recording ? " active" : ""}`}
                      aria-label={recording ? "停止录音" : "录音"}
                      disabled={sending}
                      onClick={() => void toggleVoice()}
                    >
                      <MicIcon />
                    </button>
                  </div>
                  <span className={`input-hint${tokenHint.warn ? " warn" : ""}`}>
                    {tokenHint.text}
                  </span>
                  <button
                    type="button"
                    className="send-btn"
                    aria-label="发送"
                    disabled={
                      sending ||
                      (!input.trim() &&
                        pendingImages.length === 0 &&
                        !pendingVoice)
                    }
                    onClick={() => void sendMessage()}
                  >
                    <SendIcon />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      {accountOpen && (
        <UserAccountPanel
          user={user}
          streamEnabled={streamEnabled}
          themeMode={themeMode}
          onStreamChange={handleStreamChange}
          onThemeChange={handleThemeChange}
          onLogout={logout}
          onClose={() => setAccountOpen(false)}
        />
      )}
    </>
  );
}
