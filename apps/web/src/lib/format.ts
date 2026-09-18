/** Small date helpers shared by the plan screens. Dates are ISO strings (YYYY-MM-DD) from the API. */

export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** "Thu 18 Sep" */
export function shortDay(iso: string): string {
  return parseDate(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

/** "Today, Thu 18 Sep" or "Tomorrow, …" */
export function dayHeading(iso: string): string {
  const today = todayIso();
  const label = shortDay(iso);
  if (iso === today) return `Today, ${label}`;
  const t = parseDate(today);
  t.setDate(t.getDate() + 1);
  const tomorrow = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
  return iso === tomorrow ? `Tomorrow, ${label}` : label;
}

export function titleCase(slug: string): string {
  return slug.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function listJoin(items: string[]): string {
  return items.join(", ");
}
