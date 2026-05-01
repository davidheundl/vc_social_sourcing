import { useState, useRef, useCallback, useEffect } from "react";
import { Play, Pause } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface TimelineSliderProps {
  startDate: string;
  endDate: string;
  currentDate: string;
  onChange: (date: string) => void;
  notableDays?: { date: string; label: string }[];
}

function getDaysBetween(start: string, end: string): string[] {
  const days: string[] = [];
  const s = new Date(start);
  const e = new Date(end);
  for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) {
    days.push(d.toISOString().split("T")[0]);
  }
  return days;
}

function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function TimelineSlider({
  startDate,
  endDate,
  currentDate,
  onChange,
  notableDays = [],
}: TimelineSliderProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  const playIntervalRef = useRef<number | null>(null);
  const days = getDaysBetween(startDate, endDate);
  const currentIndex = days.indexOf(currentDate);
  const progress = days.length > 1 ? currentIndex / (days.length - 1) : 0;

  // Play auto-advance
  useEffect(() => {
    if (!isPlaying) return;
    const idx = days.indexOf(currentDate);
    if (idx >= days.length - 1) {
      setIsPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      onChange(days[idx + 1]);
    }, 1500);
    return () => clearTimeout(timer);
  }, [isPlaying, currentDate, days, onChange]);

  const handleTrackInteraction = useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track) return;
      const rect = track.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const index = Math.round(ratio * (days.length - 1));
      onChange(days[index]);
    },
    [days, onChange]
  );

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setIsPlaying(false);
    handleTrackInteraction(e.clientX);
  };

  useEffect(() => {
    if (!isDragging) return;
    const handleMove = (e: MouseEvent) => handleTrackInteraction(e.clientX);
    const handleUp = () => setIsDragging(false);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [isDragging, handleTrackInteraction]);

  const togglePlay = () => {
    if (currentIndex >= days.length - 1) {
      // Reset to start and play
      onChange(days[0]);
      setIsPlaying(true);
    } else {
      setIsPlaying((p) => !p);
    }
  };

  const notableSet = new Set(notableDays.map((n) => n.date));

  return (
    <div className="flex items-center gap-3 px-5 py-2.5 bg-card border-t border-border/50">
      {/* Play button */}
      <button
        onClick={togglePlay}
        className="w-7 h-7 rounded-full glass-panel flex items-center justify-center hover:bg-muted/80 transition-colors shrink-0"
      >
        {isPlaying ? (
          <Pause className="h-3 w-3 text-foreground" />
        ) : (
          <Play className="h-3 w-3 text-foreground ml-0.5" />
        )}
      </button>

      {/* Date label */}
      <span className="text-xs font-mono font-semibold text-foreground w-[52px] shrink-0">
        {formatShortDate(currentDate)}
      </span>

      {/* Track */}
      <div className="flex-1 relative group" ref={trackRef}>
        {/* Clickable area */}
        <div
          className="relative h-8 flex items-center cursor-pointer select-none"
          onMouseDown={handleMouseDown}
        >
          {/* Track background */}
          <div className="w-full h-1.5 rounded-full bg-muted/60 relative overflow-visible">
            {/* Filled portion */}
            <motion.div
              className="absolute top-0 left-0 h-full rounded-full bg-primary/40"
              style={{ width: `${progress * 100}%` }}
              layout
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
            />

            {/* Day tick marks */}
            {days.map((day, i) => {
              const pos = (i / (days.length - 1)) * 100;
              const isNotable = notableSet.has(day);
              const isActive = i <= currentIndex;
              const isCurrent = i === currentIndex;
              return (
                <div
                  key={day}
                  className="absolute top-1/2 -translate-y-1/2"
                  style={{ left: `${pos}%` }}
                >
                  <div
                    className={`rounded-full transition-all duration-200 ${
                      isCurrent
                        ? "w-2.5 h-2.5 -ml-[5px] bg-primary shadow-sm"
                        : isNotable
                        ? isActive
                          ? "w-2 h-2 -ml-1 bg-primary"
                          : "w-2 h-2 -ml-1 bg-primary/30"
                        : isActive
                        ? "w-1.5 h-1.5 -ml-[3px] bg-primary/50"
                        : "w-1.5 h-1.5 -ml-[3px] bg-muted-foreground/25"
                    }`}
                  />
                </div>
              );
            })}

            {/* Thumb — plain div so Framer layout transforms cannot override vertical centering */}
            <div
              className="absolute top-1/2 -translate-y-1/2 -ml-2 transition-[left] duration-300 ease-out"
              style={{ left: `${progress * 100}%` }}
            >
              <div
                className={`w-4 h-4 rounded-full bg-primary border-2 border-background shadow-md transition-transform ${
                  isDragging ? "scale-125" : "group-hover:scale-110"
                }`}
              />
            </div>
          </div>

        </div>

        {/* Floating date tooltip when dragging */}
        <AnimatePresence>
          {isDragging && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              className="absolute -top-7 pointer-events-none"
              style={{ left: `${progress * 100}%`, transform: "translateX(-50%)" }}
            >
              <div className="glass-panel px-2 py-0.5 rounded text-[10px] font-mono font-semibold text-foreground whitespace-nowrap">
                {formatShortDate(currentDate)}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* End date */}
      <span className="text-[10px] text-muted-foreground font-mono shrink-0">
        {formatShortDate(endDate)}
      </span>
    </div>
  );
}
