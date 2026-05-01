export type FounderStatus = "new" | "contacted" | "in_progress" | "closed";

export interface VCConnection {
  vc: string;
  date: string; // ISO date string e.g. "2026-04-16"
}

export interface FounderSnapshot {
  date: string;
  score: number;
  activity: "hot" | "warm" | "cold";
}

export interface Founder {
  id: string;
  name: string;
  avatar: string;
  title: string;
  company: string;
  country: string;
  sector: string;
  score: number;
  scoreExplanation: string;
  scoreSummary: string;
  activity: "hot" | "warm" | "cold";
  status: FounderStatus;
  linkedinUrl: string;
  xUrl: string;
  vcConnections: VCConnection[];
  followedVCs: VCConnection[];
  lastActivity: string;
  signals: string[];
  addedAt: string;
  discoveredWeek: string; // e.g. "W16" — the ISO week the founder was first identified
  isManual?: boolean;
  history: FounderSnapshot[];
}

// Get ISO week number from a date string
export function getISOWeek(dateStr: string): number {
  const d = new Date(dateStr);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 3 - ((d.getDay() + 6) % 7));
  const week1 = new Date(d.getFullYear(), 0, 4);
  return 1 + Math.round(((d.getTime() - week1.getTime()) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7);
}

export function getDiscoveredWeekLabel(dateStr: string): string {
  return `W${getISOWeek(dateStr)}`;
}

// Time-decay: score decreases ~3 pts per week since discovery
export function applyTimeDecay(baseScore: number, addedAt: string, currentDate: string): number {
  const added = new Date(addedAt).getTime();
  const current = new Date(currentDate).getTime();
  const weeksSince = Math.max(0, (current - added) / (7 * 24 * 60 * 60 * 1000));
  const decay = Math.floor(weeksSince) * 3;
  return Math.max(20, baseScore - decay);
}

// Helper to get VC names from connections
export function getVCNames(connections: VCConnection[]): string[] {
  return connections.map(c => c.vc);
}

// Helper to get connections active by a certain date
export function getConnectionsByDate(connections: VCConnection[], date: string): VCConnection[] {
  return connections.filter(c => c.date <= date);
}

// Helper to get snapshot for a specific date (returns latest snapshot on or before date)
export function getSnapshotForDate(founder: Founder, date: string): FounderSnapshot | null {
  const valid = founder.history.filter(h => h.date <= date);
  if (valid.length === 0) return null;
  return valid[valid.length - 1]; // history is sorted chronologically
}

// Timeline range — spans multiple weeks for weekly snapshot cadence
export const TIMELINE_START = "2026-04-06";
export const TIMELINE_END = "2026-04-30";

export const mockFounders: Founder[] = [];

