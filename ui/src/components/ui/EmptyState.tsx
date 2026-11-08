import React from "react";
import { FolderOpen } from "lucide-react";
import { Button } from "./Button";

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  actionText?: string;
  onAction?: () => void;
}

export function EmptyState({
  title = "No data found",
  description = "No records match the current criteria or filters.",
  icon,
  actionText,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-lg border border-dashed border-border bg-card/40 my-4">
      <div className="p-3 rounded-full bg-muted text-muted-foreground mb-3">
        {icon || <FolderOpen className="w-8 h-8 stroke-1" />}
      </div>
      <h4 className="text-base font-semibold text-foreground">{title}</h4>
      <p className="text-sm text-muted-foreground max-w-sm mt-1 mb-4">{description}</p>
      {actionText && onAction && (
        <Button variant="outline" size="sm" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </div>
  );
}

