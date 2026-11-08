import React, { useEffect, useState } from "react";
import { Moon, Sun, Database, Server, Layers } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface NavbarProps {
  backendType?: "mock" | "windchill";
}

export function Navbar({ backendType = "mock" }: NavbarProps) {
  const [isDark, setIsDark] = useState<boolean>(() => {
    return (
      localStorage.getItem("theme") === "dark" ||
      (!localStorage.getItem("theme") && window.matchMedia("(prefers-color-scheme: dark)").matches)
    );
  });

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [isDark]);

  const toggleTheme = () => setIsDark((prev) => !prev);

  const isMock = backendType === "mock";

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-border bg-card/80 px-6 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary/10 text-primary border border-primary/20">
          <Layers className="w-5 h-5" />
        </div>
        <div>
          <span className="text-base font-bold tracking-tight text-foreground flex items-center gap-2">
            ApexFlow PLM
            <span className="text-xs font-normal text-muted-foreground hidden sm:inline">
              PTC Windchill Architecture
            </span>
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Backend Indicator Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full border border-border bg-muted/50 text-xs font-medium">
          {isMock ? (
            <>
              <Database className="w-3.5 h-3.5 text-blue-500" />
              <span className="text-muted-foreground">Backend:</span>
              <span className="font-semibold text-blue-600 dark:text-blue-400">Mock (SQLite)</span>
            </>
          ) : (
            <>
              <Server className="w-3.5 h-3.5 text-emerald-500" />
              <span className="text-muted-foreground">Backend:</span>
              <span className="font-semibold text-emerald-600 dark:text-emerald-400">Windchill (OData)</span>
            </>
          )}
        </div>

        {/* Dark/Light Mode Toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          className="rounded-full text-muted-foreground hover:text-foreground"
        >
          {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-700" />}
        </Button>
      </div>
    </header>
  );
}

