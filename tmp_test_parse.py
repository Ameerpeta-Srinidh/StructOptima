import glob
import os
import sys
import ezdxf

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.cad_parser import CADParser

dxf_files = glob.glob("*.dxf")

for file in dxf_files:
    parser = CADParser(file)
    parser.load()
    walls = parser.extract_walls()
    print(f"\n--- {file} ---")
    print(f"{len(walls)} wall segments found via extract_walls()")
    
    if len(walls) == 0:
        layer_names = parser.get_layers()
        wall_layers = [n for n in layer_names if any(kw in n.upper() for kw in ['WALL', 'STRUCT', 'LOAD', 'BEAR', 'MASONRY', 'BRICK'])]
        print(f"Detected wall layers: {wall_layers}")
        
        doc = ezdxf.readfile(file)
        msp = doc.modelspace()
        
        if wall_layers:
            for layer in wall_layers:
                types = set(e.dxftype() for e in msp.query(f'*[layer=="{layer}"]'))
                print(f"Layer '{layer}' contains entity types: {types}")
        else:
            print("No wall layers matching keywords found.")
            if "0" in layer_names:
                types = set(e.dxftype() for e in msp.query('*[layer=="0"]'))
                print(f"Layer '0' contains entity types: {types}")
