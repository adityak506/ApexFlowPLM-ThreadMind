/**
 * Frontend Observability & OpenTelemetry Client Module
 *
 * Implements lightweight client telemetry adhering to W3C Trace Context standards:
 * - Generates 32-hex trace IDs and 16-hex span IDs.
 * - Formats and propagates standard W3C `traceparent` headers (`00-${traceId}-${spanId}-01`).
 * - Captures navigation timing (page load time, TTFB, DNS, DOMContentLoaded).
 * - Tracks API call durations, HTTP status codes, and trace context.
 * - Captures unhandled runtime errors (`window.onerror`, `unhandledrejection`).
 * - Strictly strips all Personal Identifiable Information (PII) and credentials.
 * - Provides reactive event subscriptions for the System Health dashboard.
 * - Zero-risk fallback: telemetry failures will never break user actions.
 */

export interface ApiMetric {
  id: string;
  timestamp: string;
  method: string;
  endpoint: string;
  status: number;
  durationMs: number;
  traceId: string;
  spanId: string;
  traceparent: string;
  ok: boolean;
  error?: string;
}

export interface ErrorLogEvent {
  id: string;
  timestamp: string;
  message: string;
  source: string;
  stack?: string;
  traceId?: string;
}

export interface PagePerformanceMetrics {
  pageLoadMs: number;
  domContentLoadedMs: number;
  ttfbMs: number;
  dnsMs: number;
  tcpMs: number;
  recordedAt: string;
}

// ============================================================================
// W3C Trace Context Utilities
// ============================================================================

/**
 * Generate a random 32-character hex string representing a 128-bit W3C Trace ID.
 */
