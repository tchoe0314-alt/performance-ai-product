import type { BuildingPlacement } from "../types";
import type { PreviewSemanticLayer } from "./previewSemanticLayers";
import { DEFAULT_PREVIEW_SOURCE_LAYER_VISIBILITY, type PreviewSourceLayerVisibility } from "./previewSourceLayers";

export const ENVIRONMENT_LAYERS = ["topographic", "zoning", "parcels", "survey", "utilities"] as const;
export type EnvironmentLayer = typeof ENVIRONMENT_LAYERS[number];
export type DisplayUnits = "ft" | "m";
export type EnvironmentScope = { account: string; project: string; generation: number };
export type WorkspaceEnvironment = {
  version: 1; mode: "2d" | "3d"; quality: "standard" | "high";
  units: DisplayUnits; mapEnabled: boolean; satellite: boolean; mapLocked: boolean;
  layers: Record<EnvironmentLayer, boolean>; semantic: Partial<Record<PreviewSemanticLayer, boolean>>;
  sources: PreviewSourceLayerVisibility; snap: boolean; ortho: boolean; grid: boolean; gridFt: number;
  hiddenCadLayers: string[];
};
export function defaultEnvironment(): WorkspaceEnvironment {
  return { version: 1, mode: "2d", quality: "standard", units: "ft", mapEnabled: false, satellite: true,
    mapLocked: false, layers: {topographic:true,zoning:true,parcels:true,survey:true,utilities:true},
    semantic: {}, sources: {...DEFAULT_PREVIEW_SOURCE_LAYER_VISIBILITY}, snap:true, ortho:false, grid:false, gridFt:5, hiddenCadLayers:[] };
}
export function environmentStorageKey(scope: EnvironmentScope) {
  return `civora-environment-v1:${JSON.stringify([scope.account,scope.project||`draft-${scope.generation}`])}`;
}
export function parseEnvironment(raw: string | null): WorkspaceEnvironment {
  const result=defaultEnvironment();
  try {
    const value=JSON.parse(raw??"null");if(value?.version!==1)return result;
    if(value.mode==="2d"||value.mode==="3d")result.mode=value.mode;
    if(value.quality==="standard"||value.quality==="high")result.quality=value.quality;
    if(value.units==="ft"||value.units==="m")result.units=value.units;
    if(Array.isArray(value.hiddenCadLayers))result.hiddenCadLayers=[...new Set(value.hiddenCadLayers.filter((layer:unknown):layer is string=>typeof layer==="string"&&layer.length>0&&layer.length<=100))].slice(0,500) as string[];
    for(const key of ["mapEnabled","satellite","mapLocked","snap","ortho","grid"] as const)if(typeof value[key]==="boolean")result[key]=value[key];
    if(typeof value.gridFt==="number"&&Number.isFinite(value.gridFt)&&value.gridFt>=0.1&&value.gridFt<=1000)result.gridFt=value.gridFt;
    for(const key of ENVIRONMENT_LAYERS)if(typeof value.layers?.[key]==="boolean")result.layers[key]=value.layers[key];
    for(const key of Object.keys(result.sources) as Array<keyof PreviewSourceLayerVisibility>)if(typeof value.sources?.[key]==="boolean")result.sources[key]=value.sources[key];
    for(const key of ["buildings","roads","parking","utilities","lots","landscape","water","other"] as PreviewSemanticLayer[])if(typeof value.semantic?.[key]==="boolean")result.semantic[key]=value.semantic[key];
  }catch{/* Broken view preferences cannot prevent opening the design. */}
  return result;
}
export function displayLength(feet:number,units:DisplayUnits,places=1,keepZeros=false) {
  const rounded=(feet*(units==="m"?0.3048:1)).toFixed(places);
  return `${keepZeros ? rounded : Number(rounded)} ${units}`;
}
/** Classify actual modeled/imported data; a setback alone is not zoning. */
export function environmentLayerForObject(item: {type?:string;meta?:BuildingPlacement["meta"]}): EnvironmentLayer | undefined {
  const tokens=[item.meta?.source_type,item.meta?.source_kind,item.meta?.cad_layer,item.meta?.layer,item.meta?.environment_layer].filter(Boolean).join(" ").toLowerCase();
  if(/zoning|zoning_boundary/.test(tokens))return "zoning";
  if(/parcel|boundary_parcel/.test(tokens)||item.type==="lot"||item.type==="lot_block")return "parcels";
  if(/eg_contour|topograph|contours|c-topo/.test(tokens))return "topographic";
  if(/survey|c-surv/.test(tokens))return "survey";
  if(["utility","utility_corridor","hydrant","manhole","inlet","outfall"].includes(String(item.type))||/c-util|c-watr|c-san|utility/.test(tokens))return "utilities";
}
export function environmentObjectVisible(item:{type?:string;meta?:BuildingPlacement["meta"]},layers:WorkspaceEnvironment["layers"]) {
  const layer=environmentLayerForObject(item);return !layer||layers[layer];
}
