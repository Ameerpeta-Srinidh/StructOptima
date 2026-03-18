import ezdxf

def create_dxf_with_columns(filename="preplaced_columns.dxf"):
    doc = ezdxf.new()
    msp = doc.modelspace()

    # Define standard layers
    doc.layers.new(name='COLUMNS', dxfattribs={'color': 1}) # Red
    doc.layers.new(name='BEAMS', dxfattribs={'color': 5})   # Blue
    doc.layers.new(name='WALLS', dxfattribs={'color': 7})   # White/Black

    print(f"Generating {filename}...")

    col_size = 300 # mm
    half_col = col_size / 2
    wall_thick = 230
    half_wall = wall_thick / 2
    
    # 3x3 Grid of Columns
    x_coords = [0, 4000, 8000]
    y_coords = [0, 5000, 10000]

    # Create Walls
    for y in y_coords:
        y_top = y + half_wall
        y_bot = y - half_wall
        msp.add_line((0, y_top), (8000, y_top), dxfattribs={'layer': 'WALLS'})
        msp.add_line((0, y_bot), (8000, y_bot), dxfattribs={'layer': 'WALLS'})

    for x in x_coords:
        x_left = x - half_wall
        x_right = x + half_wall
        msp.add_line((x_left, 0), (x_left, 10000), dxfattribs={'layer': 'WALLS'})
        msp.add_line((x_right, 0), (x_right, 10000), dxfattribs={'layer': 'WALLS'})

    # Create Columns (LWPOLYLINE)
    for x in x_coords:
        for y in y_coords:
            x1, y1 = x - half_col, y - half_col
            x2, y2 = x + half_col, y - half_col
            x3, y3 = x + half_col, y + half_col
            x4, y4 = x - half_col, y + half_col
            
            msp.add_lwpolyline(
                [(x1, y1), (x2, y2), (x3, y3), (x4, y4), (x1, y1)], 
                dxfattribs={'layer': 'COLUMNS'}
            )

    # Create Beams (Lines)
    for y in y_coords:
        msp.add_line((0, y), (4000, y), dxfattribs={'layer': 'BEAMS'})
        msp.add_line((4000, y), (8000, y), dxfattribs={'layer': 'BEAMS'})

    for x in x_coords:
        msp.add_line((x, 0), (x, 5000), dxfattribs={'layer': 'BEAMS'})
        msp.add_line((x, 5000), (x, 10000), dxfattribs={'layer': 'BEAMS'})

    doc.saveas(filename)
    print(f"Successfully created: {filename} in {doc.filename}")
    print("Layers used: COLUMNS, BEAMS, WALLS")

if __name__ == "__main__":
    create_dxf_with_columns()