// Legacy mock data kept for reference only — not exported as active data
const _legacyMockData: Founder[] = [
  {
    id: "1",
    name: "Sarah Chen",
    avatar: "/avatars/sarah-chen.jpg",
    title: "Ex-Staff Engineer",
    company: "Stripe",
    country: "United States",
    sector: "Fintech",
    score: 94,
    scoreExplanation: "Followed 4 top VCs in 2 weeks. Updated LinkedIn to 'Exploring new opportunities'. Ex-Stripe with payments domain expertise.",
    scoreSummary: "4 VC follows in 2 weeks + title change → payments expert exploring",
    activity: "hot",
    status: "new",
    linkedinUrl: "https://linkedin.com",
    xUrl: "https://x.com",
    vcConnections: [
      { vc: "a16z", date: "2026-04-16" },
      { vc: "Sequoia", date: "2026-04-18" },
      { vc: "Founders Fund", date: "2026-04-22" },
      { vc: "Lightspeed", date: "2026-04-28" },
    ],
    followedVCs: [
      { vc: "a16z", date: "2026-04-16" },
      { vc: "Sequoia", date: "2026-04-18" },
      { vc: "Founders Fund", date: "2026-04-22" },
      { vc: "Lightspeed", date: "2026-04-28" },
    ],
    lastActivity: "2h ago",
    signals: ["Multi-VC follow", "Title change", "Domain expert"],
    addedAt: "2026-04-16",
    discoveredWeek: "W16",
    history: [
      { date: "2026-04-16", score: 58, activity: "warm" },
      { date: "2026-04-18", score: 68, activity: "warm" },
      { date: "2026-04-22", score: 82, activity: "hot" },
      { date: "2026-04-25", score: 88, activity: "hot" },
      { date: "2026-04-28", score: 94, activity: "hot" },
    ],
  },
  {
    id: "2",
    name: "Marcus Weber",
    avatar: "/avatars/marcus-weber.jpg",
    title: "VP of Engineering",
    company: "Deliveroo",
    country: "United Kingdom",
    sector: "Logistics",
    score: 88,
    scoreExplanation: "Began engaging with startup content. Connected with 3 VCs. Strong operational background in marketplace logistics.",
    scoreSummary: "3 VC connects + startup content engagement → logistics operator",
    activity: "hot",
    status: "new",
    linkedinUrl: "https://linkedin.com",
    xUrl: "https://x.com",
    vcConnections: [
      { vc: "Accel", date: "2026-04-17" },
      { vc: "Index Ventures", date: "2026-04-21" },
      { vc: "Balderton", date: "2026-04-26" },
    ],
    followedVCs: [
      { vc: "Accel", date: "2026-04-17" },
      { vc: "Index Ventures", date: "2026-04-21" },
      { vc: "Balderton", date: "2026-04-26" },
    ],
    lastActivity: "5h ago",
    signals: ["Multi-VC follow", "Content engagement", "Operator background"],
    addedAt: "2026-04-17",
    discoveredWeek: "W16",
    history: [
      { date: "2026-04-17", score: 55, activity: "warm" },
      { date: "2026-04-21", score: 72, activity: "warm" },
      { date: "2026-04-26", score: 85, activity: "hot" },
      { date: "2026-04-30", score: 88, activity: "hot" },
    ],
  },
  {
    id: "3",
    name: "Aisha Patel",
    avatar: "/avatars/aisha-patel.jpg",
    title: "Head of AI/ML",
    company: "DeepMind",
    country: "United Kingdom",
    sector: "AI / ML",
    score: 85,
    scoreExplanation: "Followed Sequoia and a16z within same week. Published research on applied AI for startups. PhD from Stanford.",
    scoreSummary: "2 top-tier VC follows + applied AI research → DeepMind PhD",
    activity: "warm",
    status: "contacted",
    linkedinUrl: "https://linkedin.com",
    xUrl: "https://x.com",
    vcConnections: [
      { vc: "Sequoia", date: "2026-04-19" },
      { vc: "a16z", date: "2026-04-23" },
    ],
    followedVCs: [
      { vc: "Sequoia", date: "2026-04-19" },
      { vc: "a16z", date: "2026-04-23" },
    ],
    lastActivity: "1d ago",
    signals: ["Multi-VC follow", "Thought leadership", "PhD researcher"],
    addedAt: "2026-04-19",
    discoveredWeek: "W16",
    history: [
      { date: "2026-04-19", score: 55, activity: "warm" },
      { date: "2026-04-23", score: 75, activity: "warm" },
      { date: "2026-04-28", score: 85, activity: "warm" },
    ],
  },
  {
    id: "4",
    name: "Jonas Lindberg",
    avatar: "/avatars/jonas-lindberg.jpg",
    title: "Co-founder & CTO",
    company: "Klarna (early)",
    country: "Sweden",
    sector: "Fintech",
    score: 82,
    scoreExplanation: "Serial entrepreneur signal. Left advisory role. Started following 2 US-based VCs suggesting cross-border ambitions.",
    scoreSummary: "Serial founder + US VC follows → cross-border fintech ambitions",
    activity: "warm",
    status: "new",
    linkedinUrl: "https://linkedin.com",
    xUrl: "https://x.com",
    vcConnections: [
      { vc: "Benchmark", date: "2026-04-20" },
      { vc: "Ribbit Capital", date: "2026-04-25" },
    ],
    followedVCs: [
      { vc: "Benchmark", date: "2026-04-20" },
      { vc: "Ribbit Capital", date: "2026-04-25" },
    ],
    lastActivity: "2d ago",
    signals: ["Serial founder", "Cross-border signal", "Fintech expert"],
    addedAt: "2026-04-20",
    discoveredWeek: "W17",
    history: [
      { date: "2026-04-20", score: 65, activity: "warm" },
      { date: "2026-04-25", score: 78, activity: "warm" },
      { date: "2026-04-27", score: 82, activity: "warm" },
    ],
  },
  {
    id: "5",
    name: "Mei Zhang",
    avatar: "/avatars/mei-zhang.jpg",
    title: "Principal PM",
    company: "ByteDance",
    country: "Singapore",
    sector: "Consumer",
    score: 79,
    scoreExplanation: "Followed 3 consumer-focused VCs. Attending startup conferences. Strong product sense from TikTok growth team.",
    scoreSummary: "3 consumer VC follows + conference attendance → TikTok growth PM",
    activity: "warm",
    status: "in_progress",
    linkedinUrl: "https://linkedin.com",
    xUrl: "https://x.com",
    vcConnections: [
      { vc: "GGV Capital", date: "2026-04-18" },
      { vc: "DST Global", date: "2026-04-22" },
      { vc: "Tiger Global", date: "2026-04-27" },
    ],
    followedVCs: [
      { vc: "GGV Capital", date: "2026-04-18" },
      { vc: "DST Global", date: "2026-04-22" },
      { vc: "Tiger Global", date: "2026-04-27" },
    ],
    lastActivity: "3d ago",
    signals: ["Multi-VC follow", "Conference attendance", "Growth expertise"],
    addedAt: "2026-04-18",
    discoveredWeek: "W16",
    history: [
      { date: "2026-04-18", score: 48, activity: "cold" },
      { date: "2026-04-22", score: 62, activity: "warm" },
      { date: "2026-04-27", score: 75, activity: "warm" },
      { date: "2026-04-30", score: 79, activity: "warm" },
    ],
  },
  {
    id: "6",
    name: "David Okafor",
    avatar: "/avatars/david-okafor.jpg",
    title: "Engineering Manager",
    company: "Google",
    country: "United States",
    sector: "Developer Tools",
    score: 74,
    scoreExplanation: "Recently followed a16z and YC partners. Open source contributions increasing. Side project gaining traction on GitHub.",
    scoreSummary: "a16z + YC follows + growing OSS project → dev tools builder",
    activity: "warm",
    status: "new",
    linkedinUrl: "https://linkedin.com",
    xUrl: "https://x.com",
    vcConnections: [
      { vc: "a16z", date: "2026-04-24" },
      { vc: "Y Combinator", date: "2026-04-29" },
    ],
    followedVCs: [
      { vc: "a16z", date: "2026-04-24" },
      { vc: "Y Combinator", date: "2026-04-29" },
    ],
    lastActivity: "4d ago",
    signals: ["Multi-VC follow", "OSS contributor", "Side project"],
    addedAt: "2026-04-24",
    discoveredWeek: "W17",
    history: [
      { date: "2026-04-24", score: 52, activity: "warm" },
      { date: "2026-04-29", score: 74, activity: "warm" },
    ],
  },
  {
    id: "7",
    name: "Elena Rossi",
    avatar: "/avatars/elena-rossi.jpg",
    title: "Director of Product",
    company: "Spotify",
    country: "Germany",
    sector: "Consumer",
    score: 68,
    scoreExplanation: "Followed Northzone and EQT Ventures. LinkedIn shows 'Open to opportunities'. B2C product expertise from Spotify.",
    scoreSummary: "Open to work + 2 EU VC follows → B2C product leader",
    activity: "cold",
    status: "closed",
    linkedinUrl: "https://linkedin.com",
    xUrl: "https://x.com",
    vcConnections: [
      { vc: "Northzone", date: "2026-04-16" },
      { vc: "EQT Ventures", date: "2026-04-19" },
    ],
    followedVCs: [
      { vc: "Northzone", date: "2026-04-16" },
      { vc: "EQT Ventures", date: "2026-04-19" },
    ],
    lastActivity: "1w ago",
    signals: ["VC follow", "Open to work", "Product leader"],
    addedAt: "2026-04-16",
    discoveredWeek: "W16",
    history: [
      { date: "2026-04-16", score: 55, activity: "warm" },
      { date: "2026-04-19", score: 65, activity: "warm" },
      { date: "2026-04-23", score: 68, activity: "cold" },
    ],
  },
  {
    id: "8",
    name: "Raj Krishnamurthy",
    avatar: "/avatars/raj-krishnamurthy.jpg",
    title: "Staff SWE",
    company: "Meta",
    country: "United States",
    sector: "AI / ML",
    score: 63,
    scoreExplanation: "Followed Greylock. Posting about AI infrastructure challenges. 10+ years at Meta's infra team.",
    scoreSummary: "Greylock follow + AI infra content → 10yr Meta veteran",
    activity: "cold",
    status: "new",
    linkedinUrl: "https://linkedin.com",
    xUrl: "https://x.com",
    vcConnections: [
      { vc: "Greylock", date: "2026-04-20" },
    ],
    followedVCs: [
      { vc: "Greylock", date: "2026-04-20" },
    ],
    lastActivity: "2w ago",
    signals: ["VC follow", "Content creator", "Infra expert"],
    addedAt: "2026-04-20",
    discoveredWeek: "W17",
    history: [
      { date: "2026-04-20", score: 48, activity: "cold" },
      { date: "2026-04-25", score: 58, activity: "cold" },
      { date: "2026-04-30", score: 63, activity: "cold" },
    ],
  },
];

