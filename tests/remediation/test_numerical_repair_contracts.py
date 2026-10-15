"""Independent analytical contracts; no application, files or providers."""
import unittest

from engines.hydrology_engine import RationalArea, compute_rational_method
from engines.detention_engine import BasinGeometry, basin_storage_cf, generate_stage_storage_curve
from engines.surface_engine import GridSurface, compare_surfaces
from engines.grading_engine import GradingEngine
from engines.earthwork_engine import compute_earthwork


class NumericalRepairContracts(unittest.TestCase):
    def test_rational_one_acre_reference_and_invalid_domains(self):
        self.assertAlmostEqual(compute_rational_method([RationalArea("reference", 1, .625, 4)]).total_runoff_cfs, 2.52)
        for values in ((-1, .625, 4), (1, 1.1, 4), (1, .625, float("nan"))):
            with self.subTest(values=values), self.assertRaises(ValueError):
                compute_rational_method([RationalArea("invalid", *values)])

    def test_rectangular_basin_simpson_reference(self):
        # Simpson's rule is exact for the quadratic cross-sectional area.
        area = lambda z: (100 + 8*z)*(20 + 8*z)
        expected = 5/6*(area(0) + 4*area(2.5) + area(5))
        self.assertAlmostEqual(expected, 24666.666666666668)
        self.assertAlmostEqual(basin_storage_cf(100, 20, 5, 4), expected)
        self.assertAlmostEqual(generate_stage_storage_curve(BasinGeometry(100, 20, 5, 4))[-1].storage_cf, expected)

    def test_uniform_node_domain_all_volume_entrypoints(self):
        existing = GridSurface(0, 0, 20, 20, 10, 3, 3, [[100.0]*3 for _ in range(3)])
        proposed = GridSurface(0, 0, 20, 20, 10, 3, 3, [[101.0]*3 for _ in range(3)])
        self.assertAlmostEqual(compare_surfaces(existing, proposed)["fill_cf"], 20*20*1)
        self.assertAlmostEqual(GradingEngine(existing)._compute_earthwork(proposed)[1], 20*20*1)
        self.assertAlmostEqual(compute_earthwork(existing, proposed)["results"]["fill_cf"], 20*20*1)
        proposed.x_min += 1000
        proposed.x_max += 1000
        with self.assertRaises(ValueError):
            compare_surfaces(existing, proposed)


if __name__ == "__main__":
    unittest.main()
