/** Show only the last 8 chars of a (long) test-program rev; full value goes in a tooltip. */
export function last8(rev: string): string {
  if (!rev) return "";
  return rev.length > 8 ? rev.slice(-8) : rev;
}
