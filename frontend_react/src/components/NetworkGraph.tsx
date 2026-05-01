import { useEffect, useRef, useState, useCallback } from "react";
import { vcNodes, Founder, FounderStatus, VCNode } from "@/data/mockFounders";
import { motion, AnimatePresence } from "framer-motion";
import { Linkedin, Twitter, X, Zap, Building2, Users } from "lucide-react";
import { ScoreBadge } from "./ScoreBadge";
import { ActivityBadge } from "./ActivityBadge";
import { StatusBadge } from "./StatusBadge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const SECTOR_COLORS: Record<string, string> = {
  "Fintech": "#2dd4a8",
  "AI / ML": "#a78bfa",
  "Consumer": "#f59e0b",
  "Logistics": "#38bdf8",
  "Developer Tools": "#f472b6",
};

const VC_COLOR = "#6366f1";

interface GNode {
  id: string;
  name: string;
  type: "founder" | "vc";
  x: number; y: number;
  vx: number; vy: number;
  score?: number;
  sector?: string;
  activity?: "hot" | "warm" | "cold";
  founder?: Founder;
  vcData?: VCNode;
  visible: boolean;
  targetVisible: boolean;
  appearTime: number;
  scale: number;
}

interface GEdge {
  source: string; target: string;
  vc: string;
  type: "follow" | "engagement" | "shared";
  strength: number;
  progress: number;
  targetProgress: number;
  appearTime: number;
}

interface NetworkGraphProps {
  founders: Founder[];
  allFounders: Founder[];
  onStatusChange?: (id: string, status: FounderStatus) => void;
  currentDate?: string;
  vcNodesOverride?: VCNode[];
}

