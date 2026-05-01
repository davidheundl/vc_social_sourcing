import { FounderStatus } from "@/data/mockFounders";

const STATUS_CONFIG: Record<FounderStatus, { label: string; className: string }> = {
  new: { label: "New", className: "bg-blue-100 text-blue-700 border-blue-200" },
  contacted: { label: "Contacted", className: "bg-amber-100 text-amber-700 border-amber-200" },
  in_progress: { label: "In Progress", className: "bg-purple-100 text-purple-700 border-purple-200" },
  closed: { label: "Closed", className: "bg-emerald-100 text-emerald-700 border-emerald-200" },
};

export function StatusBadge({ status }: { status: FounderStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${config.className}`}>
      {config.label}
    </span>
  );
}
