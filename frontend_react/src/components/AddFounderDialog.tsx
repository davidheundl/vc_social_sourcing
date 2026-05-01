import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Sparkles } from "lucide-react";
import { Founder, getDiscoveredWeekLabel } from "@/data/mockFounders";
import { toast } from "sonner";

interface AddFounderDialogProps {
  onAdd: (founder: Founder) => void;
}

export function AddFounderDialog({ onAdd }: AddFounderDialogProps) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [country, setCountry] = useState("United States");
  const [sector, setSector] = useState("AI / ML");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [xUrl, setXUrl] = useState("");
  const [enriching, setEnriching] = useState(false);

  const handleAdd = () => {
    if (!name.trim()) return;
    const initials = name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
    const founder: Founder = {
      id: `manual-${Date.now()}`,
      name: name.trim(),
      avatar: initials,
      title: title.trim() || "Unknown",
      company: company.trim() || "Unknown",
      country,
      sector,
      score: 0,
      scoreExplanation: "Manually added — awaiting enrichment.",
      scoreSummary: "Manual add — run enrichment to score",
      activity: "cold",
      status: "new",
      linkedinUrl: linkedinUrl.trim() || "https://linkedin.com",
      xUrl: xUrl.trim() || "https://x.com",
      vcConnections: [],
      followedVCs: [],
      lastActivity: "Just added",
      signals: ["Manually added"],
      addedAt: new Date().toISOString().split("T")[0],
      discoveredWeek: getDiscoveredWeekLabel(new Date().toISOString().split("T")[0]),
      isManual: true,
      history: [{ date: new Date().toISOString().split("T")[0], score: 0, activity: "cold" as const }],
    };
    onAdd(founder);
    toast.success(`${name} added to pipeline`);
    setName(""); setTitle(""); setCompany(""); setLinkedinUrl(""); setXUrl("");
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Plus className="h-3.5 w-3.5" /> Add Candidate
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Candidate Manually</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 pt-2">
          <Input placeholder="Full name *" value={name} onChange={e => setName(e.target.value)} />
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="Title / Role" value={title} onChange={e => setTitle(e.target.value)} />
            <Input placeholder="Company" value={company} onChange={e => setCompany(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Select value={country} onValueChange={setCountry}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="United States">United States</SelectItem>
                <SelectItem value="United Kingdom">United Kingdom</SelectItem>
                <SelectItem value="Germany">Germany</SelectItem>
                <SelectItem value="Sweden">Sweden</SelectItem>
                <SelectItem value="Singapore">Singapore</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sector} onValueChange={setSector}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="AI / ML">AI / ML</SelectItem>
                <SelectItem value="Fintech">Fintech</SelectItem>
                <SelectItem value="Consumer">Consumer</SelectItem>
                <SelectItem value="Logistics">Logistics</SelectItem>
                <SelectItem value="Developer Tools">Dev Tools</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="LinkedIn URL" value={linkedinUrl} onChange={e => setLinkedinUrl(e.target.value)} />
            <Input placeholder="X / Twitter URL" value={xUrl} onChange={e => setXUrl(e.target.value)} />
          </div>
          <div className="flex gap-2 pt-2">
            <Button onClick={handleAdd} className="flex-1" disabled={!name.trim()}>Add to Pipeline</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface EnrichButtonProps {
  founders: Founder[];
  onEnrich: (enriched: Founder[]) => void;
}

export function EnrichButton({ founders, onEnrich }: EnrichButtonProps) {
  const [enriching, setEnriching] = useState(false);
  const unenriched = founders.filter(f => f.isManual && f.score === 0);

  if (unenriched.length === 0) return null;

  const handleEnrich = () => {
    setEnriching(true);
    // Simulate enrichment
    setTimeout(() => {
      const enriched = founders.map(f => {
        if (!f.isManual || f.score > 0) return f;
        const score = Math.floor(Math.random() * 40) + 45;
        const vcs = ["a16z", "Sequoia", "Greylock", "Accel", "Y Combinator"];
        const picked = vcs.sort(() => Math.random() - 0.5).slice(0, Math.floor(Math.random() * 3) + 1);
        const today = new Date().toISOString().split("T")[0];
        const vcConns = picked.map(vc => ({ vc, date: today }));
        return {
          ...f,
          score,
          activity: (score >= 80 ? "hot" : score >= 60 ? "warm" : "cold") as "hot" | "warm" | "cold",
          scoreExplanation: `Enrichment found ${picked.length} VC connections. Profile suggests ${f.sector} focus with ${f.title} background.`,
          scoreSummary: `${picked.length} VC connections found → ${f.sector} background`,
          vcConnections: vcConns,
          followedVCs: vcConns,
          signals: ["Enriched", `${picked.length} VC connections`],
          lastActivity: "Just enriched",
          history: [...f.history, { date: today, score, activity: (score >= 80 ? "hot" : score >= 60 ? "warm" : "cold") as "hot" | "warm" | "cold" }],
        };
      });
      onEnrich(enriched);
      setEnriching(false);
      toast.success(`Enriched ${unenriched.length} candidates`);
    }, 1500);
  };

  return (
    <Button variant="outline" size="sm" className="gap-1.5" onClick={handleEnrich} disabled={enriching}>
      <Sparkles className="h-3.5 w-3.5" />
      {enriching ? "Enriching..." : `Enrich ${unenriched.length} new`}
    </Button>
  );
}
