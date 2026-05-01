import { mockFounders } from "@/data/mockFounders";
import { Users, Flame, TrendingUp, Globe } from "lucide-react";

export function StatsCards() {
  const total = mockFounders.length;
  const hot = mockFounders.filter((f) => f.activity === "hot").length;
  const avgScore = Math.round(mockFounders.reduce((a, f) => a + f.score, 0) / total);
  const countries = new Set(mockFounders.map((f) => f.country)).size;

  const stats = [
    { label: "Tracked Founders", value: total, icon: Users, accent: "text-primary" },
    { label: "Hot Leads", value: hot, icon: Flame, accent: "text-score-high" },
    { label: "Avg Score", value: avgScore, icon: TrendingUp, accent: "text-score-medium" },
    { label: "Countries", value: countries, icon: Globe, accent: "text-primary" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((s) => (
        <div key={s.label} className="glass rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{s.label}</span>
            <s.icon className={`h-4 w-4 ${s.accent}`} />
          </div>
          <p className="text-2xl font-bold font-mono">{s.value}</p>
        </div>
      ))}
    </div>
  );
}