export interface VCNode {
  id: string;
  name: string;
  type: "vc";
  logo: string;
  employee: string;
  employeeRole: string;
  subscribedAt: string; // ISO date — when this VC was added as a subscription
}

export const vcNodes: VCNode[] = [
  { id: "vc-1", name: "a16z", type: "vc", logo: "/logos/a16z.svg", employee: "Marc Andreessen", employeeRole: "General Partner", subscribedAt: "2026-04-15" },
  { id: "vc-2", name: "Sequoia", type: "vc", logo: "/logos/sequoia.svg", employee: "Lisa Park", employeeRole: "Managing Director", subscribedAt: "2026-04-15" },
  { id: "vc-3", name: "Founders Fund", type: "vc", logo: "/logos/founders-fund.svg", employee: "Alex Kumar", employeeRole: "Partner", subscribedAt: "2026-04-15" },
  { id: "vc-4", name: "Lightspeed", type: "vc", logo: "/logos/lightspeed.svg", employee: "Vikram Shah", employeeRole: "Venture Partner", subscribedAt: "2026-04-15" },
  { id: "vc-5", name: "Accel", type: "vc", logo: "/logos/accel.svg", employee: "Nina Okonkwo", employeeRole: "Principal", subscribedAt: "2026-04-15" },
  { id: "vc-6", name: "Index Ventures", type: "vc", logo: "/logos/index-ventures.svg", employee: "Hans Mueller", employeeRole: "General Partner", subscribedAt: "2026-04-15" },
  { id: "vc-7", name: "Balderton", type: "vc", logo: "/logos/balderton.svg", employee: "James Crawford", employeeRole: "Partner", subscribedAt: "2026-04-15" },
  { id: "vc-8", name: "Benchmark", type: "vc", logo: "/logos/benchmark.svg", employee: "Peter Fenton", employeeRole: "General Partner", subscribedAt: "2026-04-15" },
  { id: "vc-9", name: "Ribbit Capital", type: "vc", logo: "/logos/ribbit.svg", employee: "Micky Malka", employeeRole: "Founding Partner", subscribedAt: "2026-04-15" },
  { id: "vc-10", name: "Y Combinator", type: "vc", logo: "/logos/yc.svg", employee: "Garry Tan", employeeRole: "President & CEO", subscribedAt: "2026-04-15" },
  { id: "vc-11", name: "Greylock", type: "vc", logo: "/logos/greylock.svg", employee: "Reid Hoffman", employeeRole: "Partner", subscribedAt: "2026-04-15" },
  { id: "vc-12", name: "Northzone", type: "vc", logo: "/logos/northzone.svg", employee: "Jeppe Zink", employeeRole: "General Partner", subscribedAt: "2026-04-15" },
  { id: "vc-13", name: "GGV Capital", type: "vc", logo: "/logos/ggv.svg", employee: "Jenny Lee", employeeRole: "Managing Partner", subscribedAt: "2026-04-15" },
  { id: "vc-14", name: "DST Global", type: "vc", logo: "/logos/dst.svg", employee: "Yuri Milner", employeeRole: "Founder", subscribedAt: "2026-04-15" },
  { id: "vc-15", name: "Tiger Global", type: "vc", logo: "/logos/tiger.svg", employee: "Scott Shleifer", employeeRole: "Partner", subscribedAt: "2026-04-22" },
  { id: "vc-16", name: "EQT Ventures", type: "vc", logo: "/logos/eqt.svg", employee: "Lars Jörnow", employeeRole: "Partner", subscribedAt: "2026-04-15" },
];
