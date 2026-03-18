import ezdxf

def create_sample_dxf(filename="sample_design.dxf"):
    doc = ezdxf.new()
    msp = doc.modelspace()

    # Define standard layers
    # Colors: 1=Red (Columns), 5=Blue (Beams), 3=Green (Footings)
    doc.layers.new(name='COLUMNS', dxfattribs={'color': 1}) # Red
    doc.layers.new(name='BEAMS', dxfattribs={'color': 5})   # Blue
    doc.layers.new(name='FOOTINGS', dxfattribs={'color': 3}) # Green
    doc.layers.new(name='WALLS', dxfattribs={'color': 7})   # White/Black
    doc.layers.new(name='DOORS', dxfattribs={'color': 2})   # Yellow

    print(f"Generating {filename}...")

    # Grid Setup: 2 Bays X (4m each), 1 Bay Y (5m)
    # Grid Lines: X=0, 4000, 8000. Y=0, 5000.
    
    col_size = 300 # mm
    half_col = col_size / 2
    wall_thick = 230
    half_wall = wall_thick / 2
    
    # Coordinates (mm)
    coords = [
        (0, 0), (4000, 0), (8000, 0),
        (0, 5000), (4000, 5000), (8000, 5000)
    ]
    
    # 3. Create Walls (Architectural Layout)
    # Walls run along grid lines, enclosing the columns
    # Horizontal Walls
    for y in [0, 5000]:
        # Wall from X=0 to X=8000
        # Draw two lines with thickness
        y_top = y + half_wall
        y_bot = y - half_wall
        msp.add_line((0, y_top), (8000, y_top), dxfattribs={'layer': 'WALLS'})
        msp.add_line((0, y_bot), (8000, y_bot), dxfattribs={'layer': 'WALLS'})

    # Vertical Walls
    for x in [0, 4000, 8000]:
        x_left = x - half_wall
        x_right = x + half_wall
        msp.add_line((x_left, 0), (x_left, 5000), dxfattribs={'layer': 'WALLS'})
        msp.add_line((x_right, 0), (x_right, 5000), dxfattribs={'layer': 'WALLS'})

    # Add a "Door" in the middle of bottom wall (Bay 1)
    # Simple representation: Circle or Block
    msp.add_circle((2000, 0), radius=450, dxfattribs={'layer': 'DOORS'})

    # 1. Create Columns (Closed Polylines)

    for cx, cy in coords:
        # Draw column centered at cx, cy
        # Local corners relative to center
        x1, y1 = cx - half_col, cy - half_col
        x2, y2 = cx + half_col, cy - half_col
        x3, y3 = cx + half_col, cy + half_col
        x4, y4 = cx - half_col, cy + half_col
        
        msp.add_lwpolyline(
            [(x1, y1), (x2, y2), (x3, y3), (x4, y4), (x1, y1)], 
            dxfattribs={'layer': 'COLUMNS'}
        )
        
        # Optional: Add Footing (1500x1500mm) centered on column
        f_size = 1500
        hf = f_size / 2
        fx1, fy1 = cx - hf, cy - hf
        fx2, fy2 = cx + hf, cy - hf
        fx3, fy3 = cx + hf, cy + hf
        fx4, fy4 = cx - hf, cy + hf
        
        msp.add_lwpolyline(
            [(fx1, fy1), (fx2, fy2), (fx3, fy3), (fx4, fy4), (fx1, fy1)],
            dxfattribs={'layer': 'FOOTINGS'}
        )

    # 2. Create Beams (Lines connecting columns)
    # Horizontal Beams
    y_lines = [0, 5000]
    for y in y_lines:
        msp.add_line((0, y), (4000, y), dxfattribs={'layer': 'BEAMS'}) # Bay 1
        msp.add_line((4000, y), (8000, y), dxfattribs={'layer': 'BEAMS'}) # Bay 2

    # Vertical Beams
    x_lines = [0, 4000, 8000]
    for x in x_lines:
        msp.add_line((x, 0), (x, 5000), dxfattribs={'layer': 'BEAMS'})

    doc.saveas(filename)
    print(f"Successfully created: {filename} in {doc.filename}")
    print("Layers used: COLUMNS, BEAMS, FOOTINGS")

if __name__ == "__main__":
    create_sample_dxf()
