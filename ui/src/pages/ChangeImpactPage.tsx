import React, { useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Zap,
  ShieldAlert,
  Layers,
  FileText,
  Building2,
  GitPullRequest,
  Search,
  ArrowRight,
  ExternalLink,
} from "lucide-react";

import { analyzeImpact, getPart } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { getLifecycleBadgeClass } from "@/lib/utils";

export function ChangeImpactPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialPart = searchParams.get("part") || "PMP-0010";

  const [partInput, setPartInput] = useState(initialPart);
  const [activePart, setActivePart] = useState(initialPart);

  // Query impact analysis
  const {
    data: impact,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["change-impact", activePart],
    queryFn: () => analyzeImpact(activePart),
    enabled: Boolean(activePart.trim()),
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!partInput.trim()) return;
    const clean = partInput.trim().toUpperCase();
    setActivePart(clean);
    setSearchParams({ part: clean });
  };

  const getSeverityBadge = (level?: string) => {
    const l = (level || "").toUpperCase();
    switch (l) {
      case "CRITICAL":
        return "bg-rose-500 text-white font-bold animate-pulse";
      case "HIGH":
        return "bg-red-500 text-white font-bold";
      case "MEDIUM":
        return "bg-amber-500 text-white font-semibold";
      case "LOW":
        return "bg-blue-500 text-white font-medium";
      default:
        return "bg-slate-500 text-white";
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Change Impact & Blast-Radius Analysis
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Evaluate cross-functional consequences before altering, revving, or obsoleting any part.
        </p>
      </div>

      {/* Part Search Input */}
      <Card>
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2 max-w-lg">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={partInput}
                onChange={(e) => setPartInput(e.target.value)}
                placeholder="Enter target component (e.g. PMP-0010, PMP-0290)..."
                aria-label="Target part number for impact analysis"
                data-testid="impact-part-input"
                className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg bg-background border border-border font-mono uppercase text-foreground focus:ring-2 focus:ring-primary"
              />
            </div>
            <Button type="submit" size="sm" data-testid="evaluate-impact-button">
              Evaluate Impact
            </Button>
          </form>

          {/* Quick presets */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Examples:</span>
            {["PMP-0010", "PMP-0290", "PMP-0001", "PMP-0021"].map((p) => (
              <button
                key={p}
                onClick={() => {
                  setPartInput(p);
                  setActivePart(p);
                  setSearchParams({ part: p });
                }}
                className={`px-2 py-0.5 rounded font-mono text-xs ${
                  activePart === p
                    ? "bg-primary text-primary-foreground font-bold"
                    : "bg-muted hover:bg-muted/80 text-foreground"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Impact Overview Header */}
      {impact && (
        <div className="p-6 rounded-xl border border-border bg-card/60 backdrop-blur-md flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-sm">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className="font-mono text-xl font-bold text-foreground">
                {impact.target_part_number}
              </span>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${getLifecycleBadgeClass(
                  impact.target_lifecycle_state
                )}`}
              >
                {impact.target_lifecycle_state}
              </span>
              <span className={`px-3 py-1 rounded-full text-xs uppercase tracking-wider ${getSeverityBadge(impact.impact_level)}`}>
                Severity: {impact.impact_level}
              </span>
            </div>
            <h3 className="text-base font-semibold text-foreground">{impact.target_part_name}</h3>
          </div>

          <div className="flex items-center gap-3">
            <Button
              size="sm"
              onClick={() => navigate(`/changes?part=${impact.target_part_number}`)}
              className="gap-2"
            >
              <Zap className="w-4 h-4 text-amber-300" /> Propose Change Request (ECR)
            </Button>
          </div>
        </div>
      )}

      {/* Blast Radius Breakdown Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      ) : isError ? (
        <ErrorState
          title={`Impact analysis failed for ${activePart}`}
          message={(error as Error)?.message}
          onRetry={refetch}
        />
      ) : !impact ? (
        <EmptyState title="No impact data available" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Affected Parent Assemblies */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Layers className="w-4 h-4 text-primary" /> Affected Assemblies ({impact.all_affected_assemblies?.length || 0})
              </CardTitle>
              <Badge variant="outline">{impact.direct_parents?.length || 0} Direct</Badge>
            </CardHeader>
            <CardContent>
              {impact.all_affected_assemblies?.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  No parent assemblies consume this part. Component is standalone or top-level.
                </p>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {impact.all_affected_assemblies?.map((assy) => (
                    <div
                      key={assy}
                      className="flex items-center justify-between p-2.5 rounded-lg border border-border/60 bg-muted/30 hover:bg-muted/70 transition-colors"
                    >
                      <span className="font-mono text-sm font-semibold text-foreground">
                        {assy}
                      </span>
                      <div className="flex items-center gap-2">
                        {impact.direct_parents?.includes(assy) && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300">
                            DIRECT PARENT
                          </span>
                        )}
                        <Link
                          to={`/bom?part=${assy}`}
                          className="text-xs text-primary hover:underline flex items-center gap-1"
                        >
                          View BOM <ExternalLink className="w-3 h-3" />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Associated Engineering Documents */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="w-4 h-4 text-amber-500" /> Engineering Documents ({impact.associated_documents?.length || 0})
              </CardTitle>
              <Badge variant="outline">Requires Revision</Badge>
            </CardHeader>
            <CardContent>
              {impact.associated_documents?.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  No CAD drawings or specifications currently linked in vault.
                </p>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {impact.associated_documents?.map((doc) => (
                    <div
                      key={doc}
                      className="flex items-center justify-between p-2.5 rounded-lg border border-border/60 bg-muted/30"
                    >
                      <span className="font-mono text-sm font-medium text-foreground">
                        {doc}
                      </span>
                      <span className="text-xs text-muted-foreground">Drawing / Spec</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Sourcing & Approved Suppliers (AML) */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Building2 className="w-4 h-4 text-emerald-500" /> Sourcing & Vendors ({impact.approved_suppliers?.length || 0})
              </CardTitle>
              <Badge variant="outline">AML Partners</Badge>
            </CardHeader>
            <CardContent>
              {impact.approved_suppliers?.length === 0 ? (
                <div className="p-3 rounded-lg bg-orange-50 dark:bg-orange-950/20 text-orange-800 dark:text-orange-300 text-xs">
                  <strong>Warning:</strong> No registered AML suppliers found for this component.
                </div>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {impact.approved_suppliers?.map((supp) => (
                    <div
                      key={supp}
                      className="flex items-center justify-between p-2.5 rounded-lg border border-border/60 bg-muted/30"
                    >
                      <span className="text-sm font-semibold text-foreground">{supp}</span>
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                        APPROVED VENDOR
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Active Change Requests */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <GitPullRequest className="w-4 h-4 text-purple-500" /> Active Change Notices ({impact.active_change_requests?.length || 0})
              </CardTitle>
              <Badge variant="outline">In-Flight Changes</Badge>
            </CardHeader>
            <CardContent>
              {impact.active_change_requests?.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">
                  No active change requests currently open against this component.
                </p>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {impact.active_change_requests?.map((cr) => (
                    <div
                      key={cr}
                      className="flex items-center justify-between p-2.5 rounded-lg border border-border/60 bg-muted/30 hover:bg-muted/70 transition-colors"
                    >
                      <span className="font-mono text-sm font-bold text-foreground">{cr}</span>
                      <span className="text-xs text-muted-foreground">In Review</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

