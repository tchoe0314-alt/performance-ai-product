import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from backend.planning.landxml_io import build_landxml_pipe_network, import_landxml


class LandXmlIoTests(unittest.TestCase):
    def test_import_landxml_reads_surfaces_alignments_and_pipe_networks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "civil.landxml"
            path.write_text(
                """
                <LandXML>
                  <CgPoints>
                    <CgPoint name="1">0 0 100</CgPoint>
                    <CgPoint name="2">10 0 101</CgPoint>
                    <CgPoint name="3">0 10 99</CgPoint>
                  </CgPoints>
                  <Surfaces>
                    <Surface name="EG">
                      <Definition surfType="TIN">
                        <P>0 0 100</P>
                        <P>10 0 101</P>
                        <P>0 10 99</P>
                        <F>1 2 3</F>
                      </Definition>
                    </Surface>
                  </Surfaces>
                  <Alignments>
                    <Alignment name="Road A" length="100">
                      <CoordGeom><Line><Start>0 0 0</Start><End>100 0 0</End></Line></CoordGeom>
                    </Alignment>
                  </Alignments>
                  <PipeNetworks>
                    <PipeNetwork name="Storm"><Pipes><Pipe name="P-1" /></Pipes><Structs><Struct name="CB-1" /></Structs></PipeNetwork>
                  </PipeNetworks>
                </LandXML>
                """,
                encoding="utf-8",
            )

            imported = import_landxml(path)

            self.assertTrue(imported["success"])
            self.assertGreaterEqual(imported["point_count"], 3)
            self.assertEqual(imported["surface_count"], 1)
            self.assertEqual(imported["surfaces"][0]["face_count"], 1)
            self.assertEqual(imported["alignment_count"], 1)
            self.assertEqual(imported["pipe_network_count"], 1)

    def test_build_landxml_pipe_network_exports_parseable_pipe_contract(self) -> None:
        plan = {
            "meta": {
                "storm_pipes": {
                    "segments": [
                        {
                            "name": "STM-1",
                            "length_ft": 100.0,
                            "diameter_in": 18.0,
                            "slope_ft_ft": 0.01,
                            "path": [{"x": 0, "y": 0}, {"x": 100, "y": 0}],
                        }
                    ],
                    "structures": [{"name": "CB-1", "x": 0, "y": 0}],
                },
                "sanitary": {
                    "segments": [{"name": "SAN-1", "length_ft": 80.0, "diameter_in": 8.0, "path": [[0, 5], [80, 5]]}],
                    "manholes": [{"name": "MH-1", "x": 0, "y": 5}],
                },
            }
        }

        xml_text = build_landxml_pipe_network(plan, network_name="Export Test")
        root = ET.fromstring(xml_text)

        pipes = root.findall(".//Pipe")
        structs = root.findall(".//Struct")
        self.assertEqual(len(pipes), 2)
        self.assertEqual(len(structs), 2)
        self.assertEqual(pipes[0].attrib["system"], "storm")
