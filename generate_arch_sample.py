import ezdxf

def create_arch_dxf(filename="sample_arch_only.dxf"):
    doc = ezdxf.new()
    msp = doc.modelspace()

    # Define architectural layers only
    doc.layers.new(name='WALLS', dxfattribs={'color': 7})   # White/Black
    doc.layers.new(name='DOORS', dxfattribs={'color': 2})   # Yellow

    print(f"Generating Architectural file {filename}...")

    # Grid Setup similar to before: 2 Bays X (4m), 1 Bay Y (5m)
    # But only drawing WALLS and DOORS. NO COLUMNS. NO BEAMS.
    
    wall_thick = 230
    half_wall = wall_thick / 2
    
    # Coordinates (mm)
    # Walls run along grid lines
    # Horizontal Walls
    for y in [0, 5000]:
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

    # Add a "Door"
    msp.add_circle((2000, 0), radius=450, dxfattribs={'layer': 'DOORS'})

    doc.saveas(filename)
    print(f"Successfully created: {filename}")
    print("Layers used: WALLS, DOORS (No Structural Layers)")

if __name__ == "__main__":
    create_arch_dxf()
