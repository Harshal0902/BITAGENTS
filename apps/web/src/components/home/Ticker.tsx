export function Ticker() {
  const items = [
    { sym: "H100·8x", px: "0.481", ch: "+2.4%" },
    { sym: "A100·40G", px: "0.293", ch: "-0.8%" },
    { sym: "RTX4090", px: "0.124", ch: "+1.1%" },
    { sym: "INFER·L70", px: "0.067", ch: "+4.2%" },
    { sym: "cGPU·IDX", px: "0.415", ch: "+0.6%" },
    { sym: "VAULT·GRW", px: "1.082", ch: "+8.4%" },
    { sym: "VAULT·CON", px: "1.014", ch: "+1.4%" },
    { sym: "H200·8x", px: "0.612", ch: "+3.7%" },
  ];
  const row = [...items, ...items];
  return (
    <div className="border-b border-grid bg-surface/40">
      <div className="ticker-mask overflow-hidden">
        <div className="flex w-max animate-ticker gap-10 px-6 py-3 font-mono text-xs">
          {row.map((it, i) => (
            <span key={i} className="flex items-center gap-3 whitespace-nowrap">
              <span className="text-muted-foreground">{it.sym}</span>
              <span className="tabular-nums">{it.px}</span>
              <span className={it.ch.startsWith("+") ? "text-signal" : "text-destructive"}>{it.ch}</span>
              <span className="text-muted-foreground/50">·</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}