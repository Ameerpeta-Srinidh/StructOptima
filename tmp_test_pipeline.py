import glob
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.cad_loader import CADLoader

dxf_files = glob.glob("*.dxf") + glob.glob("test_dxfs/*.dxf") + glob.glob("real_world_dxfs/*.dxf") + glob.glob("samples/*.dxf")
successes = []
failures = []

for file in dxf_files:
    file_path = os.path.abspath(file)
    try:
        loader = CADLoader(file_path)
        gm, beams = loader.load_grid_manager(auto_frame=True, seismic_zone="III")
        if gm.columns:
            successes.append((file, len(gm.columns), len(beams)))
        else:
            failures.append((file, "0 columns placed"))
    except Exception as e:
        failures.append((file, type(e).__name__ + ": " + str(e)))

print("\n" + "="*50)
print("SUCCESSFULLY PARSED & FRAMED:")
print("="*50)
for file, cols, beams in sorted(successes):
    print(f"[SUCCESS] {file} -> {cols} columns, {beams} beams")

print("\n" + "="*50)
print("FAILED or EMPTY STRUCTURE:")
print("="*50)
for file, err in sorted(failures):
    print(f"[FAIL] {file} -> {err}")
