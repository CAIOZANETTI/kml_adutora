import unittest

from src.assets import load_pipe_catalog
from src.geo import build_base_dataframe, build_profile_arrays, build_stationing, parse_kml_file
from src.optimize.scenarios import evaluate_uniform_catalog
from src.optimize.workflow import analyze_alignment


class VectorizedWorkflowTest(unittest.TestCase):
    def _params(self):
        return {
            "flow_m3_s": 0.08,
            "station_interval_m": 50.0,
            "elevation_source": "kml",
            "upstream_residual_head_m": 25.0,
            "minimum_pressure_head_m": 8.0,
            "terminal_pressure_head_m": 10.0,
            "localized_loss_factor": 0.10,
            "enabled_materials": ["PVC-O", "FoFo", "Aco carbono"],
            "velocity_min_m_s": 0.5,
            "velocity_max_m_s": 3.0,
            "minimum_transient_pressure_bar": -0.2,
            "pump_efficiency": 0.72,
            "energy_cost_brl_per_kwh": 0.85,
            "energy_horizon_years": 5.0,
            "operating_hours_per_year": 5000.0,
            "surge_closure_factor": 0.35,
            "surge_trip_factor": 0.45,
            "block_valve_spacing_m": 1000.0,
            "anchor_min_deflection_deg": 20.0,
            "pump_station_base_cost_brl": 250000.0,
            "surge_protection_cost_brl": 120000.0,
            "shortlist_size": 4,
            "max_zone_length_m": 1200.0,
            "max_zones": 3,
            "transition_node_cost_brl": 20000.0,
            "kinematic_viscosity_m2_s": 1.004e-6,
        }

    def test_uniform_vectorized_engine_shapes(self):
        kml = b"""<?xml version='1.0' encoding='UTF-8'?>
        <kml xmlns='http://www.opengis.net/kml/2.2'>
          <Document>
            <Placemark>
              <name>Trecho teste</name>
              <LineString>
                <coordinates>
                  -47.0,-22.0,700 -46.995,-21.998,708 -46.990,-21.996,701 -46.985,-21.995,715
                </coordinates>
              </LineString>
            </Placemark>
          </Document>
        </kml>"""
        alignment = parse_kml_file(kml, "teste.kml")[0]
        station_points = build_stationing(alignment["points"], station_interval_m=50.0)
        for point in station_points:
            point["z_terrain_m"] = point["z_hint_m"]
            point["elevation_source"] = "kml"
        base_df = build_base_dataframe(station_points)
        base_arrays = build_profile_arrays(base_df)
        catalog_df = load_pipe_catalog().head(6)

        result = evaluate_uniform_catalog(base_arrays, catalog_df, self._params())
        self.assertEqual(len(result["summary_df"]), len(catalog_df))
        self.assertEqual(result["hydraulic"]["pressure_points_bar"].shape[1], len(base_df))
        self.assertEqual(result["hydraulic"]["velocity_seg_m_s"].shape[0], len(catalog_df))

    def test_parse_and_analyze_alignment_with_zones(self):
        kml = b"""<?xml version='1.0' encoding='UTF-8'?>
        <kml xmlns='http://www.opengis.net/kml/2.2'>
          <Document>
            <Placemark>
              <name>Trecho teste</name>
              <LineString>
                <coordinates>
                  -47.0,-22.0,700 -46.995,-21.998,708 -46.990,-21.996,701 -46.985,-21.995,715 -46.980,-21.994,704
                </coordinates>
              </LineString>
            </Placemark>
          </Document>
        </kml>"""
        alignments = parse_kml_file(kml, "teste.kml")
        result = analyze_alignment(alignments[0], self._params())
        self.assertFalse(result["detail_df"].empty)
        self.assertFalse(result["uniform_df"].empty)
        self.assertFalse(result["zoned_df"].empty)
        self.assertFalse(result["zone_solution_df"].empty)
        self.assertIn("zone_signature", result["best_layout"])
        self.assertGreaterEqual(result["kpis"]["zone_count"], 1)


if __name__ == "__main__":
    unittest.main()
