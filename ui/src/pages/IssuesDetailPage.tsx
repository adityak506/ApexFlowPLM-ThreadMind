import React, { useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Copy,
  HelpCircle,
  Shuffle,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  ArrowLeft,
  ExternalLink,
} from "lucide-react";

import { getIssuesByType, getIssuesSummary } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { getLifecycleBadgeClass } from "@/lib/utils";

export function IssuesDetailPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialType = searchParams.get("type") || "duplicates";

  const [activeType, setActiveType] = useState<string>(initialType);
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["issues-by-type", activeType, page],
    queryFn: () => getIssuesByType(activeType, page, pageSize),
  });

  const { data: summary } = useQuery({
    queryKey: ["issues-summary"],
    queryFn: getIssuesSummary,
  });

  const handleTypeChange = (type: string) => {
    setActiveType(type);
    setPage(1);
    setSearchParams({ type });
  };

  const issueTabs = [
    { key: "duplicates", label: "Duplicates", count: summary?.duplicates, icon: Copy },
    { key: "obsolete_in_released", label: "Obsolete in Released", count: summary?.obsolete_in_released, icon: AlertTriangle },
    { key: "unassigned_buy", label: "Unassigned BUY", count: summary?.unassigned_buy, icon: HelpCircle },
    { key: "ebom_mbom_mismatches", label: "EBOM/MBOM Mismatches", count: summary?.ebom_mbom_mismatches, icon: Shuffle },
    { key: "rohs_risks", label: "RoHS Violations", count: summary?.rohs_risks, icon: ShieldAlert },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/")} className="rounded-full">
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            Data Health & Integrity Audits
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Detailed inspection of catalog compliance violations, redundancy, and structure divergences.
          </p>
        </div>
      </div>

      {/* Type Selector Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-border pb-3">
        {issueTabs.map((tab) => {
          const Icon = tab.icon;
          const isSelected = activeType === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => handleTypeChange(tab.key)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                isSelected
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{tab.label}</span>
              {tab.count !== undefined && (
                <span
                  className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                    isSelected ? "bg-primary-foreground/20 text-primary-foreground" : "bg-background text-foreground"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Issue Items Table */}
      <Card>
        <CardHeader className="pb-3 border-b border-border/50">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base capitalize">
              {activeType.replace(/_/g, " ")} Records {data && `(${data.total})`}
            </CardTitle>
            {data && (
              <span className="text-xs text-muted-foreground">
                Page {data.page} of {data.total_pages}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6">
              <TableSkeleton rows={6} cols={5} />
            </div>
          ) : isError ? (
            <div className="p-6">
              <ErrorState message={(error as Error)?.message} onRetry={refetch} />
            </div>
          ) : !data || data.items.length === 0 ? (
            <div className="p-6">
              <EmptyState title="No violations detected" description="All records passed integrity scan for this category." />
            </div>
          ) : (
            <div className="overflow-x-auto">
              {/* Type 1: Duplicates */}
              {activeType === "duplicates" && (
                <div className="divide-y divide-border/50 p-4 space-y-4">
                  {data.items.map((group: any, idx: number) => (
                    <div key={idx} className="p-4 rounded-xl border border-border bg-card space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                          Match Criteria: {group.match_value}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono">
                          {group.parts?.length || 0} Redundant Components
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {group.parts?.map((p: any) => (
                          <div key={p.part_number} className="p-3 rounded-lg border border-border/60 bg-muted/20 flex items-center justify-between">
                            <div>
                              <Link to={`/parts/${p.part_number}`} className="font-mono font-bold text-primary hover:underline text-sm">
                                {p.part_number}
                              </Link>
                              <div className="text-xs font-medium text-foreground">{p.name}</div>
                              <div className="text-[11px] text-muted-foreground mt-0.5">{p.material} • {p.make_buy}</div>
                            </div>
                            <Button size="sm" variant="ghost" onClick={() => navigate(`/impact?part=${p.part_number}`)}>
                              Impact <ExternalLink className="w-3 h-3 ml-1" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Type 2: Obsolete in Released */}
              {activeType === "obsolete_in_released" && (
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                    <tr>
                      <th className="py-3 px-4">Parent Assembly</th>
                      <th className="py-3 px-4">Parent State</th>
                      <th className="py-3 px-4">Obsolete Child Part</th>
                      <th className="py-3 px-4">Child State</th>
                      <th className="py-3 px-4">Usage Qty</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono text-xs">
                    {data.items.map((row: any, idx: number) => (
                      <tr key={idx} className="hover:bg-muted/30 transition-colors bg-red-500/5">
                        <td className="py-3 px-4 font-bold text-primary">
                          <Link to={`/parts/${row.parent_part_number}`} className="hover:underline">
                            {row.parent_part_number}
                          </Link>
                          <span className="font-sans font-normal text-muted-foreground block text-xs truncate max-w-xs">{row.parent_name}</span>
                        </td>
                        <td className="py-3 px-4 font-sans">
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                            {row.parent_lifecycle_state}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-bold text-rose-600 dark:text-rose-400">
                          <Link to={`/parts/${row.obsolete_child_part_number}`} className="hover:underline">
                            {row.obsolete_child_part_number}
                          </Link>
                          <span className="font-sans font-normal text-muted-foreground block text-xs truncate max-w-xs">{row.obsolete_child_name}</span>
                        </td>
                        <td className="py-3 px-4 font-sans">
                          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300">
                            {row.obsolete_child_state}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-semibold text-foreground">
                          {row.quantity} {row.unit}
                        </td>
                        <td className="py-3 px-4 text-right font-sans">
                          <Button size="sm" variant="outline" onClick={() => navigate(`/changes?part=${row.obsolete_child_part_number}`)}>
                            Fix via ECR
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {/* Type 3: Unassigned BUY Components */}
              {activeType === "unassigned_buy" && (
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                    <tr>
                      <th className="py-3 px-4">Part Number</th>
                      <th className="py-3 px-4">Component Name</th>
                      <th className="py-3 px-4">Material</th>
                      <th className="py-3 px-4">State</th>
                      <th className="py-3 px-4">AML Status</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 text-xs">
                    {data.items.map((row: any) => (
                      <tr key={row.part_number} className="hover:bg-muted/30 transition-colors">
                        <td className="py-3 px-4 font-mono font-bold text-primary">
                          <Link to={`/parts/${row.part_number}`} className="hover:underline">
                            {row.part_number}
                          </Link>
                        </td>
                        <td className="py-3 px-4 font-medium text-foreground">{row.name}</td>
                        <td className="py-3 px-4 text-muted-foreground">{row.material || "-"}</td>
                        <td className="py-3 px-4">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold border ${getLifecycleBadgeClass(row.lifecycle_state)}`}>
                            {row.lifecycle_state}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300">
                            0 SUPPLIERS
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Button size="sm" variant="ghost" onClick={() => navigate(`/parts/${row.part_number}`)}>
                            View Part <ExternalLink className="w-3 h-3 ml-1" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {/* Type 4: EBOM vs MBOM Mismatches */}
              {activeType === "ebom_mbom_mismatches" && (
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                    <tr>
                      <th className="py-3 px-4">Parent Assembly</th>
                      <th className="py-3 px-4">Child Component</th>
                      <th className="py-3 px-4 text-center">EBOM Qty</th>
                      <th className="py-3 px-4 text-center">MBOM Qty</th>
                      <th className="py-3 px-4">Discrepancy Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 font-mono text-xs">
                    {data.items.map((row: any, idx: number) => (
                      <tr key={idx} className="hover:bg-muted/30 transition-colors bg-purple-500/5">
                        <td className="py-3 px-4 font-bold text-primary">
                          <Link to={`/parts/${row.parent_part_number}`} className="hover:underline">
                            {row.parent_part_number}
                          </Link>
                        </td>
                        <td className="py-3 px-4 font-semibold text-foreground">
                          <Link to={`/parts/${row.child_part_number}`} className="hover:underline">
                            {row.child_part_number}
                          </Link>
                          <span className="font-sans font-normal text-muted-foreground block text-xs truncate max-w-xs">{row.child_name}</span>
                        </td>
                        <td className="py-3 px-4 text-center font-bold text-blue-600 dark:text-blue-400">
                          {row.ebom_quantity ?? "MISSING"}
                        </td>
                        <td className="py-3 px-4 text-center font-bold text-purple-600 dark:text-purple-400">
                          {row.mbom_quantity ?? "MISSING"}
                        </td>
                        <td className="py-3 px-4 font-sans text-xs text-muted-foreground">
                          {row.ebom_notes || row.mbom_notes || "Quantity mismatch between Engineering and Manufacturing"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {/* Type 5: RoHS Risks */}
              {activeType === "rohs_risks" && (
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                    <tr>
                      <th className="py-3 px-4">Part Number</th>
                      <th className="py-3 px-4">Name</th>
                      <th className="py-3 px-4">Prohibited Hazardous Substance</th>
                      <th className="py-3 px-4">Make/Buy</th>
                      <th className="py-3 px-4">Lifecycle State</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40 text-xs">
                    {data.items.map((row: any) => (
                      <tr key={row.part_number} className="hover:bg-muted/30 transition-colors bg-rose-500/5">
                        <td className="py-3 px-4 font-mono font-bold text-primary">
                          <Link to={`/parts/${row.part_number}`} className="hover:underline">
                            {row.part_number}
                          </Link>
                        </td>
                        <td className="py-3 px-4 font-medium text-foreground">{row.name}</td>
                        <td className="py-3 px-4 font-bold text-rose-600 dark:text-rose-400">
                          {row.material}
                        </td>
                        <td className="py-3 px-4 font-mono text-muted-foreground">{row.make_buy}</td>
                        <td className="py-3 px-4">
                          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold border ${getLifecycleBadgeClass(row.lifecycle_state)}`}>
                            {row.lifecycle_state}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Button size="sm" variant="outline" onClick={() => navigate(`/impact?part=${row.part_number}`)}>
                            Blast Radius
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

