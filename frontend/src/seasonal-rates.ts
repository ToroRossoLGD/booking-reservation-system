export type SeasonalRate = { start: string; end: string; price_cents: number; label: string };
export function readSeasonalRates(fields: FormData): SeasonalRate[] {
  const ends = fields.getAll("season_end");
  const prices = fields.getAll("season_price");
  const labels = fields.getAll("season_label");
  const rates = fields.getAll("season_start").map((start, index) => ({
    start: String(start), end: String(ends[index]),
    price_cents: Math.round(Number(prices[index]) * 100), label: String(labels[index] ?? "").trim(),
  })).sort((a, b) => a.start.localeCompare(b.start));
  if (rates.some((rate, index) => rate.end <= rate.start || (index > 0 && rates[index - 1].end > rate.start)))
    throw new Error("Sezonski periodi ne smeju da se preklapaju. Završni datum mora biti posle početnog.");
  return rates;
}
