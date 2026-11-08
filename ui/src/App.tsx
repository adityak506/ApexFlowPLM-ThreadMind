import React, { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { Skeleton } from "@/components/ui/Skeleton";

// Dynamic code-splitting for optimal route performance
const DashboardPage = lazy(() => import("@/pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const PartSearchPage = lazy(() => import("@/pages/PartSearchPage").then((m) => ({ default: m.PartSearchPage })));
const PartDetailPage = lazy(() => import("@/pages/PartDetailPage").then((m) => ({ default: m.PartDetailPage })));
const BomExplorerPage = lazy(() => import("@/pages/BomExplorerPage").then((m) => ({ default: m.BomExplorerPage })));
const BomComparePage = lazy(() => import("@/pages/BomComparePage").then((m) => ({ default: m.BomComparePage })));
const ChangeImpactPage = lazy(() => import("@/pages/ChangeImpactPage").then((m) => ({ default: m.ChangeImpactPage })));
const ChangeRequestsPage = lazy(() => import("@/pages/ChangeRequestsPage").then((m) => ({ default: m.ChangeRequestsPage })));
const IssuesDetailPage = lazy(() => import("@/pages/IssuesDetailPage").then((m) => ({ default: m.IssuesDetailPage })));
const DigitalThreadPage = lazy(() => import("@/pages/DigitalThreadPage").then((m) => ({ default: m.DigitalThreadPage })));
const SystemHealthPage = lazy(() => import("@/pages/SystemHealthPage").then((m) => ({ default: m.SystemHealthPage })));

function RouteFallback() {
  return (
    <div className="space-y-6 p-6 animate-pulse" role="status" aria-label="Loading page content">
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-28 rounded-xl" />
      </div>
      <Skeleton className="h-96 w-full rounded-xl mt-6" />
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="parts" element={<PartSearchPage />} />
            <Route path="parts/:partNumber" element={<PartDetailPage />} />
            <Route path="bom" element={<BomExplorerPage />} />
            <Route path="bom/compare" element={<BomComparePage />} />
            <Route path="impact" element={<ChangeImpactPage />} />
            <Route path="changes" element={<ChangeRequestsPage />} />
            <Route path="digital-thread" element={<DigitalThreadPage />} />
            <Route path="issues" element={<IssuesDetailPage />} />
            <Route path="system-health" element={<SystemHealthPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;

