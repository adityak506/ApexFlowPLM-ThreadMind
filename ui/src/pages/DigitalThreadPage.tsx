import React, { useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Workflow,
  Radio,
  FileCheck2,
  Package,
  Layers,
  Sparkles,
  Search,
  AlertTriangle,
  Clock,
  ArrowRight,
  Truck,
  Building,
  ShieldAlert,
  Calendar,
} from "lucide-react";

import { getDigitalThread } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton, TableSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate, getLifecycleBadgeClass } from "@/lib/utils";

export function DigitalThreadPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const initialPart = searchParams.get("part") || "PMP-0290";

  const [partInput, setPartInput] = useState(initialPart);
  const [activePart, setActivePart] = useState(initialPart);

  // Query Digital Thread Data
  const {
    data: thread,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["digital-thread", activePart],
    queryFn: () => getDigitalThread(activePart),
    enabled: Boolean(activePart.trim()),
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!partInput.trim()) return;
    const clean = partInput.trim().toUpperCase();
    setActivePart(clean);
    setSearchParams({ part: clean });
  };

  const handleGenerateImpactSummary = () => {
    // Open AI Assistant with the digital thread prompt context
    const promptText = `Generate a cross-domain closed-loop impact summary and ECR recommendation for part ${activePart} based on the IIoT sensor anomaly, QMS defect DEF-2025-0042, ERP inventory exposure ($34,912 on hand, PO-2025-0812 in transit), and PLM blast radius.`;

    // Dispatch custom event to notify AI Assistant panel if open
    window.dispatchEvent(
      new CustomEvent("open-plm-assistant", {
        detail: { prompt: promptText },
      })
    );

    // Fallback query parameter to ensure panel opens
    const newParams = new URLSearchParams(searchParams);
    newParams.set("assistant", "open");
    setSearchParams(newParams);
  };

  const getDomainBadge = (domain: string) => {
    switch (domain.toUpperCase()) {
      case "IIOT":
        return "bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-300 border-cyan-300 dark:border-cyan-800";
      case "QMS":
        return "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border-purple-300 dark:border-purple-800";
      case "PLM":
        return "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border-blue-300 dark:border-blue-800";
      case "ERP":
        return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-300 dark:border-amber-800";
      default:
        return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300";
    }
  };

  const getSeverityPill = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-500 text-white font-bold animate-pulse";
      case "WARNING":
      case "HIGH":
        return "bg-amber-500 text-white font-semibold";
      default:
        return "bg-blue-500/80 text-white";
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header and Action Button */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <Workflow className="w-6 h-6 text-primary" />
            Digital Thread & Closed-Loop Timeline
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Unified cross-domain asset intelligence correlating IIoT field telemetry, QMS defects, PLM engineering, and ERP inventory.
          </p>
        </div>

        <Button
          onClick={handleGenerateImpactSummary}
          className="gap-2 bg-gradient-to-r from-primary to-indigo-600 hover:from-primary/90 hover:to-indigo-500 text-white shadow-md self-start sm:self-auto"
        >
          <Sparkles className="w-4 h-4 text-amber-300" /> Generate AI Impact Summary
        </Button>
      </div>

      {/* Part Search & Demo Selector */}
      <Card>
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2 max-w-md">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={partInput}
                onChange={(e) => setPartInput(e.target.value)}
                placeholder="Lookup part number (e.g. PMP-0290)..."
                className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg bg-background border border-border font-mono uppercase text-foreground focus:ring-2 focus:ring-primary"
              />
            </div>
            <Button type="submit" size="sm">
              Trace Thread
            </Button>
          </form>

          {/* Seeded Closed-Loop Demo Preset */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground">Demo Story:</span>
            <button
              onClick={() => {
                setPartInput("PMP-0290");
                setActivePart("PMP-0290");
                setSearchParams({ part: "PMP-0290" });
              }}
              className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all border ${activePart === "PMP-0290"
                  ? "bg-primary text-primary-foreground border-primary shadow-xs"
                  : "bg-muted text-foreground hover:bg-muted/80 border-border"
                }`}
            >
              PMP-0290 (Bearing Closed-Loop)
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Cross-Domain Overview Cards */}
      {thread && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* IIoT Field Sensor Card */}
          <Card className="border-cyan-500/30 bg-cyan-50/20 dark:bg-cyan-950/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-cyan-800 dark:text-cyan-300 flex items-center gap-1.5">
                <Radio className="w-4 h-4 text-cyan-600 dark:text-cyan-400" /> IIoT Telemetry
              </CardTitle>
              <Badge variant="destructive">
                {(thread.telemetry_events || []).length} Alarm(s)
              </Badge>
            </CardHeader>
            <CardContent className="space-y-1 text-xs">
              <div className="font-mono font-bold text-base text-foreground">
                {(thread.telemetry_events && thread.telemetry_events[0]?.metric_value) || "12.8"} mm/s RMS
              </div>
              <p className="text-muted-foreground text-[11px]">
                Asset: <strong>{(thread.telemetry_events && thread.telemetry_events[0]?.serial_number) || "SN-APX-2025-001"}</strong>
              </p>
              <div className="text-[11px] text-rose-600 dark:text-rose-400 font-medium">
                Threshold: {(thread.telemetry_events && thread.telemetry_events[0]?.threshold_value) || "4.5"} mm/s exceeded
              </div>
            </CardContent>
          </Card>

          {/* QMS Quality Defect Card */}
          <Card className="border-purple-500/30 bg-purple-50/20 dark:bg-purple-950/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-purple-800 dark:text-purple-300 flex items-center gap-1.5">
                <FileCheck2 className="w-4 h-4 text-purple-600 dark:text-purple-400" /> QMS Non-Conformance
              </CardTitle>
              <Badge variant="outline" className="border-purple-300 text-purple-700 dark:text-purple-300">
                {(thread.defects || []).length} NC Report(s)
              </Badge>
            </CardHeader>
            <CardContent className="space-y-1 text-xs">
              <div className="font-mono font-bold text-base text-purple-800 dark:text-purple-300">
                {(thread.defects && thread.defects[0]?.defect_number) || "DEF-2025-0042"}
              </div>
              <p className="text-muted-foreground text-[11px] truncate">
                {(thread.defects && thread.defects[0]?.title) || "Fatigue spalling on raceway"}
              </p>
              <div className="text-[11px] font-semibold text-foreground">
                Action: {(thread.defects && thread.defects[0]?.containment_action) || "Quarantine and inspect"}
              </div>
            </CardContent>
          </Card>

          {/* PLM Engineering Blast Radius */}
          <Card className="border-blue-500/30 bg-blue-50/20 dark:bg-blue-950/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-blue-800 dark:text-blue-300 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-blue-600 dark:text-blue-400" /> PLM Impact
              </CardTitle>
              <Badge variant="secondary">
                {thread.impact?.impact_level || "HIGH"} Severity
              </Badge>
            </CardHeader>
            <CardContent className="space-y-1 text-xs">
              <div className="font-mono font-bold text-base text-blue-800 dark:text-blue-300">
                {thread.impact?.all_affected_assemblies?.length || 4} Assemblies
              </div>
              <p className="text-muted-foreground text-[11px] truncate">
                Includes ApexFlow 1000 (PMP-0001)
              </p>
              <div className="text-[11px] text-muted-foreground">
                {thread.impact?.associated_documents?.length || 1} CAD Drawings linked
              </div>
            </CardContent>
          </Card>

          {/* ERP Inventory & Procurement Exposure */}
          <Card className="border-amber-500/30 bg-amber-50/20 dark:bg-amber-950/10">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
                <Package className="w-4 h-4 text-amber-600 dark:text-amber-400" /> ERP Supply Chain
              </CardTitle>
              <Badge variant="outline" className="border-amber-300 text-amber-700 dark:text-amber-300">
                {(thread.open_pos || []).length} In-Transit PO
              </Badge>
            </CardHeader>
            <CardContent className="space-y-1 text-xs">
              <div className="font-mono font-bold text-base text-amber-800 dark:text-amber-300">
                ${thread.stock_summary?.total_valuation ? thread.stock_summary.total_valuation.toLocaleString() : "34,912"}
              </div>
              <p className="text-muted-foreground text-[11px]">
                {thread.stock_summary?.total_on_hand ?? 245} units in stock across {thread.stock_summary?.stock_locations?.length || 3} WH
              </p>
              <div className="text-[11px] text-amber-700 dark:text-amber-400 font-medium">
                PO-2025-0812: 500 units in transit
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Unified Chronological Digital Thread Timeline */}
      <Card>
        <CardHeader className="border-b border-border/50 pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <span>Unified Chronological Timeline:</span>
                <span className="font-mono text-primary font-bold">{activePart}</span>
              </CardTitle>
              <CardDescription>
                Closed-loop trail correlating field anomalies, quality root causes, product structure impacts, and supply chain commitments.
              </CardDescription>
            </div>
            <span className="text-xs text-muted-foreground font-mono">
              {thread?.timeline?.length || 0} Cross-Domain Events
            </span>
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-xl" />
              ))}
            </div>
          ) : isError ? (
            <ErrorState
              title={`Digital Thread query failed for ${activePart}`}
              message={(error as Error)?.message}
              onRetry={refetch}
            />
          ) : !thread || (thread.timeline || []).length === 0 ? (
            <EmptyState
              title="No Digital Thread Events"
              description={`No cross-domain events recorded for part '${activePart}'. Try selecting PMP-0290.`}
            />
          ) : (
            <div className="relative border-l-2 border-border/80 ml-4 pl-6 space-y-6">
              {(thread.timeline || []).map((evt, idx) => (
                <div key={evt.id || idx} className="relative group">
                  {/* Timeline Node Dot */}
                  <div className="absolute -left-[31px] top-1.5 w-4 h-4 rounded-full border-2 border-background bg-primary shadow-xs group-hover:scale-125 transition-transform" />

                  {/* Event Card */}
                  <div className="p-4 rounded-xl border border-border bg-card hover:border-primary/40 hover:bg-muted/20 transition-all space-y-2.5">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold border ${getDomainBadge(
                            evt.domain
                          )}`}
                        >
                          {evt.domain}
                        </span>
                        <span className="font-semibold text-sm text-foreground">
                          {evt.title}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] uppercase font-bold ${getSeverityPill(evt.severity || "INFO")}`}>
                          {evt.severity || "INFO"}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          {formatDate(evt.timestamp || "")}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {evt.description}
                    </p>

                    {/* Metadata tags */}
                    {evt.metadata && Object.keys(evt.metadata).length > 0 && (
                      <div className="pt-2 border-t border-border/40 flex flex-wrap gap-2 text-[11px] font-mono text-muted-foreground">
                        {Object.entries(evt.metadata).map(([k, v]) => (
                          <span key={k} className="px-2 py-0.5 rounded bg-muted/60 text-foreground">
                            {k}: <strong>{String(v)}</strong>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

