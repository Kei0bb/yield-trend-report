export async function copyGridToClipboard(container: HTMLElement): Promise<void> {
  const dpr = window.devicePixelRatio || 1;
  const w = container.scrollWidth;
  const h = container.scrollHeight;
  const off = document.createElement("canvas");
  off.width = Math.ceil(w * dpr);
  off.height = Math.ceil(h * dpr);
  const ctx = off.getContext("2d");
  if (!ctx) throw new Error("no 2d context");
  ctx.scale(dpr, dpr);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, w, h);
  const base = container.getBoundingClientRect();
  // wafer canvases
  container.querySelectorAll("canvas").forEach((cv) => {
    const r = cv.getBoundingClientRect();
    const x = r.left - base.left + container.scrollLeft;
    const y = r.top - base.top + container.scrollTop;
    ctx.drawImage(cv as HTMLCanvasElement, x, y, r.width, r.height);
  });
  // header/lot text labels
  container.querySelectorAll("th").forEach((th) => {
    const text = (th.textContent || "").trim();
    if (!text) return;
    const r = th.getBoundingClientRect();
    const cs = getComputedStyle(th);
    ctx.fillStyle = cs.color;
    ctx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    ctx.textBaseline = "middle";
    ctx.textAlign = (cs.textAlign === "right" ? "right" : cs.textAlign === "left" ? "left" : "center");
    const padX = ctx.textAlign === "right" ? r.width - 4 : ctx.textAlign === "left" ? 4 : r.width / 2;
    const x = r.left - base.left + container.scrollLeft + padX;
    const y = r.top - base.top + container.scrollTop + r.height / 2;
    ctx.fillText(text, x, y);
  });
  const blob: Blob = await new Promise((res, rej) =>
    off.toBlob((b) => (b ? res(b) : rej(new Error("toBlob failed"))), "image/png"),
  );
  await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
}
