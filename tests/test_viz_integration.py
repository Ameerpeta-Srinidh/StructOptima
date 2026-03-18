
import sys
import os
sys.path.append(os.getcwd())

import unittest
from src.digital_twin import DigitalTwinExplorer
from src.shm_viz import SHMDashboard
from src.site_inspection import SiteInspectionManager

class TestVisualizationIntegration(unittest.TestCase):
    
    def setUp(self):
        self.dt = DigitalTwinExplorer("TestProject")
        self.shm = SHMDashboard("TestProject")
        self.site = SiteInspectionManager("TestProject")
        
    def test_digital_twin_metadata(self):
        print("\nTesting Digital Twin Metadata...")
        meta_col = self.dt.get_element_metadata("C1")
        self.assertEqual(meta_col["Type"], "Column")
        self.assertIn("FireRating", meta_col)
        print(f"✅ Metadata retrieved for C1: {meta_col}")
        
        dev = self.dt.get_as_built_deviation("C1")
        self.assertIn("dx", dev)
        print(f"✅ As-Built Deviation simulated: {dev}")

    def test_shm_viz(self):
        print("\nTesting SHM Visualization...")
        # 1. Heatmap
        heat_data = self.shm.generate_heatmap_data(["C1", "B1"])
        self.assertTrue(0.0 <= heat_data["C1"] <= 1.0)
        print(f"✅ Heatmap data generated: {heat_data}")
        
        # 2. Damage Index
        di = self.shm.get_damage_index(current_freq=1.4, baseline_freq=1.5)
        print(f"✅ Damage Index calculated: {di}")
        self.assertIn("status", di)
        
        # 3. FFT
        fft = self.shm.calculate_fft_spectrum(1.5)
        self.assertEqual(len(fft["freq"]), 100)
        print("✅ FFT Spectrum generated.")

    def test_site_inspection_ar(self):
        print("\nTesting Site Inspection AR Tools...")
        # 1. QR Code
        qr = self.site.generate_qr_code("C1")
        self.assertTrue(qr.startswith("http"))
        print(f"✅ QR Code URL: {qr}")
        
        # 2. Defect with coords
        defect = self.site.classify_defect(0.5, "Shear Crack", "Beam", coordinates={"lat": 12.0, "lon": 77.0})
        self.assertIsNotNone(defect.location_coords)
        print(f"✅ Defect classified with Geo-Tags: {defect.defect_type} at {defect.location_coords}")
        
        # 3. Map Data
        map_data = self.site.get_defect_map_data()
        self.assertEqual(len(map_data), 1)
        self.assertEqual(map_data[0]["type"], "Shear Crack")
        print("✅ Defect Map Data retrieval successful.")

if __name__ == '__main__':
    unittest.main()
