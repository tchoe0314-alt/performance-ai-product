import { useState } from "react";

/** Editable design controls; project restore/save adapters use these same setters. */
export function useDashboardDesignControls() {
  const [lotWidth, setLotWidth] = useState("");
  const [lotHeight, setLotHeight] = useState("");
  const [buildingWidth, setBuildingWidth] = useState("");
  const [buildingDepth, setBuildingDepth] = useState("");
  const [buildingCount, setBuildingCount] = useState("");
  const [setback, setSetback] = useState("");
  const [parkingCount, setParkingCount] = useState("");
  const [parkingStallWidth, setParkingStallWidth] = useState("9");
  const [parkingStallDepth, setParkingStallDepth] = useState("18");
  const [parkingAisleWidth, setParkingAisleWidth] = useState("24");
  const [parkingAdaAisleWidth, setParkingAdaAisleWidth] = useState("8");
  const [parkingAdaCount, setParkingAdaCount] = useState("0");
  const [parkingCompactCount, setParkingCompactCount] = useState("0");
  const [parkingCompactWidth, setParkingCompactWidth] = useState("8");
  const [parkingAngle, setParkingAngle] = useState<"90" | "60" | "45">("90");
  const [parkingLoading, setParkingLoading] = useState<"single" | "double">("double");
  const [minSlopePct, setMinSlopePct] = useState("");
  const [pipeMinSlopePct, setPipeMinSlopePct] = useState("");
  const [maxParkingSlopePct, setMaxParkingSlopePct] = useState("");
  const [maxRoadGradePct, setMaxRoadGradePct] = useState("");
  const [maxAdaCrossSlopePct, setMaxAdaCrossSlopePct] = useState("");
  const [assumedTerrainSlopePct, setAssumedTerrainSlopePct] = useState("8");
  const [roads, setRoads] = useState(true);
  const [grading, setGrading] = useState(true);
  const [drainage, setDrainage] = useState(true);
  return {
    lotWidth, setLotWidth,
    lotHeight, setLotHeight,
    buildingWidth, setBuildingWidth,
    buildingDepth, setBuildingDepth,
    buildingCount, setBuildingCount,
    setback, setSetback,
    parkingCount, setParkingCount,
    parkingStallWidth, setParkingStallWidth,
    parkingStallDepth, setParkingStallDepth,
    parkingAisleWidth, setParkingAisleWidth,
    parkingAdaAisleWidth, setParkingAdaAisleWidth,
    parkingAdaCount, setParkingAdaCount,
    parkingCompactCount, setParkingCompactCount,
    parkingCompactWidth, setParkingCompactWidth,
    parkingAngle, setParkingAngle,
    parkingLoading, setParkingLoading,
    minSlopePct, setMinSlopePct,
    pipeMinSlopePct, setPipeMinSlopePct,
    maxParkingSlopePct, setMaxParkingSlopePct,
    maxRoadGradePct, setMaxRoadGradePct,
    maxAdaCrossSlopePct, setMaxAdaCrossSlopePct,
    assumedTerrainSlopePct, setAssumedTerrainSlopePct,
    roads, setRoads,
    grading, setGrading,
    drainage, setDrainage,
  };
}
