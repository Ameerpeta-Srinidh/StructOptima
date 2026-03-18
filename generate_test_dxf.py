
import ezdxf
from ezdxf import units

def create_complex_dxf(filename="complex_house.dxf"):
    doc = ezdxf.new(dxfversion='R2010')
    doc.units = units.MM
    msp = doc.modelspace()
    
    # Layers
    doc.layers.add("COLUMNS", color=4) # Cyan
    doc.layers.add("BEAMS", color=2) # Yellow
    doc.layers.add("WALLS", color=7) # White
    doc.layers.add("DOORS", color=3) # Green
    doc.layers.add("WINDOWS", color=1) # Red
    doc.layers.add("TEXT", color=7)
    
    # Grid Logic (4x3 Grid, 4m spans)
    # X Grid: 0, 4, 8, 12
    # Y Grid: 0, 4, 8
    
    x_lines = [0, 4000, 8000, 12000]
    y_lines = [0, 4000, 8000]
    
    col_size = 230
    
    # 1. Place Columns
    cols = []
    for x in x_lines:
        for y in y_lines:
            # Skip some to make it interesting (e.g. L-shape)
            if x == 12000 and y == 8000: continue # Cutout
            
            # Draw Rec
            cx, cy = x, y
            p1 = (cx - col_size/2, cy - col_size/2)
            p2 = (cx + col_size/2, cy - col_size/2)
            p3 = (cx + col_size/2, cy + col_size/2)
            p4 = (cx - col_size/2, cy + col_size/2)
            
            msp.add_lwpolyline([p1, p2, p3, p4, p1], dxfattribs={'layer': 'COLUMNS'})
            cols.append((x, y))
            
            # Label
            msp.add_text(f"C_{int(x)}_{int(y)}", dxfattribs={'layer': 'TEXT', 'height': 150}).set_placement((x+200, y+200))

    # 2. Place Design Beams (Connecting Grid)
    # Horizontal
    for y in y_lines:
        for i in range(len(x_lines)-1):
            x1, x2 = x_lines[i], x_lines[i+1]
            if x2 == 12000 and y == 8000: continue
            msp.add_line((x1, y), (x2, y), dxfattribs={'layer': 'BEAMS'})
            
    # Vertical
    for x in x_lines:
        for i in range(len(y_lines)-1):
            y1, y2 = y_lines[i], y_lines[i+1]
            if x == 12000 and y2 == 8000: continue
            msp.add_line((x, y1), (x, y2), dxfattribs={'layer': 'BEAMS'})

    # 3. Architectural Walls (Double lines around grid lines)
    # Parallel lines offset by 115mm
    for y in y_lines:
        for i in range(len(x_lines)-1):
            x1, x2 = x_lines[i], x_lines[i+1]
            if x2 == 12000 and y == 8000: continue
            
            # Wall Top/Bot
            msp.add_line((x1, y+115), (x2, y+115), dxfattribs={'layer': 'WALLS'})
            msp.add_line((x1, y-115), (x2, y-115), dxfattribs={'layer': 'WALLS'})
            
    for x in x_lines:
        for i in range(len(y_lines)-1):
            y1, y2 = y_lines[i], y_lines[i+1]
            if x == 12000 and y2 == 8000: continue
             # Wall Left/Right
            msp.add_line((x-115, y1), (x-115, y2), dxfattribs={'layer': 'WALLS'})
            msp.add_line((x+115, y1), (x+115, y2), dxfattribs={'layer': 'WALLS'})

    # 4. Doors (Simple Arcs/Lines)
    # Place a Door at (2000, 0) - Front Entrance
    msp.add_line((1500, -115), (1500, 115), dxfattribs={'layer': 'DOORS'})
    msp.add_line((2500, -115), (2500, 115), dxfattribs={'layer': 'DOORS'})
    msp.add_arc((2500, 115), radius=1000, start_angle=90, end_angle=180, dxfattribs={'layer': 'DOORS'})
    msp.add_text("Main Entry", dxfattribs={'layer': 'TEXT', 'height': 200}).set_placement((2000, -500))

    # 5. Rooms Text
    rooms = [
        ("Living Room", 2000, 2000),
        ("Dining", 6000, 2000),
        ("Kitchen", 10000, 2000),
        ("Bedroom 1", 2000, 6000),
        ("Bedroom 2", 6000, 6000),
        ("Master Bed", 10000, 6000),
    ]
    for txt, rx, ry in rooms:
        # Check if bounds
        if rx > 8000 and ry > 4000 and rx > 10000: continue # Cutout logic tweak check
        if rx == 10000 and ry == 6000 and 8000 not in y_lines: pass # Logic is fine
        
        msp.add_text(txt, dxfattribs={'layer': 'TEXT', 'height': 300}).set_placement((rx-500, ry))

    doc.saveas(filename)
    print(f"Generated {filename}")

if __name__ == "__main__":
    create_complex_dxf()
