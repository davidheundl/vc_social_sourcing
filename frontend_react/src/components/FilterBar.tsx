import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Search, Download } from "lucide-react";
import { Button } from "@/components/ui/button";

interface FilterBarProps {
  search: string;
  onSearchChange: (v: string) => void;
  country: string;
  onCountryChange: (v: string) => void;
  sector: string;
  onSectorChange: (v: string) => void;
  scoreRange: string;
  onScoreRangeChange: (v: string) => void;
  activity: string;
  onActivityChange: (v: string) => void;
  onExport: () => void;
}

export function FilterBar({
  search, onSearchChange,
  country, onCountryChange,
  sector, onSectorChange,
  scoreRange, onScoreRangeChange,
  activity, onActivityChange,
  onExport,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search founders..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9 bg-secondary border-border"
        />
      </div>

      <Select value={country} onValueChange={onCountryChange}>
        <SelectTrigger className="w-[160px] bg-secondary border-border">
          <SelectValue placeholder="Country" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Countries</SelectItem>
          <SelectItem value="United States">United States</SelectItem>
          <SelectItem value="United Kingdom">United Kingdom</SelectItem>
          <SelectItem value="Germany">Germany</SelectItem>
          <SelectItem value="Sweden">Sweden</SelectItem>
          <SelectItem value="Singapore">Singapore</SelectItem>
        </SelectContent>
      </Select>

      <Select value={sector} onValueChange={onSectorChange}>
        <SelectTrigger className="w-[160px] bg-secondary border-border">
          <SelectValue placeholder="Sector" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Sectors</SelectItem>
          <SelectItem value="Fintech">Fintech</SelectItem>
          <SelectItem value="AI / ML">AI / ML</SelectItem>
          <SelectItem value="Consumer">Consumer</SelectItem>
          <SelectItem value="Logistics">Logistics</SelectItem>
          <SelectItem value="Developer Tools">Dev Tools</SelectItem>
        </SelectContent>
      </Select>

      <Select value={scoreRange} onValueChange={onScoreRangeChange}>
        <SelectTrigger className="w-[140px] bg-secondary border-border">
          <SelectValue placeholder="Score" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Scores</SelectItem>
          <SelectItem value="80+">80+</SelectItem>
          <SelectItem value="60-79">60–79</SelectItem>
          <SelectItem value="<60">&lt; 60</SelectItem>
        </SelectContent>
      </Select>

      <Select value={activity} onValueChange={onActivityChange}>
        <SelectTrigger className="w-[130px] bg-secondary border-border">
          <SelectValue placeholder="Activity" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Activity</SelectItem>
          <SelectItem value="hot">Hot</SelectItem>
          <SelectItem value="warm">Warm</SelectItem>
          <SelectItem value="cold">Cold</SelectItem>
        </SelectContent>
      </Select>

      <Button variant="outline" onClick={onExport} className="gap-2 border-border">
        <Download className="h-4 w-4" />
        Export CSV
      </Button>
    </div>
  );
}
