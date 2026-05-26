export async function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new Error("读取图片失败"));
    reader.readAsDataURL(file);
  });
}

export async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(new Error("读取音频失败"));
    reader.readAsDataURL(blob);
  });
}

export function pickRecorderMime(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const t of candidates) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return "";
}

export function mimeToVoiceFormat(mime: string): string {
  const base = mime.split(";")[0]?.trim().toLowerCase() ?? "webm";
  if (base.includes("webm")) return "webm";
  if (base.includes("ogg")) return "ogg";
  if (base.includes("mp4") || base.includes("m4a")) return "mp4";
  if (base.includes("wav")) return "wav";
  return "webm";
}

export class VoiceRecorder {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];

  get recording(): boolean {
    return this.recorder?.state === "recording";
  }

  async start(): Promise<void> {
    if (this.recording) return;
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = pickRecorderMime();
    this.chunks = [];
    this.recorder = mime
      ? new MediaRecorder(this.stream, { mimeType: mime })
      : new MediaRecorder(this.stream);
    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.recorder.start();
  }

  async stop(): Promise<{ base64: string; format: string } | null> {
    const rec = this.recorder;
    if (!rec || rec.state === "inactive") {
      this.cleanup();
      return null;
    }

    return new Promise((resolve) => {
      rec.onstop = async () => {
        const mime = rec.mimeType || "audio/webm";
        const blob = new Blob(this.chunks, { type: mime });
        this.cleanup();
        if (!blob.size) {
          resolve(null);
          return;
        }
        try {
          resolve({
            base64: await blobToBase64(blob),
            format: mimeToVoiceFormat(mime),
          });
        } catch {
          resolve(null);
        }
      };
      rec.stop();
    });
  }

  cancel(): void {
    if (this.recorder && this.recorder.state !== "inactive") {
      this.recorder.onstop = null;
      this.recorder.stop();
    }
    this.cleanup();
  }

  private cleanup(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.recorder = null;
    this.chunks = [];
  }
}
