const STREAM_KEY = "my_vllm_stream";

export function getStreamEnabled(): boolean {
  const v = localStorage.getItem(STREAM_KEY);
  if (v === null) return true;
  return v === "1";
}

export function setStreamEnabled(enabled: boolean): void {
  localStorage.setItem(STREAM_KEY, enabled ? "1" : "0");
}
