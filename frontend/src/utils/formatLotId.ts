export type LotIdFormat = "raw" | "date" | "yearweek";

const STORAGE_KEY = "dashboard.lotIdFormat";

export function getLotIdFormat(): LotIdFormat {
  const v = localStorage.getItem(STORAGE_KEY);
  return v === "date" || v === "yearweek" ? v : "raw";
}

export function setLotIdFormat(mode: LotIdFormat): void {
  localStorage.setItem(STORAGE_KEY, mode);
}

function isoWeek(d: Date): string {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const week = Math.ceil((((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}

export function formatLotId(lotId: string, lotDate: string, mode: LotIdFormat): string {
  if (mode === "date") return lotDate;
  if (mode === "yearweek") {
    const d = new Date(lotDate);
    return isNaN(d.getTime()) ? lotId : isoWeek(d);
  }
  return lotId;
}
