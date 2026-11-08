import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  Eye,
  Layers,
  Zap,
} from "lucide-react";

import { getParts } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { getLifecycleBadgeClass, formatDate } from "@/lib/utils";

export function PartSearchPage() {
  const navigate = useNavigate();
  const [queryInput, setQueryInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [lifecycleFilter, setLifecycleFilter] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["parts-search", searchQuery, lifecycleFilter, page],
    queryFn: () =>
      getParts({
        query: searchQuery,
        lifecycle_state: lifecycleFilter || undefined,
        page,
        page_size: pageSize,
      }),
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchQuery(queryInput.trim());
    setPage(1);
  };

  const handleFilterChange = (state: string) => {
    setLifecycleFilter(state);
    setPage(1);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Part Catalog Search
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Browse and query engineering components, materials, and assemblies across all lifecycles.
          </p>
        </div>
      </div>

      {/* Search and Filters Bar */}
      <Card>
        <CardContent className="p-4 space-y-4 sm:space-y-0 sm:flex sm:items-center sm:justify-between sm:gap-4">
          <form onSubmit={handleSearchSubmit} className="flex-1 flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="Search by part number (e.g. PMP-0001), name, or material..."
                aria-label="Search parts"
                data-testid="part-search-input"
                className="w-full pl-9 pr-4 py-2 rounded-lg text-sm bg-background border border-border text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <Button type="submit" size="sm" data-testid="part-search-button">
              Search
            </Button>
          </form>

          {/* Lifecycle State Filter Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            <span className="text-xs font-medium text-muted-foreground mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3" /> State:
            </span>
            {["", "RELEASED", "IN_WORK", "UNDER_REVIEW", "OBSOLETE"].map((st) => (
              <button
                key={st || "all"}
                onClick={() => handleFilterChange(st)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors whitespace-nowrap ${
                  lifecycleFilter === st
                    ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                }`}
              >
                {st ? st.replace("_", " ") : "All"}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Parts Table */}
      <Card>
        <CardHeader className="pb-3 border-b border-border/50">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">
              Catalog Items {data && <span className="text-muted-foreground font-normal">({data.total})</span>}
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
              <TableSkeleton rows={8} cols={6} />
            </div>
          ) : isError ? (
            <div className="p-6">
              <ErrorState message={(error as Error)?.message} onRetry={refetch} />
            </div>
          ) : data?.items?.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="No components match your search"
                description="Try loosening your search terms or clearing the lifecycle filter."
                actionText="Clear Filters"
                onAction={() => {
                  setQueryInput("");
                  setSearchQuery("");
                  setLifecycleFilter("");
                }}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                  <tr>
                    <th className="py-3 px-4">Part Number</th>
                    <th className="py-3 px-4">Name</th>
                    <th className="py-3 px-4">Version</th>
                    <th className="py-3 px-4">Lifecycle State</th>
                    <th className="py-3 px-4">Source</th>
                    <th className="py-3 px-4">Material</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {data?.items?.map((part) => (
                    <tr
                      key={part.part_number}
                      className="hover:bg-muted/30 transition-colors group cursor-pointer"
                      onClick={() => navigate(`/parts/${part.part_number}`)}
                    >
                      <td className="py-3 px-4 font-mono font-medium text-primary">
                        <Link
                          to={`/parts/${part.part_number}`}
                          onClick={(e) => e.stopPropagation()}
                          className="hover:underline flex items-center gap-1"
                        >
                          {part.part_number}
                        </Link>
                      </td>
                      <td className="py-3 px-4 font-medium text-foreground max-w-xs truncate">
                        {part.name}
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-muted-foreground">
                        {part.version_label}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${getLifecycleBadgeClass(
                            part.lifecycle_state
                          )}`}
                        >
                          {part.lifecycle_state}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono font-medium ${
                            part.make_buy === "BUY"
                              ? "bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300"
                              : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300"
                          }`}
                        >
                          {part.make_buy}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs text-muted-foreground truncate max-w-[180px]">
                        {part.material || "-"}
                      </td>
                      <td className="py-3 px-4 text-right space-x-1" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="View Details"
                          onClick={() => navigate(`/parts/${part.part_number}`)}
                          className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        >
                          <Eye className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Explore BOM"
                          onClick={() => navigate(`/bom?part=${part.part_number}`)}
                          className="h-8 w-8 text-muted-foreground hover:text-primary"
                        >
                          <Layers className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Analyze Impact"
                          onClick={() => navigate(`/impact?part=${part.part_number}`)}
                          className="h-8 w-8 text-muted-foreground hover:text-amber-500"
                        >
                          <Zap className="w-4 h-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Controls */}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-between p-4 border-t border-border">
              <span className="text-xs text-muted-foreground">
                Showing {((data.page - 1) * pageSize) + 1} to{" "}
                {Math.min(data.page * pageSize, data.total)} of {data.total} components
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={data.page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="w-4 h-4 mr-1" /> Previous
                </Button>
                <span className="text-xs font-medium px-2">
                  {data.page} / {data.total_pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={data.page >= data.total_pages}
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                >
                  Next <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

