import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Plus,
  CheckCircle2,
  AlertCircle,
  Clock,
  Send,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";

import { getChangeRequests, draftChangeRequest, confirmChangeRequest } from "@/services/api";
import type { DraftChangeResponse, ConfirmChangeResponse, ChangeRequest } from "@/types/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDate, getPriorityBadgeClass } from "@/lib/utils";

export function ChangeRequestsPage() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const presetPart = searchParams.get("part") || "";

  const [page, setPage] = useState<number>(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const pageSize = 10;

  // Modal and Draft State (Two-Step Safety Gate)
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("");
  const [affectedPartsInput, setAffectedPartsInput] = useState(presetPart || "PMP-0010");
  const [category, setCategory] = useState("DESIGN_IMPROVEMENT");
  const [priority, setPriority] = useState("MEDIUM");

  // Step 1 Draft response preview
  const [pendingDraft, setPendingDraft] = useState<DraftChangeResponse | null>(null);
  // Step 2 Final confirmed response
  const [confirmedResult, setConfirmedResult] = useState<ConfirmChangeResponse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Query committed change requests
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["change-requests", page, statusFilter],
    queryFn: () => getChangeRequests({ page, page_size: pageSize, status: statusFilter || undefined }),
  });

  // Step 1: Draft Mutation (Safe dry-run preview)
  const draftMutation = useMutation({
    mutationFn: draftChangeRequest,
    onSuccess: (data) => {
      setPendingDraft(data);
      setFormError(null);
    },
    onError: (err: any) => {
      setFormError(err?.message || "Failed to draft change request.");
    },
  });

  // Step 2: Confirm Mutation (Explicit commit to PLM database)
  const confirmMutation = useMutation({
    mutationFn: confirmChangeRequest,
    onSuccess: (data) => {
      setConfirmedResult(data);
      setPendingDraft(null);
      // Invalidate list to show new change request
      queryClient.invalidateQueries({ queryKey: ["change-requests"] });
    },
    onError: (err: any) => {
      setFormError(err?.message || "Failed to commit change request.");
    },
  });

  const handleOpenDraftModal = () => {
    setPendingDraft(null);
    setConfirmedResult(null);
    setFormError(null);
    if (presetPart) setAffectedPartsInput(presetPart);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setPendingDraft(null);
    setConfirmedResult(null);
    setFormError(null);
  };

  const handleStep1Submit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const parts = affectedPartsInput
      .split(",")
      .map((p) => p.trim().toUpperCase())
      .filter(Boolean);

    if (parts.length === 0) {
      setFormError("At least one affected part number is required.");
      return;
    }

    draftMutation.mutate({
      title: title.trim(),
      reason: reason.trim(),
      affected_parts: parts,
      category,
      priority,
    });
  };

  const handleStep2Confirm = () => {
    if (!pendingDraft?.draft_id) return;
    confirmMutation.mutate(pendingDraft.draft_id);
  };

  const getStatusBadge = (status?: string | null) => {
    switch ((status || "").toUpperCase()) {
      case "OPEN":
        return "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 border-blue-200 dark:border-blue-800";
      case "UNDER_REVIEW":
        return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-200 dark:border-amber-800";
      case "APPROVED":
        return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800";
      case "RESOLVED":
        return "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border-purple-200 dark:border-purple-800";
      default:
        return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300";
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Engineering Change Requests (ECR)
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Governed change control workflow with mandatory two-step draft verification and safety confirmation.
          </p>
        </div>

        <Button onClick={handleOpenDraftModal} data-testid="open-draft-ecr-button" className="gap-2 self-start sm:self-auto">
          <Plus className="w-4 h-4" /> Propose New ECR
        </Button>
      </div>

      {/* Filter and Overview Bar */}
      <Card>
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-muted-foreground">Status Filter:</span>
            {["", "OPEN", "UNDER_REVIEW", "APPROVED", "RESOLVED"].map((st) => (
              <button
                key={st || "all"}
                onClick={() => {
                  setStatusFilter(st);
                  setPage(1);
                }}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  statusFilter === st
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
                }`}
              >
                {st ? st.replace("_", " ") : "All"}
              </button>
            ))}
          </div>

          <div className="text-xs text-muted-foreground">
            {data && (
              <span>
                Total Records: <strong>{data.total}</strong>
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Change Requests Table */}
      <Card>
        <CardHeader className="pb-3 border-b border-border/50">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Change Register</CardTitle>
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
              <TableSkeleton rows={6} cols={6} />
            </div>
          ) : isError ? (
            <div className="p-6">
              <ErrorState message={(error as Error)?.message} onRetry={refetch} />
            </div>
          ) : data?.items?.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="No Change Requests Found"
                description="No change requests match the current status filter."
                actionText="Propose New ECR"
                onAction={handleOpenDraftModal}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border">
                  <tr>
                    <th className="py-3 px-4">CR Number</th>
                    <th className="py-3 px-4">Title</th>
                    <th className="py-3 px-4">State</th>
                    <th className="py-3 px-4">Priority</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Affected Parts</th>
                    <th className="py-3 px-4">Date Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {data?.items?.map((cr) => (
                    <tr key={cr.cr_number} className="hover:bg-muted/30 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-primary">
                        {cr.cr_number}
                      </td>
                      <td className="py-3 px-4 font-medium text-foreground max-w-sm">
                        <div>{cr.title}</div>
                        <div className="text-xs text-muted-foreground truncate mt-0.5 max-w-xs">
                          {cr.reason}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadge(
                            cr.status
                          )}`}
                        >
                          {cr.status}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-medium border ${getPriorityBadgeClass(
                            cr.priority
                          )}`}
                        >
                          {cr.priority}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs text-muted-foreground font-mono">
                        {cr.category}
                      </td>
                      <td className="py-3 px-4 font-mono text-xs">
                        <div className="flex flex-wrap gap-1 max-w-[200px]">
                          {cr.affected_parts?.map((p) => (
                            <span
                              key={p}
                              className="px-1.5 py-0.5 rounded bg-muted text-foreground"
                            >
                              {p}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-xs text-muted-foreground whitespace-nowrap">
                        {formatDate(cr.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-between p-4 border-t border-border">
              <span className="text-xs text-muted-foreground">
                Showing {((data.page - 1) * pageSize) + 1} to{" "}
                {Math.min(data.page * pageSize, data.total)} of {data.total} requests
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

      {/* Two-Step Draft ECR Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        title={
          confirmedResult
            ? "Change Request Committed"
            : pendingDraft
            ? "Step 2: Review Draft & Confirm Commit"
            : "Step 1: Draft Engineering Change Request"
        }
        description={
          confirmedResult
            ? "Your change request has been recorded into the PLM vault."
            : pendingDraft
            ? "Write Safety Gate Active: This change is NOT yet saved to the database."
            : "Propose modifications or obsolescence directives. All mutations default to draft preview."
        }
      >
        {/* Step 1: Draft Input Form */}
        {!pendingDraft && !confirmedResult && (
          <form onSubmit={handleStep1Submit} className="space-y-4">
            {formError && (
              <div className="p-3 rounded-lg bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <div>
              <label htmlFor="ecr-title" className="text-xs font-semibold text-muted-foreground block mb-1">
                Change Title *
              </label>
              <input
                id="ecr-title"
                data-testid="ecr-title-input"
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Upgrade Casing Material to Duplex 2205"
                className="w-full px-3 py-2 text-sm rounded-lg bg-background border border-border text-foreground focus:ring-2 focus:ring-primary"
              />
            </div>

            <div>
              <label htmlFor="ecr-parts" className="text-xs font-semibold text-muted-foreground block mb-1">
                Affected Part Numbers (comma-separated) *
              </label>
              <input
                id="ecr-parts"
                data-testid="ecr-parts-input"
                type="text"
                required
                value={affectedPartsInput}
                onChange={(e) => setAffectedPartsInput(e.target.value)}
                placeholder="e.g. PMP-0010, PMP-0290"
                className="w-full px-3 py-2 text-sm rounded-lg bg-background border border-border font-mono uppercase text-foreground focus:ring-2 focus:ring-primary"
              />
              <span className="text-[11px] text-muted-foreground block mt-0.5">
                All part numbers will be pre-validated against the active PLM catalog.
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="ecr-cat" className="text-xs font-semibold text-muted-foreground block mb-1">
                  Category
                </label>
                <select
                  id="ecr-cat"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg bg-background border border-border text-foreground focus:ring-2 focus:ring-primary"
                >
                  <option value="DESIGN_IMPROVEMENT">Design Improvement</option>
                  <option value="DEFECT">Defect / Quality Issue</option>
                  <option value="COST_REDUCTION">Cost Reduction</option>
                  <option value="COMPLIANCE">RoHS / Compliance</option>
                </select>
              </div>

              <div>
                <label htmlFor="ecr-priority" className="text-xs font-semibold text-muted-foreground block mb-1">
                  Priority
                </label>
                <select
                  id="ecr-priority"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg bg-background border border-border text-foreground focus:ring-2 focus:ring-primary"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="EMERGENCY">Emergency</option>
                </select>
              </div>
            </div>

            <div>
              <label htmlFor="ecr-reason" className="text-xs font-semibold text-muted-foreground block mb-1">
                Justification / Failure Root Cause *
              </label>
              <textarea
                id="ecr-reason"
                data-testid="ecr-reason-input"
                required
                rows={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Describe failure evidence, customer requirements, or testing reports..."
                className="w-full px-3 py-2 text-sm rounded-lg bg-background border border-border text-foreground focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-border">
              <Button type="button" variant="outline" onClick={handleCloseModal}>
                Cancel
              </Button>
              <Button type="submit" data-testid="submit-draft-button" isLoading={draftMutation.isPending}>
                Generate Draft Preview
              </Button>
            </div>
          </form>
        )}

        {/* Step 2: Draft Preview & Confirm Gate */}
        {pendingDraft && !confirmedResult && (
          <div className="space-y-4">
            <div className="p-3.5 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50/70 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 text-xs">
              <strong>SAFETY PROTOCOL:</strong> You are currently viewing an unpersisted draft (
              <span className="font-mono">{pendingDraft.draft_id}</span>). No state changes have been
              committed to the PLM database. Click <strong>"Confirm & Commit ECR"</strong> below to
              commit.
            </div>

            <div className="space-y-2 text-sm border border-border rounded-lg p-3 bg-muted/20">
              <div className="flex items-center justify-between pb-1 border-b border-border/50">
                <span className="text-xs text-muted-foreground">Draft ID:</span>
                <span className="font-mono font-bold text-primary">{pendingDraft.draft_id}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Title:</span>
                <span className="font-semibold text-foreground">{pendingDraft.title}</span>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Affected Parts:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {pendingDraft.affected_parts.map((p) => (
                    <span
                      key={p}
                      className="font-mono text-xs px-2 py-0.5 rounded bg-primary/10 text-primary font-semibold"
                    >
                      {p}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <span className="text-xs text-muted-foreground block">Justification:</span>
                <p className="text-xs text-muted-foreground mt-0.5">{pendingDraft.reason}</p>
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-border">
              <Button variant="outline" onClick={() => setPendingDraft(null)}>
                Edit Draft
              </Button>
              <Button
                onClick={handleStep2Confirm}
                data-testid="confirm-ecr-button"
                isLoading={confirmMutation.isPending}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2"
              >
                <ShieldCheck className="w-4 h-4" /> Confirm & Commit ECR
              </Button>
            </div>
          </div>
        )}

        {/* Success Confirmation View */}
        {confirmedResult && (
          <div className="space-y-4 text-center py-4">
            <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/80 text-emerald-600 dark:text-emerald-400 mx-auto flex items-center justify-center">
              <CheckCircle2 className="w-7 h-7" />
            </div>

            <div className="space-y-1">
              <h3 className="text-lg font-bold text-foreground">
                Change Request {confirmedResult.cr_number} Committed
              </h3>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                {confirmedResult.message}
              </p>
            </div>

            <div className="p-3 rounded-lg bg-muted/40 font-mono text-xs text-left space-y-1 max-w-sm mx-auto">
              <div>CR Number: <strong>{confirmedResult.cr_number}</strong></div>
              <div>State: <span className="text-emerald-600 font-semibold">{confirmedResult.status}</span></div>
              <div>Affected: {confirmedResult.affected_parts.join(", ")}</div>
            </div>

            <div className="pt-4">
              <Button onClick={handleCloseModal} data-testid="ecr-done-button" className="w-full">
                Done
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
