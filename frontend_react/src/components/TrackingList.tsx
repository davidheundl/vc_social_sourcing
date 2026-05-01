import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Subscription, getSnapshotStatus, timeAgo, timeUntil } from "@/data/mockSubscriptions";
import { Trash2, Building2, User, CheckCircle2, Clock, Loader2, MoreHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";

interface TrackingListProps {
  subscriptions: Subscription[];
  onTogglePause: (id: string) => void;
  onRemove: (id: string) => void;
}

function StatusPill({ sub }: { sub: Subscription }) {
  const status = getSnapshotStatus(sub);

  if (sub.isPaused) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Clock className="h-3 w-3" />
        Paused
      </span>
    );
  }

  if (status === "up_to_date") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-emerald-600">
        <CheckCircle2 className="h-3 w-3" />
        Scanned {timeAgo(sub.lastSnapshotAt).toLowerCase()}
        <span className="text-muted-foreground/60">· next {timeUntil(sub.nextSnapshotAt)}</span>
      </span>
    );
  }

  if (status === "stale") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-amber-600">
        <Clock className="h-3 w-3" />
        Scanning soon
        <span className="text-muted-foreground/60">· next {timeUntil(sub.nextSnapshotAt)}</span>
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-sky-600">
      <Loader2 className="h-3 w-3 animate-spin" />
      Catching up
      <span className="text-muted-foreground/60">· last {timeAgo(sub.lastSnapshotAt).toLowerCase()}</span>
    </span>
  );
}

function TypeBadge({ type }: { type: "vc" | "angel" }) {
  if (type === "vc") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-primary/10 text-primary">
        <Building2 className="h-2.5 w-2.5" />
        VC
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-amber-500/10 text-amber-600">
      <User className="h-2.5 w-2.5" />
      Angel
    </span>
  );
}

export function TrackingList({ subscriptions, onTogglePause, onRemove }: TrackingListProps) {
  return (
    <div className="space-y-1.5">
      <AnimatePresence>
        {subscriptions.map((sub, i) => (
          <motion.div
            key={sub.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: -40, height: 0 }}
            transition={{ delay: i * 0.03 }}
            className={`group relative flex items-center gap-4 px-4 py-3 rounded-xl border border-border/40 bg-card hover:bg-secondary/30 transition-colors ${sub.isPaused ? "opacity-60" : ""}`}
          >
            {/* Identity */}
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className={`flex-shrink-0 w-10 h-10 rounded-lg overflow-hidden flex items-center justify-center ${sub.type === "vc" ? "bg-background border border-border/60 p-1.5" : ""}`}>
                <img
                  src={sub.logo}
                  alt={sub.name}
                  className={sub.type === "vc" ? "w-full h-full object-contain" : "w-full h-full object-cover rounded-lg"}
                  loading="lazy"
                />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm truncate">{sub.name}</span>
                  <TypeBadge type={sub.type} />
                </div>
                <div className="text-xs text-muted-foreground truncate mt-0.5">
                  {sub.type === "vc" ? sub.firm : sub.role} · {sub.sector}
                </div>
              </div>
            </div>

            {/* Status */}
            <div className="hidden md:flex items-center min-w-[220px]">
              <StatusPill sub={sub} />
            </div>

            {/* Controls */}
            <div className="flex items-center gap-2">
              <Switch
                checked={!sub.isPaused}
                onCheckedChange={() => onTogglePause(sub.id)}
                className="data-[state=checked]:bg-emerald-500"
              />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-foreground"
                  >
                    <MoreHorizontal className="h-3.5 w-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-40">
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => {
                      onRemove(sub.id);
                      toast.success(`${sub.name} removed`);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5 mr-2" />
                    Stop tracking
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
