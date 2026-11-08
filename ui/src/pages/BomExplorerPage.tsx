import React, { useState, useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Layers,
  Network,
  ListTree,
  ChevronRight,
  ChevronDown,
  AlertTriangle,
  Search,
  ExternalLink,
  Plus,
} from "lucide-react";

import { getPartBom, getPart } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton, TableSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { getLifecycleBadgeClass } from "@/lib/utils";

// Known planted obsolete part numbers for real-time highlighting
const OBSOLETE_PARTS = new Set([
  "PMP-0021", "PMP-0042", "PMP-0063", "PMP-0084",
  "PMP-0105", "PMP-0126", "PMP-0147", "PMP-0168"
]);

interface SubBomBranchProps {
  parentPartNumber: string;
  depth: number;
}

function SubBomBranch({ parentPartNumber, depth }: SubBomBranchProps) {
  const { data: children, isLoading, isError } = useQuery({
    queryKey: ["sub-bom", parentPartNumber],
    queryFn: () => getPartBom(parentPartNumber, 1),
    staleTime: 1000 * 60 * 5,
  });

  if (isLoading) {
    return (
      <div className="py-2.5 px-4 flex items-center gap-2 text-xs text-muted-foreground animate-pulse font-sans">
        <Skeleton className="w-3.5 h-3.5 rounded-full" />
        <span>Lazy-loading child components for {parentPartNumber}...</span>
      </div>
    );
  }

  if (isError || !children || children.length === 0) {
    return (
      <div className="py-2 px-4 text-xs text-muted-foreground italic font-sans">
        No direct child components found for {parentPartNumber} (leaf part).
      </div>
    );
  }

  return (
    <div className="border-l-2 border-primary/40 my-1 py-1.5 pl-3 bg-muted/25 rounded-r-md space-y-1">
      <div className="text-[10px] font-sans font-semibold uppercase tracking-wider text-muted-foreground px-2 py-0.5 flex items-center justify-between">
        <span>Lazy-loaded Subassembly: {parentPartNumber}</span>
        <span className="font-mono text-primary">{children.length} component(s)</span>
      </div>
      <table className="w-full text-xs font-mono">
        <tbody>
          {children.map((child, cIdx) => (
            <tr key={`${child.child_part_number}-${cIdx}`} className="hover:bg-muted/40 transition-colors">
              <td className="py-1 px-2 text-muted-foreground w-12">#{child.find_number || (cIdx + 1) * 10}</td>
              <td className="py-1 px-2 font-semibold text-primary">
                <Link to={`/parts/${child.child_part_number}`} className="hover:underline">
                  {child.child_part_number}
                </Link>
              </td>
              <td className="py-1 px-2 font-sans font-medium text-foreground truncate max-w-xs">{child.child_name || "-"}</td>
              <td className="py-1 px-2 font-bold text-foreground w-20">{child.quantity} {child.unit || "ea"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BomExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialPart = searchParams.get("part") || "PMP-0001";

  const [partInput, setPartInput] = useState(initialPart);
  const [activePart, setActivePart] = useState(initialPart);
  const [levels, setLevels] = useState<number>(3);
  const [viewMode, setViewMode] = useState<"tree" | "graph">("tree");
  const [nodeLimit, setNodeLimit] = useState<number>(20);
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});

  // Query Root Assembly Details
  const { data: rootPart, isLoading: isRootLoading } = useQuery({
    queryKey: ["part", activePart],
    queryFn: () => getPart(activePart),
  });

  // Query BOM Explosion
  const {
    data: bomLinks,
    isLoading: isBomLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["bom-explosion", activePart, levels],
    queryFn: () => getPartBom(activePart, levels),
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!partInput.trim()) return;
    const clean = partInput.trim().toUpperCase();
    setActivePart(clean);
    setSearchParams({ part: clean });
  };

  const toggleExpand = (key: string) => {
    setExpandedNodes((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Graph nodes capped for performance to prevent UI freezing on large trees
  const graphDisplayItems = useMemo(() => {
    if (!bomLinks) return [];
    return bomLinks.slice(0, nodeLimit);
  }, [bomLinks, nodeLimit]);

  const hasMoreNodes = (bomLinks?.length || 0) > nodeLimit;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Page Title & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Multi-Level BOM Explorer
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Traverse and visualize recursive assembly product structures, usage links, and compliance risks.
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 border border-border rounded-lg p-1 bg-card">
          <button
            onClick={() => setViewMode("tree")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              viewMode === "tree"
                ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <ListTree className="w-3.5 h-3.5" /> Tree View
          </button>
          <button
            onClick={() => setViewMode("graph")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              viewMode === "graph"
                ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Network className="w-3.5 h-3.5" /> Graph View
          </button>
        </div>
      </div>

      {/* Assembly Selector & Level Control */}
      <Card>
        <CardContent className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Part Lookup Form */}
          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={partInput}
                onChange={(e) => setPartInput(e.target.value)}
                placeholder="Enter parent part number (e.g. PMP-0001)..."
                aria-label="Enter parent part number"
                data-testid="bom-part-input"
                className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg bg-background border border-border font-mono uppercase text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <Button type="submit" size="sm" data-testid="load-bom-button">
              Load BOM
            </Button>
          </form>

          {/* Quick Assembly Presets & Level Selector */}
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>Quick Select:</span>
              {["PMP-0001", "PMP-0002", "PMP-0003", "PMP-0006"].map((p) => (
                <button
                  key={p}
                  onClick={() => {
                    setPartInput(p);
                    setActivePart(p);
                    setSearchParams({ part: p });
                  }}
                  className={`px-2 py-1 rounded font-mono text-xs ${
                    activePart === p
                      ? "bg-primary/20 text-primary font-bold border border-primary/30"
                      : "bg-muted hover:bg-muted/80 text-foreground"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 border-l border-border pl-4">
              <label htmlFor="levels-select" className="text-xs font-medium text-muted-foreground">
                Explosion Depth:
              </label>
              <select
                id="levels-select"
                value={levels}
                onChange={(e) => setLevels(Number(e.target.value))}
                className="text-xs font-semibold py-1 px-2 rounded border border-border bg-background text-foreground focus:ring-2 focus:ring-primary"
              >
                <option value={1}>1 Level (Direct)</option>
                <option value={2}>2 Levels</option>
                <option value={3}>3 Levels</option>
                <option value={4}>4 Levels</option>
                <option value={5}>5 Levels (Deep)</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Assembly Header Banner */}
      {rootPart && (
        <div className="flex items-center justify-between p-4 rounded-lg border border-border bg-card/60 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-lg font-bold text-foreground">
                  {rootPart.part_number}
                </span>
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${getLifecycleBadgeClass(
                    rootPart.lifecycle_state
                  )}`}
                >
                  {rootPart.lifecycle_state}
                </span>
                <span className="font-mono text-xs text-muted-foreground">
                  Rev {rootPart.version_label}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">{rootPart.name}</p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-xs text-muted-foreground block">Exploded Structure</span>
            <span className="font-semibold text-sm text-foreground">
              {bomLinks?.length || 0} usage links returned
            </span>
          </div>
        </div>
      )}

      {/* BOM Presentation Container */}
      <Card>
        <CardHeader className="pb-3 border-b border-border/50">
          <CardTitle className="text-base flex items-center justify-between">
            <span>Product Hierarchy: {activePart}</span>
            {isBomLoading && <span className="text-xs font-normal text-muted-foreground animate-pulse">Exploding hierarchy...</span>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isBomLoading || isRootLoading ? (
            <div className="p-6">
              <TableSkeleton rows={8} cols={6} />
            </div>
          ) : isError ? (
            <div className="p-6">
              <ErrorState
                title={`Could not load BOM for ${activePart}`}
                message={(error as Error)?.message}
                onRetry={refetch}
              />
            </div>
          ) : !bomLinks || bomLinks.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="No BOM usage links found"
                description={`Assembly '${activePart}' contains no child components or is a leaf part.`}
              />
            </div>
          ) : viewMode === "tree" ? (
            /* ============================================================= */
            /* TREE VIEW                                                     */
            /* ============================================================= */
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                  <tr>
                    <th className="py-3 px-4 w-20">Level</th>
                    <th className="py-3 px-4">Find #</th>
                    <th className="py-3 px-4">Component Part Number</th>
                    <th className="py-3 px-4">Part Name</th>
                    <th className="py-3 px-4">Quantity</th>
                    <th className="py-3 px-4">Unit</th>
                    <th className="py-3 px-4">Status & Compliance</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40 font-mono text-xs">
                  {bomLinks.map((link, idx) => {
                    const depth = link.level || 1;
                    const isObsolete = OBSOLETE_PARTS.has(link.child_part_number);
                    const isExpanded = Boolean(expandedNodes[link.child_part_number]);

                    return (
                      <React.Fragment key={`${link.parent_part_number}-${link.child_part_number}-${idx}`}>
                        <tr
                          className={`hover:bg-muted/30 transition-colors ${
                            isObsolete ? "bg-red-500/10 dark:bg-red-950/20" : ""
                          }`}
                        >
                          <td className="py-3 px-4">
                            <span
                              className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                                depth === 1
                                  ? "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300"
                                  : depth === 2
                                  ? "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300"
                                  : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300"
                              }`}
                            >
                              L{depth}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-muted-foreground">
                            {link.find_number || (idx + 1) * 10}
                          </td>
                          <td className="py-3 px-4 font-semibold text-primary">
                            <div
                              className="flex items-center gap-1.5"
                              style={{ paddingLeft: `${(depth - 1) * 16}px` }}
                            >
                              <button
                                type="button"
                                onClick={() => toggleExpand(link.child_part_number)}
                                aria-expanded={isExpanded}
                                aria-label={`Expand children for ${link.child_part_number}`}
                                title={`Expand subassembly ${link.child_part_number}`}
                                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                              >
                                {isExpanded ? (
                                  <ChevronDown className="w-3.5 h-3.5 text-primary" />
                                ) : (
                                  <ChevronRight className="w-3.5 h-3.5" />
                                )}
                              </button>
                              <Link
                                to={`/parts/${link.child_part_number}`}
                                className="hover:underline flex items-center gap-1 font-mono"
                              >
                                {link.child_part_number}
                              </Link>
                            </div>
                          </td>
                          <td className="py-3 px-4 font-sans font-medium text-foreground">
                            {link.child_name || "-"}
                          </td>
                          <td className="py-3 px-4 font-bold text-foreground">
                            {link.quantity}
                          </td>
                          <td className="py-3 px-4 text-muted-foreground">
                            {link.unit || "ea"}
                          </td>
                          <td className="py-3 px-4 font-sans">
                            {isObsolete ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-300 dark:border-rose-800 animate-pulse">
                                <AlertTriangle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />
                                OBSOLETE (Planted #2)
                              </span>
                            ) : (
                              <span className="text-xs text-muted-foreground">Normal</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right font-sans">
                            <Link
                              to={`/bom?part=${link.child_part_number}`}
                              className="inline-flex items-center text-xs text-muted-foreground hover:text-primary transition-colors"
                            >
                              Explore <ExternalLink className="w-3 h-3 ml-1" />
                            </Link>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr key={`${link.child_part_number}-lazy-child`}>
                            <td colSpan={8} className="p-0 pl-12 pr-4 pb-2 bg-muted/10">
                              <SubBomBranch parentPartNumber={link.child_part_number} depth={depth + 1} />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            /* ============================================================= */
            /* GRAPH VIEW (Capped with Show More control to avoid freezing) */
            /* ============================================================= */
            <div className="p-6 space-y-6">
              <div className="flex items-center justify-between text-xs text-muted-foreground pb-2 border-b border-border">
                <span>
                  Visualizing top {graphDisplayItems.length} of {bomLinks.length} hierarchy nodes
                </span>
                <span className="text-muted-foreground">
                  Hierarchy capped to ensure smooth 60fps rendering
                </span>
              </div>

              {/* Node Cards Canvas Simulation */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Root Assembly Node */}
                <div className="p-4 rounded-xl border-2 border-primary bg-primary/5 shadow-sm space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-primary text-primary-foreground">
                      ROOT ASSEMBLY
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">Level 0</span>
                  </div>
                  <h4 className="font-mono font-bold text-base text-foreground">{activePart}</h4>
                  <p className="text-xs text-muted-foreground truncate">{rootPart?.name}</p>
                </div>

                {/* Child Nodes */}
                {graphDisplayItems.map((item, idx) => {
                  const isObsolete = OBSOLETE_PARTS.has(item.child_part_number);
                  return (
                    <div
                      key={`graph-node-${idx}`}
                      className={`p-4 rounded-xl border transition-all space-y-2 ${
                        isObsolete
                          ? "border-rose-400 bg-rose-50/50 dark:bg-rose-950/20 shadow-xs"
                          : "border-border bg-card hover:border-primary/50 shadow-xs"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-muted">
                          L{item.level || 1} • Parent: {item.parent_part_number}
                        </span>
                        <span className="font-mono font-bold text-xs text-foreground">
                          {item.quantity} {item.unit}
                        </span>
                      </div>
                      <div>
                        <Link
                          to={`/parts/${item.child_part_number}`}
                          className="font-mono font-semibold text-primary hover:underline block"
                        >
                          {item.child_part_number}
                        </Link>
                        <p className="text-xs text-foreground font-medium truncate mt-0.5">
                          {item.child_name || "Component"}
                        </p>
                      </div>

                      {isObsolete && (
                        <div className="pt-2 border-t border-rose-200 dark:border-rose-900/60 flex items-center gap-1.5 text-xs font-bold text-rose-700 dark:text-rose-400">
                          <AlertTriangle className="w-3.5 h-3.5" /> Obsolete Component In BOM
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Show More Node Cap Control */}
              {hasMoreNodes && (
                <div className="flex items-center justify-center pt-4">
                  <Button
                    variant="outline"
                    onClick={() => setNodeLimit((prev) => prev + 25)}
                    className="gap-2"
                  >
                    <Plus className="w-4 h-4" /> Load 25 More Nodes ({bomLinks.length - nodeLimit} remaining)
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

