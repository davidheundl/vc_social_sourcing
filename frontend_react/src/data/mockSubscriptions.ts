export type SnapshotStatus = "up_to_date" | "stale" | "outdated";
export type SubscriptionSource = "algorithm" | "manual";
export type SubscriptionType = "vc" | "angel";

export interface SnapshotLogEntry {
  id: string;
  profileName: string;
  logo: string;
  type: SubscriptionType;
  timestamp: Date;
  connectionsFound: number;
  newConnections: number;
}

export interface Subscription {
  id: string;
  name: string;
  logo: string; // firm logo for VCs, profile pic for angels
  type: SubscriptionType;
  role: string;
  firm: string;
  sector: string;
  linkedinUrl: string;
  source: SubscriptionSource;
  isPaused: boolean;
  lastSnapshotAt: Date;
  nextSnapshotAt: Date;
  totalSnapshots: number;
  connectionCount: number;
  addedAt: Date;
}

export function getSnapshotStatus(sub: Subscription): SnapshotStatus {
  if (sub.isPaused) return "outdated";
  const now = new Date();
  const diffMs = now.getTime() - sub.lastSnapshotAt.getTime();
  const diffHrs = diffMs / (1000 * 60 * 60);
  if (diffHrs < 24) return "up_to_date";
  if (diffHrs < 48) return "stale";
  return "outdated";
}

