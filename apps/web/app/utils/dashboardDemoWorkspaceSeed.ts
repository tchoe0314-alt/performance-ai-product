import type { ChatMessage, ProjectInput, ProjectRecord } from "../types";
import {
  createDemoPlacements,
  createDemoPlanResponse,
  DEMO_PROJECT_ID,
} from "./demoWorkspaceData";
import { createChatMessage, createWelcomeMessage } from "./chat";
import type { EngineeringSystemKey, SystemStatus } from "./workflowConstants";

export function buildDashboardDemoWorkspaceSeed({
  debugEmptyLayout,
  debugEmptyObjects,
}: {
  debugEmptyLayout: boolean;
  debugEmptyObjects: boolean;
}) {
  const demoPlacements = debugEmptyObjects
    ? []
    : debugEmptyLayout
      ? createDemoPlacements().filter((item) => item.type === "site")
      : createDemoPlacements();
  const demoResult = createDemoPlanResponse();
  const demoProjectInput: ProjectInput = {
    prompt_text: "Demo UI QA workspace for a 9-acre mixed-use civil site.",
    input_mode: "user",
    strict_mode: false,
    allow_ai_fill_for_blanks: false,
    manual_fields: {
      project_name: "Pinecrest Mixed-Use",
      file_name: "pinecrest-demo-ui",
      units: "ft",
      project_type: "mixed_use",
      lot: { x: 0, y: 0, w: 760, h: 520 },
      disciplines: ["roads", "grading", "drainage", "utilities"],
      buildings: demoPlacements
        .filter((item) => item.type !== "site")
        .map((item) => ({
          id: item.id,
          name: item.label ?? item.id,
          type: item.type,
          x: item.x,
          y: item.y,
          w: item.w,
          d: item.d,
          height_ft: item.h,
          rotation: item.rotation,
          source: item.source,
          generated: item.generated,
          locked: item.locked,
        })),
    },
    meta: {
      auto_named: false,
      auto_file_named: false,
      site_inputs: {
        address: "Pinecrest Mixed-Use Demo Site",
        geocode: {
          lat: 32.7767,
          lng: -96.797,
          display_name: "Pinecrest Mixed-Use Demo Site",
          provider: "demo",
        },
        site_rotation_deg: 0,
        site_alignment_locked: true,
        use_survey_for_grading: true,
        online_existing_conditions_discovery_v1: {
          version: "online_existing_conditions_discovery_v1",
          status: "candidates_found",
          candidate_count: 3,
          sources: [
            { key: "parcel_site_boundary", label: "parcel/site boundary", provider: "Demo Parcels", candidate_count: 1, review_required: true },
            { key: "road_row", label: "road/ROW data", provider: "Demo Roads", candidate_count: 1, review_required: true },
            { key: "terrain_dem_lidar", label: "terrain/DEM/LiDAR", provider: "Demo Terrain", candidate_count: 1, review_required: true },
            { key: "public_utilities", label: "public utility layers", provider: "", candidate_count: 0, review_required: true },
          ],
          missing_sources: [{ key: "public_utilities", label: "public utility layers" }],
          review_required: true,
          acceptance_status: "candidate",
        },
        auto_existing_conditions_v1: {
          version: "auto_existing_conditions_v1",
          status: "ready_for_review",
          triggered_by: "site_lock",
          clipped_to_locked_site: true,
          candidate_count: 3,
          missing_sources: ["public utility layers"],
          review_required: true,
          construction_release_allowed: false,
          truth_label:
            "Automatic existing-condition detection creates review-required candidates only; it is not survey/control or final professional evidence.",
        },
      },
    },
  };
  const demoProject: ProjectRecord = {
    project_id: DEMO_PROJECT_ID,
    name: "Pinecrest Mixed-Use",
    description: "Seeded demo workspace for UI QA.",
    updated_at: Date.now() / 1000,
    project_input: demoProjectInput,
    latest_result: demoResult,
    has_result: true,
  };
  const demoThread: ChatMessage[] = [
    createWelcomeMessage(),
    createChatMessage(
      "system",
      "Demo workspace loaded. Use this seeded project to QA canvas modes, sidebars, status cards, and object editing without signing in.",
      "status",
    ),
  ];
  const systemStatuses: Record<EngineeringSystemKey, SystemStatus> = {
    roads: "fresh",
    parking: "fresh",
    grading: "fresh",
    drainage: "stale",
    utilities: "fresh",
  };
  return { demoPlacements, demoResult, demoProject, demoThread, systemStatuses };
}
