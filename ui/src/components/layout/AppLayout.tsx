import React, { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { Navbar } from "./Navbar";
import { Sidebar } from "./Sidebar";
import { AiAssistantPanel } from "@/components/chat/AiAssistantPanel";
import { getSystemHealth } from "@/services/api";

export function AppLayout() {
  const [backendType, setBackendType] = useState<"mock" | "windchill">("mock");

  useEffect(() => {
    getSystemHealth()
      .then((data) => {
        if (data?.backend === "windchill") {
          setBackendType("windchill");
        } else {
          setBackendType("mock");
        }
      })
      .catch(() => {
        // Safe fallback
      });
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <Navbar backendType={backendType} />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-x-hidden p-6 md:p-8 max-w-7xl">
          <Outlet />
        </main>
      </div>
      <AiAssistantPanel />
    </div>
  );
}