export function timeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function timeUntil(date: Date): string {
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  if (diffMs <= 0) return "Now";
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `in ${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `in ${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `in ${days}d`;
}

const now = new Date();
const hoursAgo = (h: number) => new Date(now.getTime() - h * 60 * 60 * 1000);
const minsAgo = (m: number) => new Date(now.getTime() - m * 60 * 1000);
const hoursFromNow = (h: number) => new Date(now.getTime() + h * 60 * 60 * 1000);

export const mockSubscriptions: Subscription[] = [
  {
    id: "sub-1",
    name: "a16z",
    logo: "/logos/a16z.svg",
    type: "vc",
    role: "Venture Capital Firm",
    firm: "Andreessen Horowitz",
    sector: "Enterprise / AI",
    linkedinUrl: "https://linkedin.com",
    source: "algorithm",
    isPaused: false,
    lastSnapshotAt: minsAgo(12),
    nextSnapshotAt: hoursFromNow(11.8),
    totalSnapshots: 47,
    connectionCount: 4823,
    addedAt: hoursAgo(720),
  },
  {
    id: "sub-2",
    name: "Sequoia Capital",
    logo: "/logos/sequoia.svg",
    type: "vc",
    role: "Venture Capital Firm",
    firm: "Sequoia Capital",
    sector: "Fintech / Growth",
    linkedinUrl: "https://linkedin.com",
    source: "algorithm",
    isPaused: false,
    lastSnapshotAt: minsAgo(43),
    nextSnapshotAt: hoursFromNow(11.3),
    totalSnapshots: 52,
    connectionCount: 3912,
    addedAt: hoursAgo(840),
  },
  {
    id: "sub-3",
    name: "Founders Fund",
    logo: "/logos/founders-fund.svg",
    type: "vc",
    role: "Venture Capital Firm",
    firm: "Founders Fund",
    sector: "Deep Tech",
    linkedinUrl: "https://linkedin.com",
    source: "algorithm",
    isPaused: false,
    lastSnapshotAt: hoursAgo(2),
    nextSnapshotAt: hoursFromNow(10),
    totalSnapshots: 38,
    connectionCount: 2654,
    addedAt: hoursAgo(600),
  },
  {
    id: "sub-4",
    name: "Richard Chen",
    logo: "/avatars/vc-richard-chen.jpg",
    type: "angel",
    role: "Angel Investor",
    firm: "Independent",
    sector: "SaaS / B2B",
    linkedinUrl: "https://linkedin.com",
    source: "manual",
    isPaused: false,
    lastSnapshotAt: hoursAgo(6),
    nextSnapshotAt: hoursFromNow(6),
    totalSnapshots: 29,
    connectionCount: 1847,
    addedAt: hoursAgo(480),
  },
  {
    id: "sub-5",
    name: "Accel",
    logo: "/logos/accel.svg",
    type: "vc",
    role: "Venture Capital Firm",
    firm: "Accel Partners",
    sector: "Consumer / Marketplace",
    linkedinUrl: "https://linkedin.com",
    source: "algorithm",
    isPaused: false,
    lastSnapshotAt: hoursAgo(1),
    nextSnapshotAt: hoursFromNow(11),
    totalSnapshots: 44,
    connectionCount: 3201,
    addedAt: hoursAgo(680),
  },
  {
    id: "sub-6",
    name: "Index Ventures",
    logo: "/logos/index-ventures.svg",
    type: "vc",
    role: "Venture Capital Firm",
    firm: "Index Ventures",
    sector: "Enterprise",
    linkedinUrl: "https://linkedin.com",
    source: "algorithm",
    isPaused: false,
    lastSnapshotAt: hoursAgo(18),
    nextSnapshotAt: hoursFromNow(6),
    totalSnapshots: 31,
    connectionCount: 5102,
    addedAt: hoursAgo(500),
  },
  {
    id: "sub-7",
    name: "Sarah Liu",
    logo: "/avatars/vc-sarah-liu.jpg",
    type: "angel",
    role: "Angel Investor",
    firm: "Independent",
    sector: "Health Tech",
    linkedinUrl: "https://linkedin.com",
    source: "manual",
    isPaused: true,
    lastSnapshotAt: hoursAgo(72),
    nextSnapshotAt: hoursFromNow(0),
    totalSnapshots: 12,
    connectionCount: 982,
    addedAt: hoursAgo(360),
  },
  {
    id: "sub-8",
    name: "Lightspeed",
    logo: "/logos/lightspeed.svg",
    type: "vc",
    role: "Venture Capital Firm",
    firm: "Lightspeed Venture Partners",
    sector: "AI / ML",
    linkedinUrl: "https://linkedin.com",
    source: "algorithm",
    isPaused: false,
    lastSnapshotAt: hoursAgo(30),
    nextSnapshotAt: hoursFromNow(0),
    totalSnapshots: 35,
    connectionCount: 2890,
    addedAt: hoursAgo(550),
  },
];

export interface WeeklyDiscovery {
  subId: string;
  name: string;
  logo: string;
  type: SubscriptionType;
  newConnections: number;
}

export function getWeeklyProgress(subs: Subscription[]) {
  const active = subs.filter(s => !s.isPaused);
  const total = active.length;
  const weekMs = 7 * 24 * 60 * 60 * 1000;
  const now = Date.now();
  const scanned = active.filter(s => now - s.lastSnapshotAt.getTime() < weekMs).length;
  const scheduled = total - scanned;
  // Deterministic-ish discoveries derived from each sub's id length so it's stable across renders
  const newConnectionsThisWeek = active.reduce((acc, s) => acc + ((s.id.length * 7) % 9), 0);
  // Next sync window = soonest nextSnapshotAt among active
  const nextAt = active
    .map(s => s.nextSnapshotAt.getTime())
    .filter(t => t > now)
    .sort((a, b) => a - b)[0];
  const nextLabel = nextAt
    ? new Date(nextAt).toLocaleDateString(undefined, { weekday: "long" })
    : "Soon";
  return {
    total,
    scanned,
    scheduled,
    percent: total === 0 ? 0 : Math.round((scanned / total) * 100),
    newConnectionsThisWeek,
    nextLabel,
  };
}

export function getWeeklyDiscoveries(subs: Subscription[]): WeeklyDiscovery[] {
  return subs
    .filter(s => !s.isPaused)
    .map(s => ({
      subId: s.id,
      name: s.name,
      logo: s.logo,
      type: s.type,
      newConnections: ((s.id.length * 7) % 9),
    }))
    .filter(d => d.newConnections > 0)
    .sort((a, b) => b.newConnections - a.newConnections)
    .slice(0, 10);
}

export function generateInitialFeed(): SnapshotLogEntry[] {
  return mockSubscriptions
    .filter(s => !s.isPaused)
    .sort((a, b) => b.lastSnapshotAt.getTime() - a.lastSnapshotAt.getTime())
    .map((s, i) => ({
      id: `log-${i}`,
      profileName: s.name,
      logo: s.logo,
      type: s.type,
      timestamp: s.lastSnapshotAt,
      connectionsFound: s.connectionCount,
      newConnections: Math.floor(Math.random() * 8),
    }));
}
