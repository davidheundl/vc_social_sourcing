import { Founder } from "@/data/mockFounders";
import { ScoreBadge } from "./ScoreBadge";
import { ActivityBadge } from "./ActivityBadge";
import { Linkedin, Twitter, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface FounderRowProps {
  founder: Founder;
  rank: number;
}

export function FounderRow({ founder, rank }: FounderRowProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="group">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full grid grid-cols-[32px_1fr_1fr_90px_70px_28px] items-center gap-3 px-4 py-2.5 hover:bg-muted/50 transition-colors text-left"
      >
        <span className="text-muted-foreground font-mono text-xs">#{rank}</span>

        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-full bg-primary/10 overflow-hidden shrink-0">
            <img src={founder.avatar} alt={founder.name} className="w-full h-full object-cover" loading="lazy"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
          </div>
          <div className="min-w-0">
            <p className="font-medium text-sm text-foreground truncate">{founder.name}</p>
            <p className="text-[11px] text-muted-foreground truncate">
              {[founder.title, founder.company].filter(Boolean).join(" · ") || founder.xUrl}
            </p>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground truncate italic">{founder.scoreExplanation}</p>

        <div className="flex justify-center">
          <ScoreBadge score={founder.score} size="sm" />
        </div>

        <ActivityBadge activity={founder.activity} />

        {expanded
          ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pl-14 grid grid-cols-2 gap-6">
              <div>
                <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Signals</h4>
                <div className="flex flex-wrap gap-1">
                  {founder.signals.map((signal) => (
                    <span key={signal} className="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px] font-medium">
                      {signal}
                    </span>
                  ))}
                </div>

                <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mt-3 mb-1">VC Connections</h4>
                <div className="flex flex-wrap gap-1">
                  {founder.followedVCs.map((conn) => (
                    <span key={conn.vc} className="px-1.5 py-0.5 rounded bg-accent/10 text-accent text-[10px] font-medium">
                      {conn.vc}
                    </span>
                  ))}
                  {founder.followedVCs.length === 0 && (
                    <span className="text-[11px] text-muted-foreground">—</span>
                  )}
                </div>
              </div>

              <div>
                <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">Links</h4>
                <div className="flex gap-3 mb-3">
                  {founder.linkedinUrl && (
                    <a href={founder.linkedinUrl} target="_blank" rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline">
                      <Linkedin className="h-3.5 w-3.5" /> LinkedIn
                    </a>
                  )}
                  {founder.xUrl && (
                    <a href={founder.xUrl} target="_blank" rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline">
                      <Twitter className="h-3.5 w-3.5" /> X / Twitter
                    </a>
                  )}
                </div>
                {founder.country && (
                  <p className="text-[11px] text-muted-foreground">📍 {founder.country}</p>
                )}
                <p className="text-[11px] text-muted-foreground mt-1">Discovered: {founder.discoveredWeek}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
