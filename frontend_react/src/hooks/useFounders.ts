import { useQuery } from "@tanstack/react-query";
import { Founder, VCNode } from "@/data/mockFounders";

export function useFounders() {
  return useQuery<Founder[]>({
    queryKey: ["founders"],
    queryFn: async () => {
      const res = await fetch("/founders");
      if (!res.ok) throw new Error("Failed to fetch founders");
      return res.json();
    },
    refetchInterval: 30_000,
  });
}

export function useVCNodes() {
  return useQuery<VCNode[]>({
    queryKey: ["vc-nodes"],
    queryFn: async () => {
      const res = await fetch("/founders/vcs");
      if (!res.ok) throw new Error("Failed to fetch VC nodes");
      return res.json();
    },
    staleTime: Infinity,
  });
}
