import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  GitCompare,
  PlusCircle,
  MinusCircle,
  Edit3,
  CheckCircle2,
  ArrowRight,
  Filter,
} from "lucide-react";

import { compareBoms } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";

export function BomComparePage() {
  const [assemblyA, setAssemblyA] = useState("PMP-0001");
  const [assemblyB, setAssemblyB] = useState("PMP-0002");
  const [filterType, setFilterType] = useState<string>("ALL");

  // Query comparison results
  const {
    data: comparison,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["bom-compare", assemblyA, assemblyB],
    queryFn: () => compareBoms(assemblyA, assemblyB),
    enabled: Boolean(assemblyA.trim() && assemblyB.trim()),
  });

  const handleSwap = () => {
    setAssemblyA(assemblyB);
    setAssemblyB(assemblyA);
  };

  const differences = comparison?.differences || [];
  const filteredDifferences = differences.filter((item) => {
    if (filterType === "ALL") return true;
    return item.change_type === filterType;
  });

  const addedCount = comparison?.added_parts?.length || 0;
  const removedCount = comparison?.removed_parts?.length || 0;
  const modifiedCount = comparison?.modified_parts?.length || 0;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          BOM Comparison & Reconciliation
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Perform delta analysis between product revisions, distinct pump models, or EBOM vs. MBOM manufacturing baselines.
        </p>
      </div>

      {/* Assembly Comparison Controls */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            {/* Assembly A Input */}
            <div className="flex-1 space-y-1">
              <label htmlFor="assy-a" className="text-xs font-semibold text-muted-foreground block">
                Assembly A (Baseline)
              </label>
              <input
                id="assy-a"
                data-testid="assy-a-input"
                type="text"
                value={assemblyA}
                onChange={(e) => setAssemblyA(e.target.value.trim().toUpperCase())}
                placeholder="e.g. PMP-0001 or PMP-0001:EBOM"
                className="w-full px-3 py-2 rounded-lg text-sm bg-background border border-border font-mono uppercase text-foreground focus:ring-2 focus:ring-primary"
              />
            </div>

            {/* Swap Button */}
            <div className="flex items-center justify-center pt-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={handleSwap}
                title="Swap baseline and comparison"
                className="rounded-full"
              >
                <GitCompare className="w-5 h-5 text-muted-foreground hover:text-primary" />
              </Button>
            </div>

            {/* Assembly B Input */}
            <div className="flex-1 space-y-1">
              <label htmlFor="assy-b" className="text-xs font-semibold text-muted-foreground block">
                Assembly B (Comparison)
              </label>
              <input
                id="assy-b"
                data-testid="assy-b-input"
                type="text"
                value={assemblyB}
                onChange={(e) => setAssemblyB(e.target.value.trim().toUpperCase())}
                placeholder="e.g. PMP-0002 or PMP-0001:MBOM"
                className="w-full px-3 py-2 rounded-lg text-sm bg-background border border-border font-mono uppercase text-foreground focus:ring-2 focus:ring-primary"
              />
            </div>

            {/* Compare Action Button */}
            <div className="flex items-end">
              <Button
                onClick={() => refetch()}
                data-testid="compare-boms-button"
                className="gap-2 w-full md:w-auto"
              >
                <GitCompare className="w-4 h-4" /> Compare
              </Button>
            </div>
          </div>

          {/* Preset Buttons for Quick Demo Testing */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border/50 text-xs text-muted-foreground">
            <span>Presets:</span>
            <button
              onClick={() => {
                setAssemblyA("PMP-0001");
                setAssemblyB("PMP-0002");
              }}
              className="px-2.5 py-1 rounded bg-muted hover:bg-muted/80 text-foreground font-mono text-xs"
            >
              PMP-0001 vs PMP-0002
            </button>
            <button
              onClick={() => {
                setAssemblyA("PMP-0001:EBOM");
                setAssemblyB("PMP-0001:MBOM");
              }}
              className="px-2.5 py-1 rounded bg-muted hover:bg-muted/80 text-foreground font-mono text-xs"
            >
              EBOM vs MBOM (Planted #4)
            </button>
            <button
              onClick={() => {
                setAssemblyA("PMP-0003");
                setAssemblyB("PMP-0004");
              }}
              className="px-2.5 py-1 rounded bg-muted hover:bg-muted/80 text-foreground font-mono text-xs"
            >
              PMP-0003 vs PMP-0004
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Delta Metrics Overview */}
      {comparison && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card className="border-emerald-500/30 bg-emerald-50/20 dark:bg-emerald-950/10">
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-400 block">
                  Added in Assembly B
                </span>
                <span className="text-2xl font-bold text-emerald-800 dark:text-emerald-300">
                  {addedCount} parts
                </span>
              </div>
              <PlusCircle className="w-8 h-8 text-emerald-500/60" />
            </CardContent>
          </Card>

          <Card className="border-rose-500/30 bg-rose-50/20 dark:bg-rose-950/10">
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-rose-700 dark:text-rose-400 block">
                  Removed from Assembly B
                </span>
                <span className="text-2xl font-bold text-rose-800 dark:text-rose-300">
                  {removedCount} parts
                </span>
              </div>
              <MinusCircle className="w-8 h-8 text-rose-500/60" />
            </CardContent>
          </Card>

          <Card className="border-amber-500/30 bg-amber-50/20 dark:bg-amber-950/10">
            <CardContent className="p-4 flex items-center justify-between">
              <div>
                <span className="text-xs font-semibold text-amber-700 dark:text-amber-400 block">
                  Quantity / Spec Changes
                </span>
                <span className="text-2xl font-bold text-amber-800 dark:text-amber-300">
                  {modifiedCount} parts
                </span>
              </div>
              <Edit3 className="w-8 h-8 text-amber-500/60" />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Comparison Results Table */}
      <Card>
        <CardHeader className="pb-3 border-b border-border/50">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                Comparison Diff: <span className="font-mono text-primary">{assemblyA}</span>
                <ArrowRight className="w-4 h-4 text-muted-foreground" />
                <span className="font-mono text-primary">{assemblyB}</span>
              </CardTitle>
              <CardDescription>
                Detailed component-by-component usage differences
              </CardDescription>
            </div>

            {/* Filter by Change Type */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">Filter:</span>
              {["ALL", "ADDED", "REMOVED", "QUANTITY_CHANGED", "UNCHANGED"].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterType(f)}
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    filterType === f
                      ? "bg-primary text-primary-foreground font-semibold"
                      : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                  }`}
                >
                  {f.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6">
              <TableSkeleton rows={6} cols={6} />
            </div>
          ) : isError ? (
            <div className="p-6">
              <ErrorState
                title="Failed to compare BOM structures"
                message={(error as Error)?.message}
                onRetry={refetch}
              />
            </div>
          ) : filteredDifferences.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="No differences found"
                description={`Assemblies '${assemblyA}' and '${assemblyB}' are structurally identical for the chosen filter.`}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left font-mono">
                <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border font-sans">
                  <tr>
                    <th className="py-3 px-4">Change Type</th>
                    <th className="py-3 px-4">Part Number</th>
                    <th className="py-3 px-4">Component Name</th>
                    <th className="py-3 px-4 text-center">Qty in A</th>
                    <th className="py-3 px-4 text-center">Qty in B</th>
                    <th className="py-3 px-4">Delta</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40 text-xs">
                  {filteredDifferences.map((item, idx) => {
                    const qa = item.quantity_a ?? 0;
                    const qb = item.quantity_b ?? 0;
                    const delta = qb - qa;

                    let rowStyle = "";
                    let badgeColor = "";

                    if (item.change_type === "ADDED") {
                      rowStyle = "bg-emerald-500/10 dark:bg-emerald-950/20";
                      badgeColor = "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300";
                    } else if (item.change_type === "REMOVED") {
                      rowStyle = "bg-rose-500/10 dark:bg-rose-950/20";
                      badgeColor = "bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300";
                    } else if (item.change_type === "QUANTITY_CHANGED") {
                      rowStyle = "bg-amber-500/10 dark:bg-amber-950/20";
                      badgeColor = "bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300";
                    }

                    return (
                      <tr key={idx} className={`hover:bg-muted/30 transition-colors ${rowStyle}`}>
                        <td className="py-3 px-4 font-sans">
                          <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold ${badgeColor}`}>
                            {item.change_type}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-bold text-foreground">
                          {item.part_number}
                        </td>
                        <td className="py-3 px-4 font-sans font-medium text-foreground">
                          {item.name}
                        </td>
                        <td className="py-3 px-4 text-center font-bold">
                          {item.quantity_a !== null ? `${item.quantity_a} ${item.unit || "ea"}` : "-"}
                        </td>
                        <td className="py-3 px-4 text-center font-bold">
                          {item.quantity_b !== null ? `${item.quantity_b} ${item.unit || "ea"}` : "-"}
                        </td>
                        <td className="py-3 px-4 font-bold">
                          {item.change_type === "ADDED" && (
                            <span className="text-emerald-600 dark:text-emerald-400">+{qb}</span>
                          )}
                          {item.change_type === "REMOVED" && (
                            <span className="text-rose-600 dark:text-rose-400">-{qa}</span>
                          )}
                          {item.change_type === "QUANTITY_CHANGED" && (
                            <span className="text-amber-600 dark:text-amber-400">
                              {delta > 0 ? `+${delta}` : delta}
                            </span>
                          )}
                          {item.change_type === "UNCHANGED" && (
                            <span className="text-muted-foreground">0</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

