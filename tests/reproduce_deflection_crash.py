import sys
import os
import math # verifying
sys.path.append(os.getcwd())

from src.grid_manager import GridManager
from src.materials import Concrete
from src.visualizer import Visualizer
from src.quantifier import Quantifier
from src.stability import run_stability_check
from src.seismic import run_seismic_check

def run_test():
    print("🚀 Simulating Deflection Mode Flow...")
    
    # 1. Setup
    gm = GridManager(width_m=10, length_m=10)
    gm.generate_grid()
    beams = gm.generate_beams()
    concrete = Concrete.from_grade("M25")
    
    # 2. Visualization (Deflection Mode)
    print("  🔹 Creating Deflection Figure...")
    try:
        viz = Visualizer()
        fig = viz.create_structure_figure(gm, beams, [], concrete, view_mode="Deflection")
        print("  ✅ Deflection Figure Created")
    except Exception as e:
        print(f"  ❌ Visualization Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Post-Viz Logic (Metrics, BOM, etc.)
    print("  🔹 Running Post-Viz Modules...")
    try:
        # BOM
        quantifier = Quantifier()
        bom = quantifier.calculate_bom(gm.columns, beams, [], grid_mgr=gm)
        print("  ✅ BOM Calculated")
        
        # Stability
        print("  🔹 Running Stability Check...")
        check, summary = run_stability_check(gm.columns, beams, 1, 3.0)
        print(f"  ✅ Stability Check Done: {summary.total_members} members")
        
        # Seismic
        print("  🔹 Running Seismic Check...")
        # Building weight approx
        wt = 1000.0 
        seismic = run_seismic_check(gm.columns, beams, wt, zone="III", building_type="residential", fck=25)
        print("  ✅ Seismic Check Done")
        
        # 4. SHM Dashboard
        print("  🔹 Running SHM Checks...")
        try:
             from src.shm_viz import SHMDashboard
             shm = SHMDashboard("Test Project")
             di = shm.get_damage_index(1.45, 1.5)
             print(f"  ✅ Damage Index: {di}")
             fft = shm.calculate_fft_spectrum(1.45)
             print(f"  ✅ FFT Data: {len(fft['freq'])} points")
             heat = shm.generate_heatmap_data(["C1", "C2"])
             print(f"  ✅ Heatmap Data: {len(heat)} points")
        except ImportError:
             print("  ⚠️ SHM Module not found (Skipping)")

        # 5. Site Inspection
        print("  🔹 Running Site Inspection Checks...")
        try:
             from src.site_inspection import SiteInspectionManager
             site = SiteInspectionManager("Test Site")
             chk = site.generate_checklist("Pre_Pour")
             print(f"  ✅ Checklist Items: {len(chk)}")
             
             # Test Map Data
             map_data = site.get_defect_map_data()
             print(f"  ✅ Map Data: {len(map_data)} points")
             
             # Test QR
             qr = site.generate_qr_code("TestCol")
             print("  ✅ QR Code Generated")
             
        except ImportError:
             print("  ⚠️ Site Module not found (Skipping)")
             
    except Exception as e:
         print(f"  ❌ Post-Viz Logic Failed: {e}")
         import traceback
         traceback.print_exc()

if __name__ == "__main__":
    run_test()