export function generateTraceId(): string {
  try {
    const bytes = new Uint8Array(16);
    if (typeof crypto !== "undefined" && crypto.getRandomValues) {
      crypto.getRandomValues(bytes);
    } else {
      for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return Math.random().toString(16).substring(2).padEnd(32, "0").substring(0, 32);
  }
}

/**
 * Generate a random 16-character hex string representing a 64-bit W3C Span ID.
 */
export function generateSpanId(): string {
  try {
    const bytes = new Uint8Array(8);
    if (typeof crypto !== "undefined" && crypto.getRandomValues) {
      crypto.getRandomValues(bytes);
    } else {
      for (let i = 0; i < 8; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return Math.random().toString(16).substring(2).padEnd(16, "0").substring(0, 16);
  }
}

/**
 * Format a W3C traceparent header: `00-${traceId}-${spanId}-01`.
 */
export function formatTraceParent(traceId: string, spanId: string): string {
  return `00-${traceId}-${spanId}-01`;
}

// Current active session trace ID
let activeSessionTraceId = generateTraceId();

export function getActiveSessionTraceId(): string {
  return activeSessionTraceId;
}

export function rotateSessionTraceId(): string {
  activeSessionTraceId = generateTraceId();
  return activeSessionTraceId;
}

// ============================================================================
// Privacy & PII Scrubbing
// ============================================================================

const SENSITIVE_QUERY_REGEX = /([?&])(password|token|secret|key|auth|api_key|credential|email|card)=([^&#]*)/gi;
const BEARER_REGEX = /Bearer\s+[\w-._~+/]+=*/gi;
const EMAIL_REGEX = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g;

/**
 * Clean URLs and strings to prevent leaking user credentials, tokens, or PII.
 */
export function sanitizeTelemetryString(input: string): string {
  if (!input) return "";
  return input
    .replace(SENSITIVE_QUERY_REGEX, "$1$2=[REDACTED]")
    .replace(BEARER_REGEX, "Bearer [REDACTED]")
    .replace(EMAIL_REGEX, "[EMAIL_REDACTED]");
}

// ============================================================================
// Telemetry Store & Event Bus
// ============================================================================

const MAX_STORED_METRICS = 50;
const MAX_STORED_ERRORS = 50;

class TelemetryStore {
  private apiMetrics: ApiMetric[] = [];
  private errorEvents: ErrorLogEvent[] = [];
  private pagePerformance: PagePerformanceMetrics | null = null;
  private listeners: Set<() => void> = new Set();
  private initialized = false;

  public subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    this.listeners.forEach((fn) => {
      try {
        fn();
      } catch (err) {
        console.warn("[Telemetry] Listener failed:", err);
      }
    });
  }

  public recordApiMetric(metric: Omit<ApiMetric, "id">): void {
    const entry: ApiMetric = {
      ...metric,
      id: generateSpanId(),
      endpoint: sanitizeTelemetryString(metric.endpoint),
      error: metric.error ? sanitizeTelemetryString(metric.error) : undefined,
    };
    this.apiMetrics.unshift(entry);
    if (this.apiMetrics.length > MAX_STORED_METRICS) {
      this.apiMetrics.pop();
    }
    this.notify();
  }

  public recordError(event: Omit<ErrorLogEvent, "id">): void {
    const entry: ErrorLogEvent = {
      ...event,
      id: generateSpanId(),
      message: sanitizeTelemetryString(event.message),
      source: sanitizeTelemetryString(event.source),
      stack: event.stack ? sanitizeTelemetryString(event.stack) : undefined,
    };
    this.errorEvents.unshift(entry);
    if (this.errorEvents.length > MAX_STORED_ERRORS) {
      this.errorEvents.pop();
    }
    this.notify();
  }

  public clearErrors(): void {
    this.errorEvents = [];
    this.notify();
  }

  public setPagePerformance(perf: PagePerformanceMetrics): void {
    this.pagePerformance = perf;
    this.notify();
  }

  public getApiMetrics(): ApiMetric[] {
    return [...this.apiMetrics];
  }

  public getErrorEvents(): ErrorLogEvent[] {
    return [...this.errorEvents];
  }

  public getPagePerformance(): PagePerformanceMetrics | null {
    return this.pagePerformance;
  }

  public getSummaryStats() {
    const totalRequests = this.apiMetrics.length;
    const avgLatency =
      totalRequests > 0
        ? Math.round(this.apiMetrics.reduce((acc, m) => acc + m.durationMs, 0) / totalRequests)
        : 0;
    const failedRequests = this.apiMetrics.filter((m) => !m.ok).length;
    const errorCount = this.errorEvents.length;

    return {
      totalRequests,
      avgLatency,
      failedRequests,
      errorCount,
    };
  }

  public init(): void {
    if (this.initialized || typeof window === "undefined") return;
    this.initialized = true;

    // 1. Measure Navigation Timing
    const recordTiming = () => {
      try {
        const navEntries = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
        if (navEntries && navEntries.length > 0) {
          const nav = navEntries[0];
          const dnsMs = Math.round(nav.domainLookupEnd - nav.domainLookupStart);
          const tcpMs = Math.round(nav.connectEnd - nav.connectStart);
          const ttfbMs = Math.round(nav.responseStart - nav.requestStart);
          const domContentLoadedMs = Math.round(nav.domContentLoadedEventEnd - nav.startTime);
          const pageLoadMs = Math.round(nav.loadEventEnd - nav.startTime);

          this.setPagePerformance({
            pageLoadMs: pageLoadMs > 0 ? pageLoadMs : Math.round(performance.now()),
            domContentLoadedMs: domContentLoadedMs > 0 ? domContentLoadedMs : 0,
            ttfbMs: ttfbMs > 0 ? ttfbMs : 0,
            dnsMs: dnsMs > 0 ? dnsMs : 0,
            tcpMs: tcpMs > 0 ? tcpMs : 0,
            recordedAt: new Date().toISOString(),
          });
        } else if (performance.timing) {
          const t = performance.timing;
          const pageLoadMs = Math.max(0, t.loadEventEnd - t.navigationStart);
          const domContentLoadedMs = Math.max(0, t.domContentLoadedEventEnd - t.navigationStart);
          const ttfbMs = Math.max(0, t.responseStart - t.requestStart);
          this.setPagePerformance({
            pageLoadMs: pageLoadMs || Math.round(performance.now()),
            domContentLoadedMs,
            ttfbMs,
            dnsMs: Math.max(0, t.domainLookupEnd - t.domainLookupStart),
            tcpMs: Math.max(0, t.connectEnd - t.connectStart),
            recordedAt: new Date().toISOString(),
          });
        }
      } catch (err) {
        console.warn("[Telemetry] Failed to collect navigation timing:", err);
      }
    };

    if (document.readyState === "complete") {
      setTimeout(recordTiming, 100);
    } else {
      window.addEventListener("load", () => setTimeout(recordTiming, 100));
    }

    // 2. Capture Unhandled Window Errors
    window.addEventListener("error", (event: ErrorEvent) => {
      try {
        this.recordError({
          timestamp: new Date().toISOString(),
          message: event.message || "Unknown client runtime error",
          source: event.filename ? `${event.filename}:${event.lineno}:${event.colno}` : "window.onerror",
          stack: event.error?.stack,
          traceId: getActiveSessionTraceId(),
        });
      } catch {
        // Fallback safety
      }
    });

    // 3. Capture Unhandled Promise Rejections
    window.addEventListener("unhandledrejection", (event: PromiseRejectionEvent) => {
      try {
        const reason = event.reason;
        const message =
          typeof reason === "string"
            ? reason
            : reason?.message || JSON.stringify(reason) || "Unhandled Promise Rejection";
        this.recordError({
          timestamp: new Date().toISOString(),
          message,
          source: "unhandledrejection",
          stack: reason?.stack,
          traceId: getActiveSessionTraceId(),
        });
      } catch {
        // Fallback safety
      }
    });
  }
}

export const telemetry = new TelemetryStore();

/**
 * Initialize frontend observability listeners.
 */
export function initTelemetry(): void {
  telemetry.init();
}

/**
 * Instrumented fetch wrapper that injects W3C traceparent and X-Request-ID headers,
 * measures request latency, and logs API calls and failures to client telemetry.
 */
export async function instrumentedFetch(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<Response> {
  const traceId = getActiveSessionTraceId();
  const spanId = generateSpanId();
  const traceparent = formatTraceParent(traceId, spanId);
  const requestId = generateTraceId();

  const headers = new Headers(init?.headers || {});
  if (!headers.has("traceparent")) {
    headers.set("traceparent", traceparent);
  }
  if (!headers.has("X-Request-ID")) {
    headers.set("X-Request-ID", requestId);
  }

  const method =
    init?.method ||
    (typeof input === "object" && "method" in input && (input as Request).method
      ? (input as Request).method
      : "GET");
  const urlStr =
    typeof input === "string"
      ? input
      : input instanceof URL
      ? input.toString()
      : (input as Request).url;

  let endpoint = urlStr;
  try {
    const parsed = new URL(urlStr, typeof window !== "undefined" ? window.location.origin : "http://localhost");
    endpoint = parsed.pathname + parsed.search;
  } catch {
    // Keep original string if parsing fails
  }

  const startTime = performance.now();
  try {
    const response = await fetch(input, {
      ...init,
      headers,
    });
    const durationMs = Math.round(performance.now() - startTime);

    telemetry.recordApiMetric({
      timestamp: new Date().toISOString(),
      method,
      endpoint,
      status: response.status,
      durationMs,
      traceId,
      spanId,
      traceparent,
      ok: response.ok,
      error: response.ok ? undefined : `HTTP ${response.status}`,
    });

    if (!response.ok) {
      telemetry.recordError({
        timestamp: new Date().toISOString(),
        message: `API ${method} ${endpoint} returned status ${response.status}`,
        source: `API Call (${method})`,
        traceId,
      });
    }

    return response;
  } catch (err: any) {
    const durationMs = Math.round(performance.now() - startTime);
    const errorMessage = err?.message || "Network request failed";

    telemetry.recordApiMetric({
      timestamp: new Date().toISOString(),
      method,
      endpoint,
      status: 0,
      durationMs,
      traceId,
      spanId,
      traceparent,
      ok: false,
      error: errorMessage,
    });

    telemetry.recordError({
      timestamp: new Date().toISOString(),
      message: `Network error on ${method} ${endpoint}: ${errorMessage}`,
      source: `API Call (${method})`,
      stack: err?.stack,
      traceId,
    });

    throw err;
  }
}

/**
 * Utility function to simulate an unhandled client error for testing.
 */
export function simulateClientError(message: string = "Test simulated client exception"): void {
  telemetry.recordError({
    timestamp: new Date().toISOString(),
    message,
    source: "simulation_trigger",
    stack: new Error(message).stack,
    traceId: getActiveSessionTraceId(),
  });
}
