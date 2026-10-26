import { expect, test } from "@playwright/test";
import fixture from "../fixtures/q01-office-brief-v1.json";
import { resolveSiteSetupProgramKind, type SiteSetupProgramKind } from "../../app/utils/siteSetupProgramIntent";
import nondefault from "../fixtures/q01-office-brief-nondefault-v1.json";
import { parseCommercialConceptSpec } from "../../app/utils/demoWorkspaceData";

const cases: Array<[string, string, SiteSetupProgramKind]> = [
  ["audited office brief", fixture.command, "commercial"],
  ["office single lot", "Set up an office site on a 1000 by 1000 ft lot", "commercial"],
  ["retail single parcel", "Create a retail site on one parcel", "commercial"],
  ["industrial lot", "Create an industrial site on a lot", "commercial"],
  ["office multi-parcel", "Create office buildings on multiple parcels", "commercial"],
  ["commercial parking lots", "Plan parking lots around the office site", "commercial"],
  ["single-site lot is not subdivision", "Prepare a site on a 1000 ft lot", "commercial"],
  ["single-site parcel is not subdivision", "Prepare a site on a parcel", "commercial"],
  ["explicit subdivision", "Create a subdivision CAD plan", "subdivision"],
  ["explicit subdivision with office amenity", "Create a subdivision site with an office amenity", "subdivision"],
  ["multiple residential lots", "Create 24 lots on this site", "subdivision"],
  ["multiple parcels", "Split this site into 12 parcels", "subdivision"],
  ["CAD screenshot reference", "Recreate this CAD screenshot with contours on the site", "subdivision"],
  ["subdivision image", "Copy this image of a subdivision site", "subdivision"],
  ["campus", "Create an urbanization campus site with roads and plaza", "campus"],
  ["campus master plan", "Create a campus master plan with buildings and parking", "campus"],
  ["civic plan", "Create a civic site plan with parks and paths", "campus"],
  ["commercial ordinary plan", "Create a commercial office site with parking", "commercial"],
];
for (const [name, prompt, expected] of cases) test(`site setup intent: ${name}`, () => {
  expect(resolveSiteSetupProgramKind(prompt)).toBe(expected);
});

test("nondefault commercial requirements reach the existing generator spec without preset substitution", () => {
  expect(resolveSiteSetupProgramKind(nondefault.command)).toBe("commercial");
  expect(parseCommercialConceptSpec(nondefault.command)).toMatchObject({
    buildingAreaSf: nondefault.expected.building_program_sf,
    parkingStalls: nondefault.expected.parking_count,
    buildingUse: "office",
    siteWidth: nondefault.expected.lot_width_ft,
    siteHeight: nondefault.expected.lot_height_ft,
  });
});
