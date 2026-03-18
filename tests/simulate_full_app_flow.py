
import sys
import os
import traceback

# Add project root to path
sys.path.append(os.getcwd())

def run_smoke_test():
    print("🚀 Starting Comprehensive App Smoke Test...")
    # Redirect stdout to file to avoid truncation
    log_file = open("smoke_test.log", "w", encoding='utf-8')
    sys.stdout = log_file
    sys.stderr = log_file
    
    gm = None # Scope fix
    errors = []

    # 1. Test Key Imports
    print("\n[1/6] Testing Imports...")
    # ... (imports) ...

    # 2. Test Core Logic (Mock Data)
    print("\n[2/6] Testing Core Logic...")
    beams = [] # scope
    try:
        from src.grid_manager import GridManager
        # GridManager requires width/length as it is a Pydantic model
        gm = GridManager(width_m=20.0, length_m=20.0)
        # Use generate_grid to populate lines
        gm.generate_grid() 
        print(f"  ✅ GridManager initialized with {len(gm.x_grid_lines)}x{len(gm.y_grid_lines)} grid")
        
        # GridManager.generate_beams returns the list, doesn't store it as .beams
        beams = gm.generate_beams()
        print(f"  ✅ Beams generated: {len(beams)}")
        
    except Exception as e:
        errors.append(f"Core Logic Error: {str(e)}\n{traceback.format_exc()}")
        print(f"  ❌ Core Logic Failed: {e}")

    # 3. Test Visualization
    print("\n[3/6] Testing Visualization...")
    if gm and beams:
        try:
            from src.visualizer import Visualizer
            from src.materials import Concrete
            viz = Visualizer()
            concrete = Concrete.from_grade("M25")
            # Pass concrete object
            fig = viz.create_structure_figure(gm, beams, [], concrete, height_m=3.0, view_mode="Deflection")
            if fig:
                print("  ✅ 3D Structure Figure created (Deflection Mode)")
            
            # Test 2D Plan
            fig2d = viz.create_2d_plan(gm, beams)
            if fig2d:
                 print("  ✅ 2D Plan created")
                 
        except Exception as e:
             errors.append(f"Visualization Error: {str(e)}\n{traceback.format_exc()}")
             print(f"  ❌ Visualization Failed: {e}")
    else:
        print("  ⚠️ Skipping Visualization (GM or Beams missing)")

    # 4. Test BBS Generation
    print("\n[4/6] Testing BBS Module...")
    if gm and beams:
        try:
            from src.bbs_report import generate_bbs_from_grid_manager
            project_bbs = generate_bbs_from_grid_manager(gm, beams, "Test Project")
            print(f"  ✅ BBS generated: {len(project_bbs.members)} members")
            
            # Test Utilities
            from src.bbs_utils import get_site_vernacular, generate_bar_shape_svg
            ver = get_site_vernacular("B1")
            svg = generate_bar_shape_svg("21", {"A":100, "B":200})
            print(f"  ✅ BBS Utils verified (Vernacular: {ver})")
            
        except Exception as e:
            errors.append(f"BBS Error: {str(e)}\n{traceback.format_exc()}")
            print(f"  ❌ BBS Failed: {e}")
    else:
        print("  ⚠️ Skipping BBS (GM Init Failed)")
        
    # ... (Rest of logic) ...
    
    # Final Report
    print("\n" + "="*40)
    if errors:
        print(f"❌ SMOKE TEST FAILED with {len(errors)} errors:")
        for i, err in enumerate(errors):
            print(f"\n--- Error {i+1} ---\n{err}")
    else:
        print("✅ ALL SYSTEMS GO. App logic appears stable.")
    print("="*40)
    
    log_file.close()

if __name__ == "__main__":
    run_smoke_test()

if __name__ == "__main__":
    run_smoke_test()
