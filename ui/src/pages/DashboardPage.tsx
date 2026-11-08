import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Package,
  CheckCircle2,
  Clock,
  AlertOctagon,
  Copy,
  AlertTriangle,
  HelpCircle,
  Shuffle,
  ShieldAlert,
  ArrowRight,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  Legend,
} from "recharts";

import { getParts, getIssuesSummary } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";

export function DashboardPage() {
  const navigate = useNavigate();

  // Query parts counts across states
  const {
    data: allPartsData,
    isLoading: isPartsLoading,
    isError: isPartsError,
    error: partsError,
    refetch: refetchParts,
  } = useQuery({
    queryKey: ["dashboard-parts-summary"],
    queryFn: () => getParts({ page: 1, page_size: 1 }),
  });

  const { data: releasedData, isLoading: isRelLoading } = useQuery({
    queryKey: ["parts-count-released"],
    queryFn: () => getParts({ lifecycle_state: "RELEASED", page: 1, page_size: 1 }),
  });

  const { data: inWorkData, isLoading: isInWorkLoading } = useQuery({
    queryKey: ["parts-count-inwork"],
    queryFn: () => getParts({ lifecycle_state: "IN_WORK", page: 1, page_size: 1 }),
  });

  const { data: underReviewData, isLoading: isReviewLoading } = useQuery({
    queryKey: ["parts-count-under-review"],
    queryFn: () => getParts({ lifecycle_state: "UNDER_REVIEW", page: 1, page_size: 1 }),
  });

  const { data: obsoleteData, isLoading: isObsLoading } = useQuery({
    queryKey: ["parts-count-obsolete"],
    queryFn: () => getParts({ lifecycle_state: "OBSOLETE", page: 1, page_size: 1 }),
  });

  // Query planted issues summary
  const {
    data: issuesSummary,
    isLoading: isIssuesLoading,
    isError: isIssuesError,
    error: issuesError,
    refetch: refetchIssues,
  } = useQuery({
    queryKey: ["issues-summary"],
    queryFn: getIssuesSummary,
  });

  const isStatsLoading =
    isPartsLoading || isRelLoading || isInWorkLoading || isReviewLoading || isObsLoading;

  if (isPartsError || isIssuesError) {
    return (
      <ErrorState
        title="Error loading dashboard data"
        message={(partsError as Error)?.message || (issuesError as Error)?.message}
        onRetry={() => {
          refetchParts();
          refetchIssues();
        }}
      />
    );
  }

  // Distribution chart data with strict required colors:
  // In Work (blue), Under Review (amber), Released (green), Obsolete (red)
  const chartData = [
    {
      name: "In Work",
      value: inWorkData?.total || 0,
      color: "#2563eb", // blue
    },
    {
      name: "Under Review",
      value: underReviewData?.total || 0,
      color: "#d97706", // amber
    },
    {
      name: "Released",
      value: releasedData?.total || 0,
      color: "#16a34a", // green
    },
    {
      name: "Obsolete",
      value: obsoleteData?.total || 0,
      color: "#dc2626", // red
    },
  ];

  const plantedIssues = [
    {
      key: "duplicates",
      title: "Duplicate / Redundant Parts",
      description: "Parts sharing identical technical specifications and materials",
      count: issuesSummary?.duplicates ?? 0,
      icon: Copy,
      color: "text-amber-600 dark:text-amber-400",
      bgColor: "bg-amber-100 dark:bg-amber-950/60",
    },
    {
      key: "obsolete_in_released",
      title: "Obsolete Parts in Released BOMs",
      description: "Critical compliance violation: active assemblies containing dead stock",
      count: issuesSummary?.obsolete_in_released ?? 0,
      icon: AlertTriangle,
      color: "text-red-600 dark:text-red-400",
      bgColor: "bg-red-100 dark:bg-red-950/60",
    },
    {
      key: "unassigned_buy",
      title: "Unassigned BUY Components",
      description: "Purchased components lacking approved AML manufacturer sources",
      count: issuesSummary?.unassigned_buy ?? 0,
      icon: HelpCircle,
      color: "text-orange-600 dark:text-orange-400",
      bgColor: "bg-orange-100 dark:bg-orange-950/60",
    },
    {
      key: "ebom_mbom_mismatches",
      title: "EBOM vs. MBOM Discrepancies",
      description: "Engineering design quantities diverging from Manufacturing assembly",
      count: issuesSummary?.ebom_mbom_mismatches ?? 0,
      icon: Shuffle,
      color: "text-purple-600 dark:text-purple-400",
      bgColor: "bg-purple-100 dark:bg-purple-950/60",
    },
    {
      key: "rohs_risks",
      title: "RoHS Material Compliance Violations",
      description: "Components containing prohibited hazardous heavy metals (Pb, Cd, Hg)",
      count: issuesSummary?.rohs_risks ?? 0,
      icon: ShieldAlert,
      color: "text-rose-600 dark:text-rose-400",
      bgColor: "bg-rose-100 dark:bg-rose-950/60",
    },
  ];

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Engineering Governance Dashboard
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Real-time visibility into component lifecycles, product structures, and catalog health.
        </p>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Parts */}
        <Card className="hover:border-primary/50 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Parts</CardTitle>
            <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400">
              <Package className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            {isStatsLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="text-2xl font-bold">{allPartsData?.total.toLocaleString()}</div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Active pump catalog items</p>
          </CardContent>
        </Card>

        {/* Released Parts */}
        <Card className="hover:border-emerald-500/50 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Released</CardTitle>
            <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            {isStatsLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {releasedData?.total.toLocaleString()}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Production-ready baselines</p>
          </CardContent>
        </Card>

        {/* In Work Parts */}
        <Card className="hover:border-blue-500/50 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">In Work</CardTitle>
            <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400">
              <Clock className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            {isStatsLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {inWorkData?.total.toLocaleString()}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Active engineering design</p>
          </CardContent>
        </Card>

        {/* Obsolete Parts */}
        <Card className="hover:border-rose-500/50 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Obsolete</CardTitle>
            <div className="p-2 rounded-lg bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400">
              <AlertOctagon className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            {isStatsLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div className="text-2xl font-bold text-rose-600 dark:text-rose-400">
                {obsoleteData?.total.toLocaleString()}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Deprecated components</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Lifecycle Distribution & Planted Issues */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Lifecycle Distribution Chart */}
        <div className="lg:col-span-5">
          <Card className="h-full flex flex-col">
            <CardHeader>
              <CardTitle>Lifecycle State Distribution</CardTitle>
              <CardDescription>Breakdown of all component revisions across lifecycle phases</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col items-center justify-center min-h-[300px]">
              {isStatsLoading ? (
                <Skeleton className="h-56 w-56 rounded-full" />
              ) : (
                <div className="w-full h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={chartData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={85}
                        paddingAngle={4}
                        dataKey="value"
                      >
                        {chartData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip
                        formatter={(val: number) => [`${val} parts`, "Count"]}
                        contentStyle={{
                          backgroundColor: "hsl(var(--card))",
                          borderColor: "hsl(var(--border))",
                          borderRadius: "0.5rem",
                          color: "hsl(var(--foreground))",
                        }}
                      />
                      <Legend verticalAlign="bottom" height={36} iconType="circle" />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Planted Data Health Issues Panel */}
        <div className="lg:col-span-7">
          <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle className="flex items-center gap-2">
                  Catalog Health Diagnostics
                  {issuesSummary && (
                    <Badge variant="destructive" className="ml-2">
                      {issuesSummary.total_issues} Detected
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  Automated PLM integrity scans. Click any issue to view affected parts and parent BOMs.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {isIssuesLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full rounded-lg" />
                  ))}
                </div>
              ) : (
                plantedIssues.map((issue) => {
                  const Icon = issue.icon;
                  return (
                    <div
                      key={issue.key}
                      onClick={() => navigate(`/issues?type=${issue.key}`)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") navigate(`/issues?type=${issue.key}`);
                      }}
                      className="group flex items-center justify-between p-3.5 rounded-lg border border-border bg-card hover:bg-muted/50 hover:border-primary/40 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <div className="flex items-center gap-3.5">
                        <div className={`p-2.5 rounded-lg ${issue.bgColor} ${issue.color}`}>
                          <Icon className="w-5 h-5 shrink-0" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                              {issue.title}
                            </h4>
                            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-muted text-foreground">
                              {issue.count}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5">{issue.description}</p>
                        </div>
                      </div>
                      <div className="text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all">
                        <ArrowRight className="w-4 h-4" />
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

