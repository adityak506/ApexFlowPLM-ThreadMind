import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind class names safely with clsx and twMerge.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format ISO datetime string into human readable localized string.
 */
export function formatDate(isoString?: string | null): string {
  if (!isoString) return "-";
  try {
    const d = new Date(isoString);
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

/**
 * Lifecycle state badge color definitions:
 * - IN_WORK: Blue
 * - UNDER_REVIEW: Amber
 * - RELEASED: Green
 * - OBSOLETE: Red
 */
export function getLifecycleBadgeClass(state?: string | null): string {
  const norm = (state || "").toUpperCase().replace(/\s+/g, "_");
  switch (norm) {
    case "IN_WORK":
      return "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-800";
    case "UNDER_REVIEW":
      return "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800";
    case "RELEASED":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800";
    case "OBSOLETE":
      return "bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200 dark:border-rose-800";
    default:
      return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700";
  }
}

/**
 * Priority badge color definitions:
 * - EMERGENCY: Purple/Red
 * - HIGH: Orange
 * - MEDIUM: Yellow
 * - LOW: Slate
 */
export function getPriorityBadgeClass(priority?: string | null): string {
  const norm = (priority || "").toUpperCase();
  switch (norm) {
    case "EMERGENCY":
      return "bg-red-500 text-white font-semibold";
    case "HIGH":
      return "bg-orange-100 text-orange-800 dark:bg-orange-950/60 dark:text-orange-300 border-orange-200 dark:border-orange-800";
    case "MEDIUM":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-950/60 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800";
    case "LOW":
      return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

