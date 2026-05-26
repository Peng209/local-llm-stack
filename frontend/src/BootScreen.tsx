interface Props {
  message: string;
  error?: string | null;
  onRetry?: () => void;
}

export default function BootScreen({ message, error, onRetry }: Props) {
  return (
    <div className="boot-screen">
      <div className="boot-card">
        <div className="boot-spinner" aria-hidden />
        <p className="boot-title">{error ? "连接失败" : "正在启动"}</p>
        <p className="boot-sub">{error ?? message}</p>
        {error && onRetry && (
          <button type="button" className="boot-retry" onClick={onRetry}>
            重试
          </button>
        )}
      </div>
    </div>
  );
}
