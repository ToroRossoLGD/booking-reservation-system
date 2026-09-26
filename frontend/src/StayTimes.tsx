export default function StayTimes({ check_in_time, check_out_time, timezone }: { check_in_time?: string | null; check_out_time?: string | null; timezone?: string }) {
  return <p>{check_in_time && check_out_time ? <>Prijava od {check_in_time} · Odjava do {check_out_time} ({timezone ?? "Europe/Belgrade"})</> : "Vreme prijave i odjave nije navedeno. Dogovori se sa domaćinom."}</p>;
}
