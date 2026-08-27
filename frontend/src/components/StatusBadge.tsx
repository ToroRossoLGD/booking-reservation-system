export function StatusBadge({ value }: { value: string }) {
  return (
    <span className={`status-badge status-${value}`} data-status={value}>
      {value.replaceAll("_", " ")}
    </span>
  );
}
