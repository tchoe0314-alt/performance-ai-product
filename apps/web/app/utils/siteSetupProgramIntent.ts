export type SiteSetupProgramKind = "commercial" | "subdivision" | "campus";

/** Chooses a draft geometry family, not engineering suitability or approval. */
export function resolveSiteSetupProgramKind(message: string): SiteSetupProgramKind {
  const subdivision =
    /\b(recreate|copy|like the image|like this image|subdivision|master plan|lots|parcels|contours?|cad screenshot|as many)\b/i.test(message) &&
    /\b(image|plan|site|cad|subdivision|lots?|parcels?|contours?|dense|stuff)\b/i.test(message);
  const campus =
    /\b(urbanization|campus|boulevard|plaza|municipal|park|parks|master plan|site model|3d massing|massing|community|civic)\b/i.test(message) &&
    /\b(plan|site|layout|model|3d|buildings?|roads?|paths?|parking|trees?|plaza|like this|image)\b/i.test(message);
  // A single site lot/parcel is context, not an instruction to subdivide. Even
  // plural commercial parking lots/parcels must not select residential geometry.
  // Preserve explicit subdivision requests, including an office amenity.
  const commercialProgram = /\b(office|commercial|retail|industrial|warehouse|parking\s+lots?)\b/i.test(message);
  const explicitSubdivision = /\bsubdivision\b/i.test(message);
  return campus ? "campus" : subdivision && (!commercialProgram || explicitSubdivision) ? "subdivision" : "commercial";
}
