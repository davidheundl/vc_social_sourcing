import { cn } from "@/lib/utils";

interface ActivityBadgeProps {
  activity: "hot" | "warm" | "cold";
}

export function ActivityBadge({ activity }: ActivityBadgeProps) {
  const config = {
    hot: { label: "Hot", className: "bg-score-high/10 text-score-high border-score-high/20" },
    warm: { label: "Warm", className: "bg-score-medium/10 text-score-medium border-score-medium/20" },
    cold: { label: "Cold", className: "bg-muted text-muted-foreground border-border" },
  };

  const { label, className } = config[activity];

  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", className)}>
      <span className={cn("w-1.5 h-1.5 rounded-full", {
        "bg-score-high animate-pulse-glow": activity === "hot",
        "bg-score-medium": activity === "warm",
        "bg-muted-foreground": activity === "cold",
      })} />
      {label}
    </span>
  );
}
