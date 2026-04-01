# engines/surface_engine.py



from __future__ import annotations



import csv

import math

from dataclasses import dataclass

from typing import Iterator, List, Optional, Tuple





# =========================================================

# DATA CLASSES

# =========================================================



@dataclass

class SurveyPoint:

    x: float

    y: float

    z: float





@dataclass

class GridSurface:

    x_min: float

    y_min: float

    x_max: float

    y_max: float

    cell_size: float

    ncols: int

    nrows: int

    values: List[List[float]]



    # -----------------------------------------------------



    def x_at(self, col: int) -> float:

        return self.x_min + col * self.cell_size



    def y_at(self, row: int) -> float:

        return self.y_min + row * self.cell_size



    def elevation_at_index(self, row: int, col: int) -> float:

        return self.values[row][col]



    def iter_points(self) -> Iterator[Tuple[float, float, float]]:

        for row in range(self.nrows):

            y = self.y_at(row)

            for col in range(self.ncols):

                x = self.x_at(col)

                yield x, y, self.values[row][col]



    def bounds(self) -> Tuple[float, float, float, float]:

        return self.x_min, self.y_min, self.x_max, self.y_max

    def copy(self) -> "GridSurface":

        return GridSurface(
            x_min=self.x_min,
            y_min=self.y_min,
            x_max=self.x_max,
            y_max=self.y_max,
            cell_size=self.cell_size,
            ncols=self.ncols,
            nrows=self.nrows,
            values=[list(row) for row in self.values],
        )





# =========================================================

# SURFACE ENGINE

# =========================================================



class SurfaceEngine:

    """

    Builds an existing ground surface using IDW (Inverse Distance Weighting).

    Simple, stable, and good for debugging.

    """



    def __init__(self, points: List[SurveyPoint]):

        if len(points) < 3:

            raise ValueError("Need at least 3 survey points.")

        self.points = points



    # -----------------------------------------------------



    @classmethod

    def from_csv(cls, csv_path: str) -> "SurfaceEngine":

        points: List[SurveyPoint] = []



        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:

            reader = csv.DictReader(f)



            required = {"x", "y", "z"}

            fieldnames = {h.lower().strip() for h in (reader.fieldnames or [])}



            if not required.issubset(fieldnames):

                raise ValueError(f"CSV must contain columns: {required}")



            for i, row in enumerate(reader, start=2):

                try:

                    x = float(row["x"])

                    y = float(row["y"])

                    z = float(row["z"])

                except Exception:

                    raise ValueError(f"Bad row {i}: {row}")



                points.append(SurveyPoint(x, y, z))



        return cls(points)



    # -----------------------------------------------------



    def bounds(self) -> Tuple[float, float, float, float]:

        xs = [p.x for p in self.points]

        ys = [p.y for p in self.points]

        return min(xs), min(ys), max(xs), max(ys)



    # -----------------------------------------------------



    def elevation_at(

        self,

        x: float,

        y: float,

        power: float = 2.0,

        neighbors: int = 8,

        max_radius: Optional[float] = None,

    ) -> float:



        dists: List[Tuple[float, float]] = []



        for pt in self.points:

            dx = x - pt.x

            dy = y - pt.y

            d = math.hypot(dx, dy)



            if d == 0:

                return pt.z



            if max_radius is not None and d > max_radius:

                continue



            dists.append((d, pt.z))



        if not dists:

            # fallback if radius excluded everything

            for pt in self.points:

                d = max(math.hypot(x - pt.x, y - pt.y), 1e-9)

                dists.append((d, pt.z))



        dists.sort(key=lambda t: t[0])

        nearest = dists[: max(1, neighbors)]



        weighted_sum = 0.0

        total_weight = 0.0



        for d, z in nearest:

            w = 1.0 / (d ** power)

            weighted_sum += z * w

            total_weight += w



        return weighted_sum / total_weight if total_weight else 0.0



    # -----------------------------------------------------



    def build_grid(

        self,

        x_min: Optional[float] = None,

        y_min: Optional[float] = None,

        x_max: Optional[float] = None,

        y_max: Optional[float] = None,

        cell_size: float = 10.0,

        padding: float = 0.0,

        power: float = 2.0,

        neighbors: int = 8,

    ) -> GridSurface:



        if cell_size <= 0:

            raise ValueError("cell_size must be > 0")



        bx0, by0, bx1, by1 = self.bounds()



        x_min = bx0 if x_min is None else x_min

        y_min = by0 if y_min is None else y_min

        x_max = bx1 if x_max is None else x_max

        y_max = by1 if y_max is None else y_max



        # apply padding

        x_min -= padding

        y_min -= padding

        x_max += padding

        y_max += padding



        ncols = int(round((x_max - x_min) / cell_size)) + 1

        nrows = int(round((y_max - y_min) / cell_size)) + 1



        values: List[List[float]] = []



        for row in range(nrows):

            y = y_min + row * cell_size

            row_vals: List[float] = []



            for col in range(ncols):

                x = x_min + col * cell_size

                z = self.elevation_at(x, y, power=power, neighbors=neighbors)

                row_vals.append(z)



            values.append(row_vals)



        return GridSurface(

            x_min=x_min,

            y_min=y_min,

            x_max=x_min + (ncols - 1) * cell_size,

            y_max=y_min + (nrows - 1) * cell_size,

            cell_size=cell_size,

            ncols=ncols,

            nrows=nrows,

            values=values,

        )



    # -----------------------------------------------------



    def spot_elevations(

        self,

        x_min: float,

        y_min: float,

        x_max: float,

        y_max: float,

        spacing: float = 25.0,

    ) -> List[Tuple[float, float, float]]:



        if spacing <= 0:

            raise ValueError("spacing must be > 0")



        spots: List[Tuple[float, float, float]] = []



        y = y_min

        while y <= y_max + 1e-9:

            x = x_min

            while x <= x_max + 1e-9:

                z = self.elevation_at(x, y)

                spots.append((x, y, z))

                x += spacing

            y += spacing



        return spots

