import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Package,
  Layers,
  GitCompare,
  Zap,
  FileText,
  Activity,
  Workflow,
  HeartPulse,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  title: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { title: "Dashboard", path: "/", icon: LayoutDashboard },
  { title: "Part Catalog", path: "/parts", icon: Package },
  { title: "BOM Explorer", path: "/bom", icon: Layers },
  { title: "BOM Compare", path: "/bom/compare", icon: GitCompare },
  { title: "Impact Analysis", path: "/impact", icon: Zap },
  { title: "Change Requests", path: "/changes", icon: FileText },
  { title: "Digital Thread", path: "/digital-thread", icon: Workflow },
  { title: "Data Health", path: "/issues", icon: Activity },
  { title: "System Health", path: "/system-health", icon: HeartPulse },
];

export function Sidebar() {
  return (
    <aside className="w-64 border-r border-border bg-card flex flex-col shrink-0 min-h-[calc(100vh-4rem)]">
      <div className="p-4 border-b border-border/50">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Navigation
        </p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.title}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border/50 text-xs text-muted-foreground">
        <div className="flex items-center justify-between">
          <span>PLM Version</span>
          <span className="font-mono text-[11px] font-semibold text-foreground">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
}

