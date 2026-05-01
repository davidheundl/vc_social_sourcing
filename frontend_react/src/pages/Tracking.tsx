import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { mockSubscriptions, Subscription, getWeeklyProgress } from "@/data/mockSubscriptions";
import { TrackingList } from "@/components/TrackingList";
import { SnapshotActivityFeed } from "@/components/SnapshotActivityFeed";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Radar, Eye, Plus, Search, Building2, User, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function Tracking() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>(mockSubscriptions);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [addOpen, setAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<"vc" | "angel">("vc");
  const [newLinkedin, setNewLinkedin] = useState("");

  const progress = useMemo(() => getWeeklyProgress(subscriptions), [subscriptions]);

  const filtered = useMemo(() => {
    return subscriptions.filter(s => {
      if (search && !s.name.toLowerCase().includes(search.toLowerCase()) && !s.firm.toLowerCase().includes(search.toLowerCase())) return false;
      if (typeFilter === "vc" && s.type !== "vc") return false;
      if (typeFilter === "angel" && s.type !== "angel") return false;
      return true;
    });
  }, [subscriptions, search, typeFilter]);

  const handleTogglePause = (id: string) => {
    setSubscriptions(prev => prev.map(s => {
      if (s.id !== id) return s;
      const paused = !s.isPaused;
      toast(paused ? `${s.name} paused` : `${s.name} resumed`);
      return { ...s, isPaused: paused };
    }));
  };

  const handleRemove = (id: string) => {
    setSubscriptions(prev => prev.filter(s => s.id !== id));
  };

  const handleAdd = () => {
    if (!newName.trim()) return;
    const now = new Date();
    const sub: Subscription = {
      id: `sub-manual-${Date.now()}`,
      name: newName.trim(),
      logo: newType === "vc" ? "/logos/a16z.png" : "/avatars/vc-richard-chen.jpg",
      type: newType,
      role: newType === "vc" ? "Venture Capital Firm" : "Angel Investor",
      firm: newType === "vc" ? newName.trim() : "Independent",
      sector: "General",
      linkedinUrl: newLinkedin.trim() || "https://linkedin.com",
      source: "manual",
      isPaused: false,
      lastSnapshotAt: now,
      nextSnapshotAt: new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000),
      totalSnapshots: 0,
      connectionCount: 0,
      addedAt: now,
    };
    setSubscriptions(prev => [sub, ...prev]);
    toast.success(`${newName} added to tracking`);
    setNewName("");
    setNewLinkedin("");
    setAddOpen(false);
  };

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="max-w-[1400px] mx-auto px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
                <Radar className="h-3.5 w-3.5 text-primary-foreground" />
              </div>
              <h1 className="text-sm font-bold tracking-tight">Founder Radar</h1>
            </div>

            {/* Nav tabs */}
            <nav className="flex items-center gap-1 ml-4">
              <Link
                to="/"
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Radar className="h-3.5 w-3.5" />
                  Radar
                </span>
              </Link>
              <span className="px-3 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary">
                <span className="flex items-center gap-1.5">
                  <Eye className="h-3.5 w-3.5" />
                  Tracking
                </span>
              </span>
            </nav>
          </div>

          <Dialog open={addOpen} onOpenChange={setAddOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="gap-1.5 text-xs">
                <Plus className="h-3.5 w-3.5" />
                Add to Tracking
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Add to Tracking</DialogTitle>
              </DialogHeader>
              <div className="space-y-3 pt-2">
                <Select value={newType} onValueChange={(v) => setNewType(v as "vc" | "angel")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="vc">
                      <span className="flex items-center gap-2"><Building2 className="h-3.5 w-3.5" /> VC Firm</span>
                    </SelectItem>
                    <SelectItem value="angel">
                      <span className="flex items-center gap-2"><User className="h-3.5 w-3.5" /> Angel Investor</span>
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  placeholder={newType === "vc" ? "Firm name (e.g. Benchmark)" : "Full name"}
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                />
                <Input
                  placeholder="LinkedIn URL"
                  value={newLinkedin}
                  onChange={e => setNewLinkedin(e.target.value)}
                />
                <Button onClick={handleAdd} className="w-full" disabled={!newName.trim()}>
                  Start Tracking
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </header>

      {/* Hero Status Banner */}
      <div className="border-b border-border/50 bg-gradient-to-r from-primary/5 via-card/50 to-emerald-500/5">
        <div className="max-w-[1400px] mx-auto px-5 py-5 flex items-center gap-6 flex-wrap">
          <div className="flex items-center gap-3 flex-1 min-w-[280px]">
            <div className="relative flex-shrink-0 w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-emerald-600" />
              <span className="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75 animate-ping" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
              </span>
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-foreground">
                Scanning {progress.total} investors continuously
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                This week: <span className="font-semibold text-foreground">{progress.scanned}</span> of {progress.total} snapshots complete
                {" · "}
                <span className="font-semibold text-emerald-600">{progress.newConnectionsThisWeek} new connections</span> discovered
              </div>
            </div>
          </div>

          <div className="flex-1 min-w-[200px] max-w-md">
            <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
              <span>Weekly cycle</span>
              <span className="font-mono text-foreground">{progress.percent}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-primary transition-all duration-700"
                style={{ width: `${progress.percent}%` }}
              />
            </div>
          </div>

          <div className="text-xs text-muted-foreground">
            Next sync window: <span className="font-semibold text-foreground">{progress.nextLabel}</span>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex min-h-0 max-w-[1400px] mx-auto w-full">
        {/* Tracking list */}
        <div className="flex-1 flex flex-col min-h-0 px-5 py-4">
          {/* Filters */}
          <div className="flex items-center gap-2 mb-3">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search tracked profiles..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-8 h-8 text-xs bg-secondary/50 border-border/50"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-[120px] h-8 text-xs bg-secondary/50 border-border/50">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="vc">VCs Only</SelectItem>
                <SelectItem value="angel">Angels Only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto">
            <TrackingList
              subscriptions={filtered}
              onTogglePause={handleTogglePause}
              onRemove={handleRemove}
            />
          </div>
        </div>

        {/* Activity Feed sidebar */}
        <div className="w-[300px] border-l border-border bg-card/30 hidden md:flex flex-col">
          <SnapshotActivityFeed />
        </div>
      </div>
    </div>
  );
}
