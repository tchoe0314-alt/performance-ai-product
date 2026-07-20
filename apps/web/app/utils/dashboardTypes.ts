import type { LucideIcon } from "lucide-react";

import type { BuildingPlacement, SiteObjectType } from "../types";
import type { CadToolRequest } from "./cadToolTypes";
import type { SidebarStatus, SidePanelKey } from "./workspaceShell";

export type CapabilityExposure = {
  key: string;
  label: string;
  exposed: "yes" | "no";
  surfaces: string[];
  status: SidebarStatus;
  value: string;
  missingWiring: string;
  exactFix: string;
};

export type PrimaryWorkflowKey = "setup" | "draw" | "objects" | "design" | "analyze" | "deliver";

export type CadToolRequestForPreview = CadToolRequest;

export type PrimaryWorkflowItem = {
  key: PrimaryWorkflowKey;
  label: string;
  caption: string;
  panel: SidePanelKey;
  icon: LucideIcon;
  status: SidebarStatus;
  metric: string;
};

export type ApprovalState = "idle" | "approving" | "starting";

export type RecentChangeType =
  | "object_added"
  | "object_deleted"
  | "object_renamed"
  | "object_style_changed"
  | "object_type_changed"
  | "object_visibility_changed"
  | "site_boundary_unlocked"
  | "site_boundary_relocked"
  | "generate_recorded"
  | "review_package_recorded"
  | "ai_realism_recorded";

export type DraftUndoAction =
  | { action: "add"; object: BuildingPlacement }
  | {
      action: "add_many";
      objects: BuildingPlacement[];
      label: string;
    }
  | { action: "delete"; object: BuildingPlacement }
  | {
      action: "delete_many";
      objects: BuildingPlacement[];
      label: string;
    }
  | {
      action: "update";
      objectId: string;
      before: BuildingPlacement;
      after: BuildingPlacement;
      label: string;
    }
  | {
      action: "combine";
      object: BuildingPlacement;
      hiddenSources: BuildingPlacement[];
      label: string;
    }
  | {
      action: "explode";
      object: BuildingPlacement;
      beforeSources: BuildingPlacement[];
      afterSources: BuildingPlacement[];
      label: string;
    }
  | {
      action: "bulk_update";
      before: BuildingPlacement[];
      after?: BuildingPlacement[];
      label: string;
    };

export type DraftBlockDefinition = {
  id: string;
  name: string;
  type: SiteObjectType;
  objects: BuildingPlacement[];
  createdAt: number;
  updatedAt?: number;
  revision?: number;
};

export type RecentChange = {
  id: string;
  type: RecentChangeType;
  label: string;
  detail: string;
  createdAt: number;
  undo?: DraftUndoAction;
  undoBlockedReason?: string;
};

export type PerformanceAIDashboardProps = {
  forceDemoWorkspace?: boolean;
};
