import React, { useState, useEffect, useCallback } from "react";
import {
  Activity,
  Server,
  Database,
  Cpu,
  Clock,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  Copy,
  Check,
  ShieldCheck,
  Zap,
  ArrowUpRight,
  Trash2,
  Bug,
  Globe,
  Radio,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { getSystemHealth, type SystemHealthResponse } from "@/services/api";
import {
  telemetry,
  simulateClientError,
  getActiveSessionTraceId,
  type ApiMetric,
  type ErrorLogEvent,
  type PagePerformanceMetrics,
} from "@/lib/telemetry";

export function SystemHealthPage() {
  const [healthData, setHealthData] = useState<SystemHealthResponse | null>(null);
  const [isPinging, setIsPinging] = useState<boolean>(false);
  const [pingLatency, setPingLatency] = useState<number | null>(null);
  const [lastPingTime, setLastPingTime] = useState<string | null>(null);
  const [pingError, setPingError] = useState<string | null>(null);

  // Client telemetry states
  const [apiMetrics, setApiMetrics] = useState<ApiMetric[]>(() => telemetry.getApiMetrics());
  const [errorEvents, setErrorEvents] = useState<ErrorLogEvent[]>(() => telemetry.getErrorEvents());
  const [pagePerf, setPagePerf] = useState<PagePerformanceMetrics | null>(() => telemetry.getPagePerformance());
  const [copiedTraceId, setCopiedTraceId] = useState<string | null>(null);
  const [expandedErrorId, setExpandedErrorId] = useState<string | null>(null);

  // Subscribe to telemetry store updates
  useEffect(() => {
    const unsubscribe = telemetry.subscribe(() => {
      setApiMetrics(telemetry.getApiMetrics());
      setErrorEvents(telemetry.getErrorEvents());
      setPagePerf(telemetry.getPagePerformance());
    });
    return unsubscribe;
  }, []);

  // Ping API function
  const runPing = useCallback(async () => {
    setIsPinging(true);
    setPingError(null);
    const start = performance.now();
    try {
      const data = await getSystemHealth();
      const latency = Math.round(performance.now() - start);
      setHealthData(data);
      setPingLatency(latency);
      setLastPingTime(new Date().toLocaleTimeString());
    } catch (err: any) {
      setPingError(err?.message || "Failed to reach backend API");
      setPingLatency(Math.round(performance.now() - start));
    } finally {
      setIsPinging(false);
    }
  }, []);

  // Initial ping on mount
  useEffect(() => {
    runPing();
  }, [runPing]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedTraceId(id);
    setTimeout(() => setCopiedTraceId(null), 2000);
  };

  const handleSimulateError = () => {
    simulateClientError(
      `Simulated frontend exception triggered at ${new Date().toLocaleTimeString()} for verification`
    );
  };

  const activeTraceId = getActiveSessionTraceId();
  const summary = telemetry.getSummaryStats();
  const isHealthy = !pingError && healthData?.status === "healthy";

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-border">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Activity className="w-6 h-6 text-primary" />
            System Health & Observability
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time status, W3C distributed trace context propagation, and frontend performance metrics.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={runPing}
            disabled={isPinging}
            className="flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isPinging ? "animate-spin" : ""}`} />
            {isPinging ? "Pinging..." : "Ping API"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleSimulateError}
            className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 border-amber-300 dark:border-amber-800 hover:bg-amber-50 dark:hover:bg-amber-950/30"
          >
            <Bug className="w-3.5 h-3.5" />
            Simulate Error
          </Button>
        </div>
      </div>

      {/* Status Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Active Backend */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center justify-between">
              <span>Backend Engine</span>
              <Database className="w-4 h-4 text-blue-500" />
            </CardDescription>
            <CardTitle className="text-xl font-bold flex items-center gap-2">
              {healthData?.backend === "windchill" ? (
                <>
                  <Server className="w-5 h-5 text-emerald-500" />
                  <span>Windchill</span>
                </>
              ) : (
                <>
                  <Database className="w-5 h-5 text-blue-500" />
                  <span>Mock (SQLite)</span>
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1">
            <div className="flex items-center justify-between">
              <span>Mode:</span>
              <Badge variant={healthData?.backend === "windchill" ? "released" : "inwork"}>
                {healthData?.backend === "windchill" ? "PTC REST / OData" : "Local Mock Engine"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>API Version:</span>
              <span className="font-mono text-foreground">{healthData?.version || "v1.0.0"}</span>
            </div>
          </CardContent>
        </Card>

        {/* Card 2: API Status & Latency */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center justify-between">
              <span>API Probe Status</span>
              <Radio className="w-4 h-4 text-emerald-500" />
            </CardDescription>
            <CardTitle className="text-xl font-bold flex items-center gap-2">
              {isHealthy ? (
                <>
                  <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                  <span className="text-emerald-600 dark:text-emerald-400">Healthy</span>
                </>
              ) : (
                <>
                  <AlertCircle className="w-5 h-5 text-rose-500" />
                  <span className="text-rose-600 dark:text-rose-400">Degraded</span>
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1">
            <div className="flex items-center justify-between">
              <span>Ping Latency:</span>
              <span className="font-mono font-semibold text-foreground">
                {pingLatency !== null ? `${pingLatency} ms` : "Measuring..."}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span>Last Checked:</span>
              <span>{lastPingTime || "Just now"}</span>
            </div>
          </CardContent>
        </Card>

        {/* Card 3: Client Page Performance */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center justify-between">
              <span>Page Performance</span>
              <Clock className="w-4 h-4 text-purple-500" />
            </CardDescription>
            <CardTitle className="text-xl font-bold text-foreground">
              {pagePerf ? `${pagePerf.pageLoadMs} ms` : "Observing..."}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1">
            <div className="flex items-center justify-between">
              <span>DOM Ready:</span>
              <span className="font-mono text-foreground">{pagePerf?.domContentLoadedMs ?? 0} ms</span>
            </div>
            <div className="flex items-center justify-between">
              <span>TTFB:</span>
              <span className="font-mono text-foreground">{pagePerf?.ttfbMs ?? 0} ms</span>
            </div>
          </CardContent>
        </Card>

        {/* Card 4: Request Telemetry Summary */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center justify-between">
              <span>API Observability</span>
              <Cpu className="w-4 h-4 text-amber-500" />
            </CardDescription>
            <CardTitle className="text-xl font-bold text-foreground">
              {summary.totalRequests} <span className="text-xs font-normal text-muted-foreground">requests</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1">
            <div className="flex items-center justify-between">
              <span>Avg Latency:</span>
              <span className="font-mono font-semibold text-foreground">{summary.avgLatency} ms</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Client Errors:</span>
              <span className={`font-mono font-semibold ${summary.errorCount > 0 ? "text-rose-500" : "text-emerald-500"}`}>
                {summary.errorCount}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* W3C Distributed Tracing Banner */}
      <Card className="bg-gradient-to-r from-blue-500/5 via-indigo-500/5 to-purple-500/5 border-primary/20">
        <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-primary" />
              <span className="text-sm font-semibold text-foreground">W3C Distributed Trace Context Active</span>
              <Badge variant="outline" className="text-[10px] bg-background">
                Traceparent Propagated
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground max-w-2xl">
              All browser API calls inject standard W3C <code className="text-primary font-mono text-[11px]">traceparent: 00-&#123;trace_id&#125;-&#123;span_id&#125;-01</code> and{" "}
              <code className="text-primary font-mono text-[11px]">X-Request-ID</code> headers. Frontend user interactions link seamlessly to FastAPI backend spans in Grafana Tempo.
            </p>
          </div>
          <div className="flex items-center gap-2 bg-background/80 px-3 py-1.5 rounded-lg border border-border shrink-0">
            <span className="text-xs text-muted-foreground">Session Trace ID:</span>
            <span className="font-mono text-xs font-medium text-foreground max-w-[120px] sm:max-w-none truncate">
              {activeTraceId}
            </span>
            <button
              onClick={() => handleCopy(activeTraceId, "session-trace")}
              title="Copy Trace ID"
              className="text-muted-foreground hover:text-foreground p-1 transition-colors"
            >
              {copiedTraceId === "session-trace" ? (
                <Check className="w-3.5 h-3.5 text-emerald-500" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Recent Client Errors Section */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <div className="flex items-center gap-2">
              <CardTitle className="text-base font-semibold">Captured Client Errors</CardTitle>
              {errorEvents.length > 0 && (
                <Badge variant="destructive" className="text-[11px]">
                  {errorEvents.length}
                </Badge>
              )}
            </div>
            <CardDescription className="text-xs">
              Automatic capture of unhandled window errors, promise rejections, and failed API queries.
            </CardDescription>
          </div>
          {errorEvents.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => telemetry.clearErrors()}
              className="text-xs text-muted-foreground hover:text-destructive flex items-center gap-1"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Clear Log
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {errorEvents.length === 0 ? (
            <div className="text-center py-8 border border-dashed border-border rounded-lg bg-muted/20">
              <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              <p className="text-sm font-medium text-foreground">No Client Errors Detected</p>
              <p className="text-xs text-muted-foreground mt-1">
                Unhandled runtime exceptions and network errors will be recorded here automatically.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border text-muted-foreground bg-muted/30">
                    <th className="py-2.5 px-3 font-medium">Timestamp</th>
                    <th className="py-2.5 px-3 font-medium">Source / Type</th>
                    <th className="py-2.5 px-3 font-medium">Message</th>
                    <th className="py-2.5 px-3 font-medium">Trace ID</th>
                    <th className="py-2.5 px-3 font-medium text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {errorEvents.slice(0, 10).map((err) => (
                    <React.Fragment key={err.id}>
                      <tr className="hover:bg-muted/30 transition-colors">
                        <td className="py-2.5 px-3 font-mono text-muted-foreground whitespace-nowrap">
                          {new Date(err.timestamp).toLocaleTimeString()}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 font-mono text-[11px]">
                            {err.source}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-medium text-foreground max-w-md truncate">
                          {err.message}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-muted-foreground">
                          {err.traceId ? (
                            <span className="flex items-center gap-1">
                              <span>{err.traceId.substring(0, 12)}...</span>
                              <button
                                onClick={() => handleCopy(err.traceId!, err.id)}
                                title="Copy full Trace ID"
                                className="hover:text-foreground"
                              >
                                {copiedTraceId === err.id ? (
                                  <Check className="w-3 h-3 text-emerald-500" />
                                ) : (
                                  <Copy className="w-3 h-3" />
                                )}
                              </button>
                            </span>
                          ) : (
                            <span className="text-muted-foreground/50">N/A</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          {err.stack ? (
                            <button
                              onClick={() => setExpandedErrorId(expandedErrorId === err.id ? null : err.id)}
                              className="text-primary hover:underline text-[11px]"
                            >
                              {expandedErrorId === err.id ? "Hide Stack" : "View Stack"}
                            </button>
                          ) : (
                            <span className="text-muted-foreground/40">—</span>
                          )}
                        </td>
                      </tr>
                      {expandedErrorId === err.id && err.stack && (
                        <tr className="bg-muted/50">
                          <td colSpan={5} className="p-3">
                            <pre className="text-[11px] font-mono text-muted-foreground overflow-x-auto p-2 bg-card rounded border border-border">
                              {err.stack}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent API Invocations Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center justify-between">
            <span>Recent API Requests & Latency</span>
            <span className="text-xs font-normal text-muted-foreground">
              Showing last {Math.min(apiMetrics.length, 15)} requests
            </span>
          </CardTitle>
          <CardDescription className="text-xs">
            Live log of HTTP requests dispatched with injected W3C traceparent headers.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {apiMetrics.length === 0 ? (
            <div className="text-center py-6 text-muted-foreground text-xs">
              No network requests recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border text-muted-foreground bg-muted/30">
                    <th className="py-2.5 px-3 font-medium">Method</th>
                    <th className="py-2.5 px-3 font-medium">Endpoint</th>
                    <th className="py-2.5 px-3 font-medium">Status</th>
                    <th className="py-2.5 px-3 font-medium">Duration</th>
                    <th className="py-2.5 px-3 font-medium">W3C Traceparent</th>
                    <th className="py-2.5 px-3 font-medium text-right">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {apiMetrics.slice(0, 15).map((m) => {
                    const isSuccess = m.status >= 200 && m.status < 300;
                    return (
                      <tr key={m.id} className="hover:bg-muted/30 transition-colors">
                        <td className="py-2.5 px-3 font-semibold">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                              m.method === "GET"
                                ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                                : m.method === "POST"
                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                : "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300"
                            }`}
                          >
                            {m.method}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-foreground">{m.endpoint}</td>
                        <td className="py-2.5 px-3">
                          <Badge variant={isSuccess ? "released" : "destructive"}>
                            {m.status > 0 ? `${m.status} ${isSuccess ? "OK" : "Error"}` : "Network Error"}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 font-mono">
                          <span
                            className={
                              m.durationMs > 500
                                ? "text-amber-500 font-semibold"
                                : m.durationMs > 1000
                                ? "text-rose-500 font-semibold"
                                : "text-muted-foreground"
                            }
                          >
                            {m.durationMs} ms
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <span className="truncate max-w-[150px]">{m.traceparent}</span>
                            <button
                              onClick={() => handleCopy(m.traceparent, m.id)}
                              title="Copy W3C Traceparent Header"
                              className="hover:text-foreground"
                            >
                              {copiedTraceId === m.id ? (
                                <Check className="w-3 h-3 text-emerald-500" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono text-muted-foreground text-right whitespace-nowrap">
                          {new Date(m.timestamp).toLocaleTimeString()}
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

      {/* Privacy Notice Banner */}
      <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/40 border border-border text-xs text-muted-foreground">
        <ShieldCheck className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-foreground">Strict Privacy & Zero PII Guarantee: </span>
          Client-side observability is configured strictly to exclude all sensitive information. Auth tokens, passwords, user emails, and CAD payload contents are automatically scrubbed and redacted before telemetry is recorded.
        </div>
      </div>
    </div>
  );
}

