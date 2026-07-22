import { expect, test, type APIRequestContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const DEFAULT_API_URL = "https://api.civoraai.com";
const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const apiBaseUrl = (process.env.PLAYWRIGHT_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_URL).replace(/\/+$/, "");

const fixtureDir = path.resolve(__dirname, "../../../../backend/fixtures/real_input_benchmarks");
const landxmlFixture = path.join(fixtureDir, "surface_pipe.landxml");
const geojsonFixture = path.join(fixtureDir, "constraints.geojson");
const geotiffFixture = path.join(fixtureDir, "surface_grid.tif");
const lasFixture = path.join(fixtureDir, "surface_points.las");

type UploadResponse = {
  success?: boolean;
  file_type?: string;
  imports?: Array<Record<string, unknown>>;
  canonical_existing_conditions?: {
    canonical_existing_conditions_model?: {
      canonical_targets?: string[];
    };
  };
  import_validation?: {
    production_usable?: boolean;
    blockers?: Array<Record<string, unknown>>;
  };
  warnings?: string[];
};

async function login(request: APIRequestContext) {
  const response = await request.post(`${apiBaseUrl}/api/auth/login`, {
    data: { email, password },
  });
  expect(response.status(), "hosted login should succeed").toBe(200);
  const payload = (await response.json()) as { token?: string };
  const token = String(payload.token || "");
  expect(token, "hosted login returned a bearer token").toBeTruthy();
  return token;
}

async function uploadExistingCondition(
  request: APIRequestContext,
  token: string,
  file: { name: string; mimeType: string; buffer: Buffer },
) {
  const response = await request.post(`${apiBaseUrl}/api/upload-existing-conditions`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: { file },
  });
  expect(response.status(), `${file.name} upload should return a handled response`).toBe(200);
  return (await response.json()) as UploadResponse;
}

function canonicalTargets(payload: UploadResponse) {
  return payload.canonical_existing_conditions?.canonical_existing_conditions_model?.canonical_targets || [];
}

test.describe("hosted real source depth", () => {
  test("uploads LandXML, GeoJSON, GeoTIFF, and LAS paths without fake production truth", async ({ request }) => {
    test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required for hosted real source depth proof.");

    const token = await login(request);

    const landxml = await uploadExistingCondition(request, token, {
      name: "surface_pipe.landxml",
      mimeType: "application/xml",
      buffer: fs.readFileSync(landxmlFixture),
    });
    expect(landxml.success, "LandXML fixture should import as canonical review evidence").toBe(true);
    expect(canonicalTargets(landxml)).toEqual(expect.arrayContaining(["terrain_surface_metadata", "pipe_network_metadata"]));
    expect(landxml.import_validation?.production_usable, "LandXML alone must not become production/survey truth").toBe(false);

    const geojson = await uploadExistingCondition(request, token, {
      name: "constraints.geojson",
      mimeType: "application/geo+json",
      buffer: fs.readFileSync(geojsonFixture),
    });
    expect(geojson.success, "GeoJSON fixture should import as GIS/context evidence").toBe(true);
    expect(canonicalTargets(geojson)).toContain("gis_layers");
    expect(geojson.import_validation?.production_usable, "GIS context alone must not become production/survey truth").toBe(false);

    const geotiff = await uploadExistingCondition(request, token, {
      name: "surface_grid.tif",
      mimeType: "image/tiff",
      buffer: fs.readFileSync(geotiffFixture),
    });
    expect(geotiff.file_type).toBe("tif");
    expect(String(geotiff.imports?.[0]?.source_type || "")).toMatch(/geotiff/i);
    expect(geotiff.success, "Valid GeoTIFF fixture should canonicalize as terrain evidence").toBe(true);
    expect(canonicalTargets(geotiff)).toEqual(expect.arrayContaining(["dem_surface", "terrain_surface"]));
    expect(geotiff.import_validation?.production_usable, "GeoTIFF alone must not become survey/control truth").toBe(false);

    const las = await uploadExistingCondition(request, token, {
      name: "surface_points.las",
      mimeType: "application/octet-stream",
      buffer: fs.readFileSync(lasFixture),
    });
    expect(las.file_type).toBe("las");
    expect(String(las.imports?.[0]?.source_type || "")).toMatch(/las|point_cloud/i);
    expect(las.success, "Valid LAS fixture should canonicalize as LiDAR terrain evidence").toBe(true);
    expect(canonicalTargets(las)).toEqual(expect.arrayContaining(["lidar_point_cloud", "terrain_evidence"]));
    expect(las.import_validation?.production_usable, "LAS alone must not become survey/control truth").toBe(false);
  });
});
