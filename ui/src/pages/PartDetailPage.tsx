import React, { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Package,
  Layers,
  Zap,
  FileText,
  Calendar,
  Tag,
  Boxes,
  ExternalLink,
} from "lucide-react";

import { getPart, getPartWhereUsed, getPartBom } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton, TableSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { getLifecycleBadgeClass, formatDate } from "@/lib/utils";

export function PartDetailPage() {
  const { partNumber } = useParams<{ partNumber: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"attributes" | "where-used" | "bom">("attributes");

  const cleanPartNumber = partNumber || "";

  // Query Part Record
  const {
    data: part,
    isLoading: isPartLoading,
    isError: isPartError,
    error: partError,
    refetch: refetchPart,
  } = useQuery({
    queryKey: ["part-detail", cleanPartNumber],
    queryFn: () => getPart(cleanPartNumber),
    enabled: Boolean(cleanPartNumber),
  });

  // Query Where-Used Parents
  const {
    data: whereUsed,
    isLoading: isWhereUsedLoading,
  } = useQuery({
    queryKey: ["part-where-used", cleanPartNumber],
    queryFn: () => getPartWhereUsed(cleanPartNumber, true),
    enabled: Boolean(cleanPartNumber && activeTab === "where-used"),
  });

  // Query Direct Children BOM
  const {
    data: bomLinks,
    isLoading: isBomLoading,
  } = useQuery({
    queryKey: ["part-direct-bom", cleanPartNumber],
    queryFn: () => getPartBom(cleanPartNumber, 1),
    enabled: Boolean(cleanPartNumber && activeTab === "bom"),
  });

  if (isPartLoading) {
    return (
      <div className="space-y-6 animate-in fade-in">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="p-6 space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isPartError || !part) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="sm" onClick={() => navigate("/parts")}>
          <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to Catalog
        </Button>
        <ErrorState
          title={`Part '${cleanPartNumber}' Not Found`}
          message={(partError as Error)?.message || "The requested component does not exist in the PLM catalog."}
          onRetry={refetchPart}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Back button and Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/parts")}
            className="rounded-full"
            aria-label="Back to catalog"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
                {part.part_number}
              </h1>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getLifecycleBadgeClass(
                  part.lifecycle_state
                )}`}
              >
                {part.lifecycle_state}
              </span>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                Rev {part.revision}.{part.iteration}
              </span>
            </div>
            <p className="text-base text-muted-foreground mt-0.5">{part.name}</p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/bom?part=${part.part_number}`)}
          >
            <Layers className="w-4 h-4 mr-1.5 text-primary" /> Explore BOM
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate(`/impact?part=${part.part_number}`)}
          >
            <Zap className="w-4 h-4 mr-1.5 text-amber-500" /> Blast Radius
          </Button>
          <Button
            size="sm"
            onClick={() => navigate(`/changes?part=${part.part_number}`)}
          >
            <FileText className="w-4 h-4 mr-1.5" /> Propose Change
          </Button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="border-b border-border">
        <div className="flex gap-6">
          <button
            onClick={() => setActiveTab("attributes")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "attributes"
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Attributes & Specs
          </button>
          <button
            onClick={() => setActiveTab("where-used")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "where-used"
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Where-Used Tree
          </button>
          <button
            onClick={() => setActiveTab("bom")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "bom"
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            Direct Child BOM
          </button>
        </div>
      </div>

      {/* Tab 1: Attributes & Specs */}
      {activeTab === "attributes" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Info Card */}
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Engineering Specifications</CardTitle>
              <CardDescription>Master metadata and Windchill version attributes</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-xs text-muted-foreground block">Part Number</span>
                  <span className="font-mono font-medium">{part.part_number}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">Version / Iteration</span>
                  <span className="font-mono">{part.version_label}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">Source Designation</span>
                  <span className="font-medium">{part.make_buy}</span>
                </div>
                <div>
                  <span className="text-xs text-muted-foreground block">Primary Material</span>
                  <span className="font-medium">{part.material || "Unspecified"}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-border/50">
                <span className="text-xs text-muted-foreground block mb-1">Description</span>
                <p className="text-sm text-foreground bg-muted/40 p-3 rounded-lg leading-relaxed">
                  {part.description || "No technical description provided in vault."}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Audit & Lifecycle Timeline Card */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Audit Trail</CardTitle>
              <CardDescription>Revision timestamps and vault history</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="flex items-start gap-3">
                <Calendar className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                <div>
                  <span className="text-xs text-muted-foreground block">Created Timestamp</span>
                  <span>{formatDate(part.created_at)}</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Calendar className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                <div>
                  <span className="text-xs text-muted-foreground block">Last Modified</span>
                  <span>{formatDate(part.updated_at)}</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Tag className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                <div>
                  <span className="text-xs text-muted-foreground block">Version ID</span>
                  <span className="font-mono text-xs">{part.revision}.{part.iteration}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tab 2: Where-Used */}
      {activeTab === "where-used" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Where-Used Traversal</CardTitle>
            <CardDescription>
              Parent and ancestor assemblies that consume {part.part_number} in their indented product structures
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {isWhereUsedLoading ? (
              <div className="p-6">
                <TableSkeleton rows={4} cols={5} />
              </div>
            ) : !whereUsed || whereUsed.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  title="No consuming assemblies"
                  description="This component is currently not referenced as a child item in any active BOM."
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                    <tr>
                      <th className="py-3 px-4">Level</th>
                      <th className="py-3 px-4">Parent Part Number</th>
                      <th className="py-3 px-4">Parent Name</th>
                      <th className="py-3 px-4">State</th>
                      <th className="py-3 px-4">Usage Qty</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {whereUsed.map((row, idx) => (
                      <tr key={idx} className="hover:bg-muted/30 transition-colors">
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-xs font-mono bg-muted">
                            L{row.level}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono font-medium text-primary">
                          <Link to={`/parts/${row.parent_part_number}`} className="hover:underline">
                            {row.parent_part_number}
                          </Link>
                        </td>
                        <td className="py-3 px-4 font-medium">{row.parent_name}</td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${getLifecycleBadgeClass(
                              row.parent_lifecycle_state
                            )}`}
                          >
                            {row.parent_lifecycle_state}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono">
                          {row.quantity} {row.unit}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/bom?part=${row.parent_part_number}`)}
                          >
                            View BOM <ExternalLink className="w-3.5 h-3.5 ml-1" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tab 3: Direct Child BOM */}
      {activeTab === "bom" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">Direct Usage Links (Level 1)</CardTitle>
                <CardDescription>Components directly assembled into {part.part_number}</CardDescription>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => navigate(`/bom?part=${part.part_number}`)}
              >
                Open Full Interactive Explorer <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {isBomLoading ? (
              <div className="p-6">
                <TableSkeleton rows={4} cols={5} />
              </div>
            ) : !bomLinks || bomLinks.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  title="Leaf component"
                  description="This item is a leaf component and contains no sub-assemblies or child parts."
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                    <tr>
                      <th className="py-3 px-4">Find #</th>
                      <th className="py-3 px-4">Child Part Number</th>
                      <th className="py-3 px-4">Component Name</th>
                      <th className="py-3 px-4">Quantity</th>
                      <th className="py-3 px-4">Unit</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {bomLinks.map((link, idx) => (
                      <tr key={idx} className="hover:bg-muted/30 transition-colors">
                        <td className="py-3 px-4 font-mono text-muted-foreground">
                          {link.find_number || (idx + 1) * 10}
                        </td>
                        <td className="py-3 px-4 font-mono font-medium text-primary">
                          <Link to={`/parts/${link.child_part_number}`} className="hover:underline">
                            {link.child_part_number}
                          </Link>
                        </td>
                        <td className="py-3 px-4 font-medium">{link.child_name || "-"}</td>
                        <td className="py-3 px-4 font-mono font-semibold">{link.quantity}</td>
                        <td className="py-3 px-4 text-muted-foreground">{link.unit || "ea"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

