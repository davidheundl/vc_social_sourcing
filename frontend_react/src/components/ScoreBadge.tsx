import { cn } from "@/lib/utils";

interface ScoreBadgeProps {
  score: number;
  size?: "sm" | "md" | "lg";
}

export function ScoreBadge({ score, size = "md" }: ScoreBadgeProps) {
  const getScoreColor = () => {
    if (score >= 80) return "text-score-high border-score-high/30 bg-score-high/10";
    if (score >= 60) return "text-score-medium border-score-medium/30 bg-score-medium/10";
    return "text-score-low border-score-low/30 bg-score-low/10";
  };

  const sizeClasses = {
    sm: "w-8 h-8 text-xs",
    md: "w-10 h-10 text-sm",
    lg: "w-14 h-14 text-lg",
  };

  return (
    <div
      className={cn(
        "rounded-full border font-mono font-semibold flex items-center justify-center",
        getScoreColor(),
        sizeClasses[size]
      )}
    >
      {score}
    </div>
  );
}
