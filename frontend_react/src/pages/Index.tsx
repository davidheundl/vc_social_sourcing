import { useState, useMemo, useEffect } from "react";
import { Founder, VCNode } from "@/data/mockFounders";
import { useFounders, useVCNodes } from "@/hooks/useFounders";
import { FounderRow } from "@/components/FounderRow";
import { NetworkGraph } from "@/components/NetworkGraph";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Radar, Flame, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";

export default function Index() {
  const { data: fetchedFounders = [], isLoading } = useFounders();
  const { data: liveVCNodes = [] } = useVCNodes();
  const [founders, setFounders] = useState<Founder[]>([]);
  const [search, setSearch] = useState("");
  const [activity, setActivity] = useState("all");
  const [scoreRange, setScoreRange] = useState("all");
  const [vcFilter, setVcFilter] = useState("all");

  useEffect(() => {
    if (fetchedFounders.length > 0) setFounders(fetchedFounders);
  }, [fetchedFounders]);

  const allVCs = useMemo(() => {
    const set = new Set<string>();
    founders.forEach(f => f.followedVCs.forEach(c => set.add(c.vc)));
    return Array.from(set).sort();
  }, [founders]);

  const filtered = useMemo(() => {
    return founders
      .filter((f) => {
        if (search && !f.name.toLowerCase().includes(search.toLowerCase()) &&
          !(f.title + " " + f.company).toLowerCase().includes(search.toLowerCase())) return false;
        if (activity !== "all" && f.activity !== activity) return false;
        if (scoreRange === "40+" && f.score < 40) return false;
        if (scoreRange === "20-39" && (f.score < 20 || f.score >= 40)) return false;
        if (scoreRange === "<20" && f.score >= 20) return false;
        if (vcFilter !== "all" && !f.followedVCs.some(c => c.vc === vcFilter)) return false;
        return true;
      })
      .sort((a, b) => b.score - a.score);
  }, [founders, search, activity, scoreRange, vcFilter]);

  const hotCount = founders.filter(f => f.activity === "hot").length;

  const exportCSV = () => {
    const headers = ["Rank", "Name", "Title", "Company", "Score", "Activity", "LinkedIn", "X", "VC Connections", "Signals"];
    const rows = filtered.map((f, i) => [
      i + 1, f.name, f.title, f.company, f.score, f.activity,
      f.linkedinUrl, f.xUrl,
      f.followedVCs.map(c => c.vc).join("; "),
      f.signals.join("; "),
    ]);
    const csv = [headers, ...rows].map(r => r.map(c => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "founder-radar.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* Header */}
      <header className="absolute top-0 left-0 right-0 z-50 pointer-events-none">
        <div className="max-w-[1600px] mx-auto px-5 pt-4 flex items-center justify-between">
          <div className="flex items-center gap-3 glass-panel px-3.5 py-2 rounded-xl pointer-events-auto">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
                <Radar className="h-3.5 w-3.5 text-primary-foreground" />
              </div>
              <h1 className="text-sm font-bold tracking-tight">Founder Radar</h1>
            </div>
            <span className="w-px h-4 bg-border/50" />
            <a href="/dashboard" className="px-2.5 py-1 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors">
              ← Classic
            </a>
          </div>
          <div className="flex items-center gap-3 glass-panel px-3.5 py-2 rounded-xl pointer-events-auto text-xs">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <Flame className="h-3.5 w-3.5 text-orange-500" />
              <span className="font-semibold text-foreground">{hotCount}</span> hot
            </span>
            <span className="w-px h-4 bg-border" />
            <span className="text-muted-foreground font-mono">
              {isLoading ? "loading…" : `${filtered.length} founders`}
            </span>
          </div>
        </div>
      </header>

      {/* Main split */}
      <div className="flex-1 flex min-h-0">
        {/* Left — graph */}
        <div className="relative w-1/2 border-r border-border min-h-0 overflow-hidden">
          <NetworkGraph
            founders={filtered}
            allFounders={founders}
            currentDate={new Date().toISOString().split("T")[0]}
            vcNodesOverride={liveVCNodes.length > 0 ? liveVCNodes : undefined}
          />
        </div>

        {/* Right — list */}
        <div className="w-1/2 flex flex-col min-h-0 bg-card">
          {/* Filter strip */}
          <div className="flex items-center gap-2 px-5 py-2.5 border-b border-border/50 flex-wrap">
            <div className="relative w-[180px]">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-8 text-xs bg-secondary/50 border-border/50"
              />
            </div>

            <Select value={activity} onValueChange={setActivity}>
              <SelectTrigger className="w-[110px] h-8 text-xs bg-secondary/50 border-border/50">
                <SelectValue placeholder="Activity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Activity</SelectItem>
                <SelectItem value="hot">🔥 Hot</SelectItem>
                <SelectItem value="warm">🟡 Warm</SelectItem>
                <SelectItem value="cold">❄️ Cold</SelectItem>
              </SelectContent>
            </Select>

            <Select value={scoreRange} onValueChange={setScoreRange}>
              <SelectTrigger className="w-[110px] h-8 text-xs bg-secondary/50 border-border/50">
                <SelectValue placeholder="Score" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Scores</SelectItem>
                <SelectItem value="40+">40+</SelectItem>
                <SelectItem value="20-39">20–39</SelectItem>
                <SelectItem value="<20">&lt; 20</SelectItem>
              </SelectContent>
            </Select>

            <Select value={vcFilter} onValueChange={setVcFilter}>
              <SelectTrigger className="w-[130px] h-8 text-xs bg-secondary/50 border-border/50">
                <SelectValue placeholder="VC" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All VCs</SelectItem>
                {allVCs.map(vc => (
                  <SelectItem key={vc} value={vc}>{vc}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="flex-1" />
            <Button variant="ghost" size="sm" onClick={exportCSV} className="gap-1.5 text-xs h-8 text-muted-foreground">
              <Download className="h-3.5 w-3.5" /> CSV
            </Button>
          </div>

          {/* Column headers */}
          <div className="grid grid-cols-[32px_1fr_1fr_90px_70px_28px] gap-3 px-5 py-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider sticky top-0 bg-card z-10 border-b border-border/30">
            <span>#</span>
            <span>Founder</span>
            <span>Why</span>
            <span className="text-center">Score</span>
            <span>Activity</span>
            <span></span>
          </div>

          {/* Rows */}
          <div className="flex-1 overflow-y-auto divide-y divide-border/30">
            {filtered.map((founder, i) => (
              <FounderRow key={founder.id} founder={founder} rank={i + 1} />
            ))}
            {!isLoading && filtered.length === 0 && (
              <div className="px-5 py-12 text-center text-muted-foreground text-sm">
                No founders match your filters.
              </div>
            )}
            {isLoading && (
              <div className="px-5 py-12 text-center text-muted-foreground text-sm">
                Loading…
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