export function NetworkGraph({ founders, allFounders, onStatusChange, currentDate, vcNodesOverride }: NetworkGraphProps) {
  const activeVCNodes = vcNodesOverride ?? vcNodes;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedFounder, setSelectedFounder] = useState<Founder | null>(null);
  const [selectedVC, setSelectedVC] = useState<VCNode | null>(null);
  const [introPhase, setIntroPhase] = useState(0);
  const [introComplete, setIntroComplete] = useState(false);
  const [signalsCount, setSignalsCount] = useState(0);
  const nodesRef = useRef<GNode[]>([]);
  const edgesRef = useRef<GEdge[]>([]);
  const animRef = useRef<number>(0);
  const hoveredRef = useRef<GNode | null>(null);
  const dimRef = useRef({ w: 0, h: 0 });
  const startTimeRef = useRef(0);
  const zoomRef = useRef({ scale: 1, tx: 0, ty: 0, targetScale: 1, targetTx: 0, targetTy: 0 });
  const pulseTimeRef = useRef(0);
  const initializedRef = useRef(false);
  const panRef = useRef({ isPanning: false, startX: 0, startY: 0, startTx: 0, startTy: 0, didDrag: false });
  const avatarImagesRef = useRef<Map<string, HTMLImageElement>>(new Map());
  const vcLogoImagesRef = useRef<Map<string, HTMLImageElement>>(new Map());

  // Preload avatar images
  useEffect(() => {
    const toLoad = allFounders.filter(f => f.avatar && f.avatar.startsWith("/") && !avatarImagesRef.current.has(f.id));
    toLoad.forEach(f => {
      const img = new Image();
      img.src = f.avatar;
      avatarImagesRef.current.set(f.id, img);
    });
  }, [allFounders]);

  // Preload VC logo images
  useEffect(() => {
    activeVCNodes.forEach(vc => {
      if (!vcLogoImagesRef.current.has(vc.id)) {
        const img = new Image();
        img.src = vc.logo;
        vcLogoImagesRef.current.set(vc.id, img);
      }
    });
  }, []);

  // Build the graph layout (called once, when container has real size)
  const buildLayout = useCallback(() => {
    if (initializedRef.current) return;
    const container = containerRef.current;
    if (!container || allFounders.length === 0) return;

    const rect = container.getBoundingClientRect();
    if (rect.width < 50 || rect.height < 50) return;
    initializedRef.current = true;

    const cx = rect.width / 2;
    const cy = rect.height / 2;

    const usedVcIds = new Set<string>();
    allFounders.forEach((f) => {
      f.followedVCs.forEach((conn) => {
        const vc = activeVCNodes.find((v) => v.name === conn.vc);
        if (vc) usedVcIds.add(vc.id);
      });
    });

    const vcList = activeVCNodes.filter((v) => usedVcIds.has(v.id));

    const vcNodesList: GNode[] = vcList.map((v, i) => ({
      id: v.id, name: v.name, type: "vc" as const,
      x: cx + Math.cos((i / vcList.length) * Math.PI * 2) * Math.min(cx, cy) * 0.55,
      y: cy + Math.sin((i / vcList.length) * Math.PI * 2) * Math.min(cx, cy) * 0.55,
      vx: 0, vy: 0,
      vcData: v,
      visible: false,
      targetVisible: false,
      appearTime: 600 + i * 100,
      scale: 0,
    }));

    const vcPositionMap = new Map<string, { x: number; y: number }>();
    vcNodesList.forEach(v => vcPositionMap.set(v.name, { x: v.x, y: v.y }));

    const sortedFounders = [...allFounders].sort((a, b) => {
      const aFirst = a.followedVCs[0]?.date || a.addedAt;
      const bFirst = b.followedVCs[0]?.date || b.addedAt;
      return aFirst.localeCompare(bFirst);
    });

    const founderNodesList: GNode[] = sortedFounders.map((f, i) => {
      const firstVC = f.followedVCs[0];
      const originPos = firstVC ? vcPositionMap.get(firstVC.vc) : null;
      const startX = originPos
        ? originPos.x + (Math.random() - 0.5) * 8
        : cx + (Math.random() - 0.5) * cx * 1.4;
      const startY = originPos
        ? originPos.y + (Math.random() - 0.5) * 8
        : cy + (Math.random() - 0.5) * cy * 1.4;

      return {
        id: f.id, name: f.name, type: "founder" as const,
        x: startX, y: startY,
        vx: 0, vy: 0,
        score: f.score, sector: f.sector, activity: f.activity, founder: f,
        visible: false,
        targetVisible: false,
        appearTime: 2200 + i * 200,
        scale: 0,
      };
    });

    nodesRef.current = [...founderNodesList, ...vcNodesList];

    const edges: GEdge[] = [];
    sortedFounders.forEach((f, fi) => {
      f.followedVCs.forEach((conn, i) => {
        const vc = activeVCNodes.find((v) => v.name === conn.vc);
        if (vc) {
          const types: Array<"follow" | "engagement" | "shared"> = ["follow", "engagement", "shared"];
          edges.push({
            source: f.id, target: vc.id,
            vc: conn.vc,
            type: types[i % 3],
            strength: f.score >= 80 ? 3 : f.score >= 60 ? 2 : 1,
            progress: 0,
            targetProgress: 0,
            appearTime: 2200 + fi * 200 + i * 60,
          });
        }
      });
    });
    edgesRef.current = edges;
    startTimeRef.current = performance.now();
  }, [allFounders]);

  useEffect(() => { buildLayout(); }, [buildLayout]);

  // DATE-DRIVEN: Update visibility — VCs appear first, founders emerge from them
  useEffect(() => {
    if (!initializedRef.current) return;

    // Build a map of which VCs are subscribed by the current date
    const vcSubscribedMap = new Map<string, boolean>();
    activeVCNodes.forEach(vc => {
      vcSubscribedMap.set(vc.name, vc.subscribedAt <= (currentDate || "9999-12-31"));
    });

    // VCs are visible based on their own subscribedAt date — independent of founders
    nodesRef.current.forEach(n => {
      if (n.type === "vc") {
        const shouldBeVisible = vcSubscribedMap.get(n.name) || false;
        n.targetVisible = shouldBeVisible;
        if (shouldBeVisible && !n.visible) { n.visible = true; n.scale = 0; }
      }
    });

    // Founders are visible when currentDate >= addedAt (discovery date from VC snapshot)
    const visibleFounderIds = new Set(founders.map(f => f.id));
    const founderMap = new Map(founders.map(f => [f.id, f]));

    nodesRef.current.forEach(n => {
      if (n.type === "founder") {
        const shouldBeVisible = visibleFounderIds.has(n.id);
        n.targetVisible = shouldBeVisible;
        if (shouldBeVisible) {
          const f = founderMap.get(n.id)!;
          n.score = f.score;
          n.activity = f.activity;
          n.sector = f.sector;
          n.founder = f;
          if (!n.visible) { n.visible = true; n.scale = 0; }
        }
      }
    });

    // Edges: visible when both endpoints are visible and connection date is reached
    const activeConnections = new Map<string, Set<string>>();
    founders.forEach(f => {
      activeConnections.set(f.id, new Set(f.followedVCs.map(c => c.vc)));
    });

    edgesRef.current.forEach(e => {
      const founderVcs = activeConnections.get(e.source);
      const vcSubscribed = vcSubscribedMap.get(e.vc);
      if (founderVcs && founderVcs.has(e.vc) && vcSubscribed) {
        e.targetProgress = 1;
        const f = founderMap.get(e.source);
        if (f) e.strength = f.score >= 80 ? 3 : f.score >= 60 ? 2 : 1;
      } else {
        e.targetProgress = 0;
      }
    });
  }, [founders, currentDate]);

  // Intro phases
  useEffect(() => {
    if (introComplete) return;
    const timers = [
      setTimeout(() => setIntroPhase(1), 200),
      setTimeout(() => setIntroPhase(2), 1000),
      setTimeout(() => setIntroPhase(3), 2500),
      setTimeout(() => {
        setIntroPhase(4);
        setSignalsCount(founders.filter(f => f.activity === "hot").length);
      }, 4000),
      setTimeout(() => setIntroComplete(true), 5500),
    ];
    return () => timers.forEach(clearTimeout);
  }, [founders, introComplete]);

  const skipIntro = useCallback(() => {
    setIntroPhase(4);
    setIntroComplete(true);
    setSignalsCount(founders.filter(f => f.activity === "hot").length);
    const now = performance.now();
    nodesRef.current.forEach(n => { n.visible = true; n.scale = 1; n.appearTime = 0; });
    edgesRef.current.forEach(e => { e.progress = e.targetProgress; e.appearTime = 0; });
    startTimeRef.current = now - 6000;
  }, [founders]);

  // Get connected founders for a VC
  const getConnectedFounders = useCallback((vcName: string) => {
    return founders.filter(f => f.followedVCs.some(c => c.vc === vcName));
  }, [founders]);

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const dpr = window.devicePixelRatio || 2;
    const ctx = canvas.getContext("2d")!;

    const resizeCanvas = () => {
      const rect = container.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const prev = dimRef.current;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = rect.width + "px";
      canvas.style.height = rect.height + "px";
      dimRef.current = { w: rect.width, h: rect.height };
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);

      // Reposition nodes proportionally when container resizes
      if (prev.w > 0 && prev.h > 0 && (prev.w !== rect.width || prev.h !== rect.height)) {
        const sx = rect.width / prev.w;
        const sy = rect.height / prev.h;
        nodesRef.current.forEach(n => {
          n.x *= sx;
          n.y *= sy;
        });
      }

      // If layout wasn't built yet (container started at 0 size), build it now
      if (!initializedRef.current) buildLayout();
    };
    resizeCanvas();

    const resizeObserver = new ResizeObserver(resizeCanvas);
    resizeObserver.observe(container);

    function simulate() {
      const nodes = nodesRef.current.filter(n => n.visible && n.scale > 0.1);
      const repulsion = 4000;
      const damping = 0.6;   // high damping = settles quickly, no jitter
      const edgeLength = 180;
      const k = 0.012;

      // Check if already settled — skip physics if max velocity is tiny
      const maxV = nodes.reduce((m, n) => Math.max(m, Math.abs(n.vx), Math.abs(n.vy)), 0);
      if (maxV < 0.05) {
        nodes.forEach(n => { n.vx = 0; n.vy = 0; });
        return;
      }

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = repulsion / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          nodes[i].vx += fx; nodes[i].vy += fy;
          nodes[j].vx -= fx; nodes[j].vy -= fy;
        }
      }

      edgesRef.current.forEach((e) => {
        if (e.progress < 0.1) return;
        const s = nodesRef.current.find((n) => n.id === e.source);
        const t = nodesRef.current.find((n) => n.id === e.target);
        if (!s || !t || !s.visible || !t.visible) return;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = (dist - edgeLength) * k;
        // VC nodes are anchored — only move founder nodes
        if (s.type === "founder") { s.vx += (dx / dist) * force; s.vy += (dy / dist) * force; }
        if (t.type === "founder") { t.vx -= (dx / dist) * force; t.vy -= (dy / dist) * force; }
      });

      nodes.forEach((n) => {
        // VC nodes stay fixed in their ring positions
        if (n.type === "vc") { n.vx = 0; n.vy = 0; return; }
        n.vx += (dimRef.current.w / 2 - n.x) * 0.001;
        n.vy += (dimRef.current.h / 2 - n.y) * 0.001;
        n.vx *= damping; n.vy *= damping;
        n.x += n.vx; n.y += n.vy;
        n.x = Math.max(30, Math.min(dimRef.current.w - 30, n.x));
        n.y = Math.max(30, Math.min(dimRef.current.h - 30, n.y));
      });
    }

    function drawRoundedRect(x: number, y: number, w: number, h: number, r: number) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r);
      ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
    }

    function draw() {
      const w = dimRef.current.w;
      const h = dimRef.current.h;
      const elapsed = performance.now() - startTimeRef.current;
      pulseTimeRef.current = performance.now();

      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "hsl(220, 20%, 96%)";
      ctx.fillRect(0, 0, w, h);

      const dotAlpha = Math.min(1, elapsed / 1500) * 0.18;
      ctx.fillStyle = `rgba(160, 170, 190, ${dotAlpha})`;
      const spacing = 24;
      for (let x = spacing; x < w; x += spacing) {
        for (let y = spacing; y < h; y += spacing) {
          ctx.beginPath();
          ctx.arc(x, y, 0.8, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Animate node scale
      nodesRef.current.forEach(n => {
        if (elapsed < 6000 && !n.visible && elapsed >= n.appearTime) {
          n.visible = true;
          n.scale = 0;
        }
        if (n.targetVisible && n.visible) {
          if (n.scale < 1) n.scale = Math.min(1, n.scale + 0.06);
        } else if (!n.targetVisible && n.visible) {
          n.scale = Math.max(0, n.scale - 0.06);
          if (n.scale <= 0) n.visible = false;
        }
      });

      // Animate edge progress
      edgesRef.current.forEach(e => {
        if (elapsed < 6000 && elapsed >= e.appearTime && e.targetProgress > 0 && e.progress < e.targetProgress) {
          e.progress = Math.min(e.targetProgress, e.progress + 0.025);
        } else {
          const diff = e.targetProgress - e.progress;
          if (Math.abs(diff) > 0.01) e.progress += diff * 0.12;
          else e.progress = e.targetProgress;
        }
      });

      // Zoom
      const z = zoomRef.current;
      z.scale += (z.targetScale - z.scale) * 0.06;
      z.tx += (z.targetTx - z.tx) * 0.06;
      z.ty += (z.targetTy - z.ty) * 0.06;

      ctx.save();
      ctx.translate(z.tx, z.ty);
      ctx.scale(z.scale, z.scale);

      const nodes = nodesRef.current;
      const hovered = hoveredRef.current;
      const selected = selectedFounder;
      const selVC = selectedVC;
      const focusId = selected?.id || selVC?.id || hovered?.id;
      const focusEdges = focusId
        ? new Set(edgesRef.current.filter(e => (e.source === focusId || e.target === focusId) && e.progress > 0.1).flatMap(e => [e.source, e.target]))
        : null;

      // Draw edges
      edgesRef.current.forEach((e) => {
        if (e.progress <= 0.01) return;
        const s = nodes.find((n) => n.id === e.source);
        const t = nodes.find((n) => n.id === e.target);
        if (!s || !t || !s.visible || !t.visible || s.scale < 0.1 || t.scale < 0.1) return;

        const isFocused = focusEdges && (e.source === focusId || e.target === focusId);
        const dimmed = focusEdges && !isFocused;

        const ex = s.x + (t.x - s.x) * e.progress;
        const ey = s.y + (t.y - s.y) * e.progress;

        if (isFocused) {
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          ctx.lineTo(ex, ey);
          ctx.strokeStyle = `rgba(99, 102, 241, 0.12)`;
          ctx.lineWidth = e.strength * 4 + 4;
          ctx.stroke();
        }

        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(ex, ey);

        if (e.type === "engagement") ctx.setLineDash([5, 5]);
        else if (e.type === "shared") ctx.setLineDash([2, 4]);
        else ctx.setLineDash([]);

        const alpha = dimmed ? 0.04 : isFocused ? 0.45 : 0.12;
        ctx.strokeStyle = `rgba(99, 102, 241, ${alpha * e.progress})`;
        ctx.lineWidth = e.strength * (isFocused ? 2 : 1);
        ctx.stroke();
        ctx.setLineDash([]);
      });

      // Draw nodes
      const pulseT = (performance.now() % 2000) / 2000;

      nodes.forEach((n) => {
        if (!n.visible || n.scale < 0.01) return;

        const isHovered = hovered?.id === n.id;
        const isSelected = selected?.id === n.id || selVC?.id === n.id;
        const isConnected = focusEdges?.has(n.id);
        const dimmed = focusEdges && !isHovered && !isSelected && !isConnected;

        const s = n.scale;

        if (n.type === "vc") {
          // VC nodes: rounded squares with logo — large and visible
          const size = (isHovered || isSelected ? 40 : 34) * s;
          const halfSize = size / 2;
          const cornerR = 7 * s;

          // White background
          ctx.save();
          ctx.globalAlpha = dimmed ? 0.3 : s;
          drawRoundedRect(n.x - halfSize, n.y - halfSize, size, size, cornerR);
          ctx.fillStyle = "#ffffff";
          ctx.fill();
          ctx.strokeStyle = dimmed ? "rgba(99, 102, 241, 0.2)" : VC_COLOR;
          ctx.lineWidth = isSelected || isHovered ? 2.5 : 1.5;
          ctx.stroke();

          // Draw logo inside — no padding, fill the whole square
          const logoImg = vcLogoImagesRef.current.get(n.id);
          if (logoImg && logoImg.complete && logoImg.naturalWidth > 0) {
            ctx.save();
            drawRoundedRect(n.x - halfSize + 1, n.y - halfSize + 1, size - 2, size - 2, cornerR - 1);
            ctx.clip();
            ctx.drawImage(logoImg, n.x - halfSize + 1, n.y - halfSize + 1, size - 2, size - 2);
            ctx.restore();
          }

          ctx.restore();

          // Label: show employee name, not just firm
          if (!dimmed && s > 0.5) {
            const vcData = n.vcData;
            const label = vcData ? vcData.employee : n.name;
            const sublabel = vcData ? n.name : "";
            
            ctx.font = `600 ${9 * s}px 'Plus Jakarta Sans', sans-serif`;
            ctx.textAlign = "center";
            // Text shadow
            ctx.fillStyle = `rgba(255, 255, 255, ${0.8 * s})`;
            ctx.fillText(label, n.x + 0.5, n.y + halfSize + 11 * s + 0.5);
            ctx.fillText(label, n.x - 0.5, n.y + halfSize + 11 * s - 0.5);
            ctx.fillStyle = `rgba(30, 30, 60, ${0.65 * s})`;
            ctx.fillText(label, n.x, n.y + halfSize + 11 * s);
            
            if (sublabel) {
              ctx.font = `500 ${7.5 * s}px 'Plus Jakarta Sans', sans-serif`;
              ctx.fillStyle = `rgba(99, 102, 241, ${0.5 * s})`;
              ctx.fillText(sublabel, n.x, n.y + halfSize + 21 * s);
            }
          }

          // Selection ring
          if (isSelected || isHovered) {
            drawRoundedRect(n.x - halfSize - 3, n.y - halfSize - 3, size + 6, size + 6, cornerR + 2);
            ctx.strokeStyle = VC_COLOR + "40";
            ctx.lineWidth = 2;
            ctx.stroke();
          }
        } else {
          // Founder nodes: circles with avatars (unchanged)
          const baseRadius = n.score ? Math.max(5, (n.score / 100) * 16) : 6;
          const radius = (isHovered || isSelected ? baseRadius + 4 : baseRadius) * s;
          const color = SECTOR_COLORS[n.sector || ""] || "#6366f1";

          if (n.activity === "hot" && !dimmed && s > 0.8) {
            const ringAlpha = (1 - pulseT) * 0.35 * s;
            const ringRadius = radius + 4 + pulseT * 18;
            ctx.beginPath();
            ctx.arc(n.x, n.y, ringRadius, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(0, 200, 220, ${ringAlpha})`;
            ctx.lineWidth = 2;
            ctx.stroke();

            const pulseT2 = ((performance.now() + 1000) % 2000) / 2000;
            const ringAlpha2 = (1 - pulseT2) * 0.2 * s;
            const ringRadius2 = radius + 4 + pulseT2 * 18;
            ctx.beginPath();
            ctx.arc(n.x, n.y, ringRadius2, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(0, 200, 220, ${ringAlpha2})`;
            ctx.lineWidth = 1.5;
            ctx.stroke();
          }

          if (n.activity === "warm" && !dimmed && s > 0.8) {
            const warmT = ((performance.now()) % 3000) / 3000;
            const warmAlpha = (1 - warmT) * 0.15 * s;
            const warmRadius = radius + 3 + warmT * 10;
            ctx.beginPath();
            ctx.arc(n.x, n.y, warmRadius, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(245, 158, 11, ${warmAlpha})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }

          if (n.score && n.score >= 80 && !dimmed) {
            const glow = ctx.createRadialGradient(n.x, n.y, radius, n.x, n.y, radius + 8);
            glow.addColorStop(0, color + "25");
            glow.addColorStop(1, "transparent");
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius + 8, 0, Math.PI * 2);
            ctx.fillStyle = glow;
            ctx.fill();
          }

          const avatarImg = avatarImagesRef.current.get(n.id);
          if (avatarImg && avatarImg.complete && avatarImg.naturalWidth > 0) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
            ctx.clip();
            ctx.globalAlpha = dimmed ? 0.3 : s;
            ctx.drawImage(avatarImg, n.x - radius, n.y - radius, radius * 2, radius * 2);
            ctx.restore();
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
            ctx.strokeStyle = dimmed ? color + "30" : color;
            ctx.lineWidth = 2;
            ctx.globalAlpha = dimmed ? 0.4 : s;
            ctx.stroke();
            ctx.globalAlpha = 1;
          } else {
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = dimmed ? color + "20" : color;
            ctx.globalAlpha = dimmed ? 0.5 : s;
            ctx.fill();
            ctx.globalAlpha = 1;
          }

          if (isSelected || isHovered) {
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius + 2, 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(255, 255, 255, 0.9)";
            ctx.lineWidth = 2.5;
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius + 2, 0, Math.PI * 2);
            ctx.strokeStyle = color + "60";
            ctx.lineWidth = 1;
            ctx.stroke();
          }

          if ((n.score && n.score >= 75 && !dimmed) || isHovered || isSelected) {
            ctx.font = `${isHovered || isSelected ? "700" : "600"} ${(isHovered || isSelected ? 11 : 10) * Math.min(s, 1)}px 'Plus Jakarta Sans', sans-serif`;
            ctx.textAlign = "center";
            ctx.fillStyle = `rgba(255, 255, 255, ${0.8 * s})`;
            ctx.fillText(n.name, n.x + 0.5, n.y - radius - 6 + 0.5);
            ctx.fillText(n.name, n.x - 0.5, n.y - radius - 6 - 0.5);
            ctx.fillStyle = isHovered || isSelected ? `rgba(20, 20, 40, ${s})` : `rgba(30, 30, 60, ${0.7 * s})`;
            ctx.fillText(n.name, n.x, n.y - radius - 6);
          }
        }
      });

      ctx.restore();

      // Hover tooltip
      if (hovered && !selected && !selVC) {
        const screenX = hovered.x * z.scale + z.tx;
        const screenY = hovered.y * z.scale + z.ty;
        const tx = Math.min(screenX + 18, w - 200);
        const ty = Math.max(screenY - 50, 10);

        if (hovered.type === "founder" && hovered.founder) {
          const f = hovered.founder;
          ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
          ctx.strokeStyle = "rgba(200, 205, 220, 0.6)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.roundRect(tx, ty, 185, 62, 10);
          ctx.fill();
          ctx.stroke();

          ctx.shadowColor = "rgba(0,0,0,0.08)";
          ctx.shadowBlur = 12;
          ctx.shadowOffsetY = 4;
          ctx.beginPath();
          ctx.roundRect(tx, ty, 185, 62, 10);
          ctx.fill();
          ctx.shadowColor = "transparent";

          ctx.font = "700 11px 'Plus Jakarta Sans', sans-serif";
          ctx.fillStyle = "hsl(222, 20%, 12%)";
          ctx.textAlign = "left";
          ctx.fillText(f.name, tx + 10, ty + 18);

          ctx.font = "500 10px 'Plus Jakarta Sans', sans-serif";
          ctx.fillStyle = "rgba(30, 30, 60, 0.5)";
          ctx.fillText(`${f.title} · ${f.company}`, tx + 10, ty + 32);

          ctx.font = "600 10px 'JetBrains Mono', monospace";
          const scoreColor = f.score >= 80 ? "#2dd4a8" : f.score >= 60 ? "#f59e0b" : "#ef4444";
          ctx.fillStyle = scoreColor;
          ctx.fillText(`Score ${f.score}`, tx + 10, ty + 48);

          ctx.font = "500 9px 'Plus Jakarta Sans', sans-serif";
          ctx.fillStyle = "rgba(30, 30, 60, 0.4)";
          ctx.fillText(f.activity.toUpperCase() + " · " + (f.signals[0] || ""), tx + 75, ty + 48);
        } else if (hovered.type === "vc" && hovered.vcData) {
          const vc = hovered.vcData;
          ctx.fillStyle = "rgba(255, 255, 255, 0.92)";
          ctx.strokeStyle = "rgba(99, 102, 241, 0.3)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.roundRect(tx, ty, 185, 52, 10);
          ctx.fill();
          ctx.stroke();

          ctx.shadowColor = "rgba(0,0,0,0.08)";
          ctx.shadowBlur = 12;
          ctx.shadowOffsetY = 4;
          ctx.beginPath();
          ctx.roundRect(tx, ty, 185, 52, 10);
          ctx.fill();
          ctx.shadowColor = "transparent";

          ctx.font = "700 11px 'Plus Jakarta Sans', sans-serif";
          ctx.fillStyle = VC_COLOR;
          ctx.textAlign = "left";
          ctx.fillText(vc.employee, tx + 10, ty + 18);

          ctx.font = "500 10px 'Plus Jakarta Sans', sans-serif";
          ctx.fillStyle = "rgba(30, 30, 60, 0.5)";
          ctx.fillText(`${vc.employeeRole} · ${vc.name}`, tx + 10, ty + 34);
        }
      }

      simulate();
      animRef.current = requestAnimationFrame(draw);
    }

    draw();

    const handleMouseMove = (e: MouseEvent) => {
      // Handle panning
      if (panRef.current.isPanning) {
        const dx = e.clientX - panRef.current.startX;
        const dy = e.clientY - panRef.current.startY;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) panRef.current.didDrag = true;
        zoomRef.current.targetTx = panRef.current.startTx + dx;
        zoomRef.current.targetTy = panRef.current.startTy + dy;
        canvas.style.cursor = "grabbing";
        return;
      }

      const r = canvas.getBoundingClientRect();
      const z = zoomRef.current;
      const mx = (e.clientX - r.left - z.tx) / z.scale;
      const my = (e.clientY - r.top - z.ty) / z.scale;
      let found: GNode | null = null;
      nodesRef.current.forEach((n) => {
        if (!n.visible || n.scale < 0.3) return;
        const hitRadius = n.type === "vc" ? 24 : Math.max(10, (n.score || 50) / 100 * 18);
        if (Math.sqrt((n.x - mx) ** 2 + (n.y - my) ** 2) < hitRadius) found = n;
      });
      hoveredRef.current = found;
      canvas.style.cursor = found ? "pointer" : "grab";
    };

    const handleMouseDown = (e: MouseEvent) => {
      if (e.button !== 0) return;
      panRef.current = {
        isPanning: true,
        startX: e.clientX,
        startY: e.clientY,
        startTx: zoomRef.current.targetTx,
        startTy: zoomRef.current.targetTy,
        didDrag: false,
      };
      canvas.style.cursor = "grabbing";
    };

    const handleMouseUp = () => {
      panRef.current.isPanning = false;
    };

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = canvas.getBoundingClientRect();
      const z = zoomRef.current;
      const mouseX = e.clientX - r.left;
      const mouseY = e.clientY - r.top;

      const zoomFactor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      const newScale = Math.min(4, Math.max(0.3, z.targetScale * zoomFactor));
      const scaleRatio = newScale / z.targetScale;

      // Zoom toward cursor
      zoomRef.current.targetTx = mouseX - (mouseX - z.targetTx) * scaleRatio;
      zoomRef.current.targetTy = mouseY - (mouseY - z.targetTy) * scaleRatio;
      zoomRef.current.targetScale = newScale;
    };

    const handleClick = (e: MouseEvent) => {
      if (panRef.current.didDrag) {
        panRef.current.didDrag = false;
        return;
      }
      const r = canvas.getBoundingClientRect();
      const z = zoomRef.current;
      const mx = (e.clientX - r.left - z.tx) / z.scale;
      const my = (e.clientY - r.top - z.ty) / z.scale;
      let found: GNode | null = null;
      nodesRef.current.forEach((n) => {
        if (!n.visible || n.scale < 0.3) return;
        const hitRadius = n.type === "vc" ? 24 : Math.max(10, (n.score || 50) / 100 * 18);
        if (Math.sqrt((n.x - mx) ** 2 + (n.y - my) ** 2) < hitRadius) found = n;
      });
      if (found?.type === "founder" && found.founder) {
        setSelectedFounder(found.founder);
        setSelectedVC(null);
        const targetScale = 1.6;
        zoomRef.current.targetScale = targetScale;
        zoomRef.current.targetTx = dimRef.current.w / 2 - found.x * targetScale;
        zoomRef.current.targetTy = dimRef.current.h / 2 - found.y * targetScale;
      } else if (found?.type === "vc" && found.vcData) {
        setSelectedVC(found.vcData);
        setSelectedFounder(null);
        const targetScale = 1.6;
        zoomRef.current.targetScale = targetScale;
        zoomRef.current.targetTx = dimRef.current.w / 2 - found.x * targetScale;
        zoomRef.current.targetTy = dimRef.current.h / 2 - found.y * targetScale;
      } else if (!found) {
        setSelectedFounder(null);
        setSelectedVC(null);
        zoomRef.current.targetScale = 1;
        zoomRef.current.targetTx = 0;
        zoomRef.current.targetTy = 0;
      }
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mousedown", handleMouseDown);
    canvas.addEventListener("mouseup", handleMouseUp);
    canvas.addEventListener("mouseleave", handleMouseUp);
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    canvas.addEventListener("click", handleClick);

    return () => {
      cancelAnimationFrame(animRef.current);
      resizeObserver.disconnect();
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mousedown", handleMouseDown);
      canvas.removeEventListener("mouseup", handleMouseUp);
      canvas.removeEventListener("mouseleave", handleMouseUp);
      canvas.removeEventListener("wheel", handleWheel);
      canvas.removeEventListener("click", handleClick);
    };
  }, [selectedFounder, selectedVC]);

  const dismissPanel = () => {
    setSelectedFounder(null);
    setSelectedVC(null);
    zoomRef.current.targetScale = 1;
    zoomRef.current.targetTx = 0;
    zoomRef.current.targetTy = 0;
  };

  const connectedFounders = selectedVC ? getConnectedFounders(selectedVC.name) : [];

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full relative rounded-2xl overflow-hidden border border-border/40 bg-graph-bg">
        <canvas ref={canvasRef} className="w-full h-full" />

        {!introComplete && introPhase >= 1 && (
          <button
            onClick={skipIntro}
            className="absolute top-4 right-4 px-3 py-1.5 rounded-full glass text-xs font-medium text-muted-foreground hover:text-foreground transition-all"
          >
            Skip intro
          </button>
        )}

        <AnimatePresence>
          {introPhase >= 4 && signalsCount > 0 && !selectedFounder && !selectedVC && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className="absolute top-4 left-1/2 -translate-x-1/2 glass-panel px-4 py-2 rounded-full flex items-center gap-2"
            >
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-graph-accent opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-graph-accent" />
              </span>
              <span className="text-sm font-semibold text-foreground">{signalsCount} hot signals detected</span>
              <span className="text-xs text-muted-foreground">— click a node to explore</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Legend */}
        <div className="absolute bottom-3 left-3 glass-float px-3 py-2 rounded-lg text-[10px] flex items-center gap-3">
          {Object.entries(SECTOR_COLORS).map(([name, color]) => (
            <span key={name} className="flex items-center gap-1.5 text-muted-foreground">
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
              {name}
            </span>
          ))}
          <span className="w-px h-3 bg-border/50" />
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <span className="w-3 h-3 rounded-[3px] border-2 flex items-center justify-center" style={{ borderColor: VC_COLOR }}>
              <Building2 className="h-1.5 w-1.5" style={{ color: VC_COLOR }} />
            </span>
            VC / Investor
          </span>
        </div>

        {founders.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
            No founders match current filters.
          </div>
        )}
      </div>

      {/* Founder detail panel */}
      <AnimatePresence>
        {selectedFounder && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="absolute top-3 right-3 w-[300px] max-h-[calc(100%-24px)] overflow-y-auto glass-panel rounded-xl p-5 space-y-4"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full overflow-hidden shrink-0"
                  style={{ background: SECTOR_COLORS[selectedFounder.sector] || "#6366f1" }}>
                  {selectedFounder.avatar.startsWith("/") ? (
                    <img src={selectedFounder.avatar} alt={selectedFounder.name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-xs font-bold text-primary-foreground">
                      {selectedFounder.avatar}
                    </div>
                  )}
                </div>
                <div>
                  <h3 className="font-bold text-sm text-foreground">{selectedFounder.name}</h3>
                  <p className="text-[11px] text-muted-foreground">{selectedFounder.title} · {selectedFounder.company}</p>
                </div>
              </div>
              <button onClick={dismissPanel} className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-lg hover:bg-muted/50">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex items-center gap-3">
              <AnimatedScore score={selectedFounder.score} />
              <div className="space-y-1">
                <ActivityBadge activity={selectedFounder.activity} />
                <StatusBadge status={selectedFounder.status} />
              </div>
            </div>

            <p className="text-xs text-foreground/75 leading-relaxed">{selectedFounder.scoreExplanation}</p>

            <div>
              <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Signals</h4>
              <div className="flex flex-wrap gap-1.5">
                {selectedFounder.signals.map((signal, i) => (
                  <motion.span
                    key={signal}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.08 }}
                    className="px-2 py-1 rounded-md bg-primary/8 text-primary text-[10px] font-medium border border-primary/10"
                  >
                    <Zap className="inline h-2.5 w-2.5 mr-0.5 -mt-px" />{signal}
                  </motion.span>
                ))}
              </div>
            </div>

            <div>
              <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">VC Connections</h4>
              <div className="flex flex-wrap gap-1.5">
                {selectedFounder.vcConnections.map((conn, i) => {
                  const vcData = activeVCNodes.find(v => v.name === conn.vc);
                  return (
                    <motion.span
                      key={conn.vc}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: 0.2 + i * 0.06 }}
                      className="px-2 py-1 rounded-md bg-accent/8 text-accent text-[10px] font-semibold border border-accent/10"
                    >
                      {vcData ? vcData.employee : conn.vc}
                      <span className="text-muted-foreground font-normal"> · {conn.vc} · {new Date(conn.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                    </motion.span>
                  );
                })}
              </div>
            </div>

            <div className="flex gap-3 pt-2 border-t border-border/40">
              <a href={selectedFounder.linkedinUrl} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-primary hover:underline font-medium">
                <Linkedin className="h-3.5 w-3.5" /> LinkedIn
              </a>
              <a href={selectedFounder.xUrl} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs text-primary hover:underline font-medium">
                <Twitter className="h-3.5 w-3.5" /> X
              </a>
            </div>

            {onStatusChange && (
              <div className="pt-2 border-t border-border/40">
                <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Update Status</h4>
                <Select value={selectedFounder.status} onValueChange={(v) => onStatusChange(selectedFounder.id, v as FounderStatus)}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="new">New</SelectItem>
                    <SelectItem value="contacted">Contacted</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="closed">Closed</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <p className="text-[10px] text-muted-foreground">
              {selectedFounder.country} · {selectedFounder.sector} · Last active: {selectedFounder.lastActivity}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* VC detail panel */}
      <AnimatePresence>
        {selectedVC && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="absolute top-3 right-3 w-[300px] max-h-[calc(100%-24px)] overflow-y-auto glass-panel rounded-xl p-5 space-y-4"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-lg overflow-hidden shrink-0 bg-background border border-border/60 p-1.5 flex items-center justify-center">
                  <img src={selectedVC.logo} alt={selectedVC.name} className="w-full h-full object-contain" loading="lazy" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-foreground">{selectedVC.employee}</h3>
                  <p className="text-[11px] text-muted-foreground">{selectedVC.employeeRole}</p>
                  <p className="text-[11px] font-semibold" style={{ color: VC_COLOR }}>{selectedVC.name}</p>
                </div>
              </div>
              <button onClick={dismissPanel} className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-lg hover:bg-muted/50">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-semibold uppercase tracking-wider bg-primary/10 text-primary border border-primary/10">
                <Building2 className="h-3 w-3" />
                Venture Capital
              </span>
            </div>

            <div>
              <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Users className="h-3 w-3" />
                Connected Founders ({connectedFounders.length})
              </h4>
              <div className="space-y-2">
                {connectedFounders.map((f, i) => (
                  <motion.button
                    key={f.id}
                    initial={{ opacity: 0, x: 8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 + i * 0.06 }}
                    onClick={() => {
                      setSelectedVC(null);
                      setSelectedFounder(f);
                    }}
                    className="flex items-center gap-2.5 w-full p-2 rounded-lg hover:bg-secondary/50 transition-colors text-left"
                  >
                    <div className="w-7 h-7 rounded-full overflow-hidden shrink-0"
                      style={{ background: SECTOR_COLORS[f.sector] || "#6366f1" }}>
                      {f.avatar.startsWith("/") ? (
                        <img src={f.avatar} alt={f.name} className="w-full h-full object-cover" loading="lazy" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[9px] font-bold text-primary-foreground">
                          {f.avatar}
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold truncate">{f.name}</div>
                      <div className="text-[10px] text-muted-foreground truncate">{f.title} · {f.company}</div>
                    </div>
                    <div className="text-right">
                      <span className={`text-xs font-mono font-bold ${f.score >= 80 ? "text-score-high" : f.score >= 60 ? "text-score-medium" : "text-score-low"}`}>
                        {f.score}
                      </span>
                    </div>
                  </motion.button>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AnimatedScore({ score }: { score: number }) {
  const [displayed, setDisplayed] = useState(0);
  const ref = useRef<number>();

  useEffect(() => {
    setDisplayed(0);
    let current = 0;
    const step = () => {
      current += Math.ceil(score / 30);
      if (current >= score) {
        setDisplayed(score);
        return;
      }
      setDisplayed(current);
      ref.current = requestAnimationFrame(step);
    };
    ref.current = requestAnimationFrame(step);
    return () => { if (ref.current) cancelAnimationFrame(ref.current); };
  }, [score]);

  const color = score >= 80 ? "text-score-high border-score-high/30" : score >= 60 ? "text-score-medium border-score-medium/30" : "text-score-low border-score-low/30";

  return (
    <div className={`w-12 h-12 rounded-full border-2 font-mono font-bold text-lg flex items-center justify-center ${color}`}>
      {displayed}
    </div>
  );
}
