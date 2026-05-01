import { useMemo } from "react";
import { motion } from "framer-motion";
import { mockSubscriptions, getWeeklyDiscoveries } from "@/data/mockSubscriptions";
import { Zap, Calendar } from "lucide-react";

export function SnapshotActivityFeed() {
  const discoveries = useMemo(() => getWeeklyDiscoveries(mockSubscriptions), []);
  const totalNew = discoveries.reduce((acc, d) => acc + d.newConnections, 0);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75 animate-ping" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">This Week</span>
        </div>
        <span className="text-[10px] text-muted-foreground/70 font-mono">+{totalNew}</span>
      </div>

      <div className="px-4 py-3 border-b border-border/40">
        <div className="text-xs text-muted-foreground">Discoveries so far</div>
        <div className="text-2xl font-bold text-foreground mt-0.5">
          {totalNew} <span className="text-xs font-medium text-muted-foreground">new connections</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {discoveries.length === 0 && (
          <div className="text-xs text-muted-foreground px-3 py-6 text-center">
            No new connections discovered this week yet.
          </div>
        )}
        {discoveries.map((d, i) => (
          <motion.div
            key={d.subId}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-secondary/30 transition-colors"
          >
            <div className={`flex-shrink-0 w-7 h-7 rounded-md overflow-hidden flex items-center justify-center ${d.type === "vc" ? "bg-background border border-border/60 p-1" : ""}`}>
              <img
                src={d.logo}
                alt={d.name}
                className={d.type === "vc" ? "w-full h-full object-contain" : "w-full h-full object-cover rounded-md"}
                loading="lazy"
              />
            </div>
            <div className="flex-1 min-w-0 text-xs">
              <div className="font-medium text-foreground truncate">{d.name}</div>
            </div>
            <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-emerald-600">
              <Zap className="h-3 w-3" />
              +{d.newConnections}
            </span>
          </motion.div>
        ))}
      </div>

      <div className="px-4 py-3 border-t border-border/40 flex items-center gap-2 text-[10px] text-muted-foreground">
        <Calendar className="h-3 w-3" />
        <span>Updated continuously · Next full cycle Monday</span>
      </div>
    </div>
  );
}
