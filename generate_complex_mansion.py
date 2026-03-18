import ezdxf

def create_mansion_dxf(filename="complex_mansion.dxf"):
    doc = ezdxf.new()
    msp = doc.modelspace()

    # Layers
    doc.layers.new(name='COLUMNS', dxfattribs={'color': 1}) # Red
    doc.layers.new(name='BEAMS', dxfattribs={'color': 3})   # Green
    doc.layers.new(name='WALLS', dxfattribs={'color': 7})   # White
    doc.layers.new(name='SLABS', dxfattribs={'color': 4})   # Cyan

    print(f"Generating Complex Mansion: {filename}...")

    # Mansion Layout: 20m x 15m
    # Grid: 5m spacing X, 5m spacing Y
    # X Grids: 0, 5000, 10000, 15000, 20000
    # Y Grids: 0, 5000, 10000, 15000

    col_size = 300 # 300x300mm columns
    
    # Helper to draw column (center coords)
    def add_column(cx, cy):
        half = col_size / 2
        pts = [
            (cx-half, cy-half),
            (cx+half, cy-half),
            (cx+half, cy+half),
            (cx-half, cy+half)
        ]
        # CLOSED polyline
        msp.add_lwpolyline(pts, format='xy', close=True, dxfattribs={'layer': 'COLUMNS'})

    # Helper to draw beam
    def add_beam(x1, y1, x2, y2):
        msp.add_line((x1, y1), (x2, y2), dxfattribs={'layer': 'BEAMS'})
        
    # Helper to draw wall (double line) - Simplified as single line for now or matching beam
    def add_wall(x1, y1, x2, y2):
        msp.add_line((x1, y1), (x2, y2), dxfattribs={'layer': 'WALLS'})

    # Generate Grid
    x_grids = [0, 5000, 10000, 15000, 20000]
    y_grids = [0, 5000, 10000, 15000]

    # Add Columns at Intersections
    # Skip some to create "Large Hall" or "Balcony" feel
    # Let's verify structure: Full grid
    for x in x_grids:
        for y in y_grids:
            # Skip (10000, 5000) and (10000, 10000) to make large hall?
            # No, let's keep it regular for seismic stability first
            add_column(x, y)

    # Add Beams (Grid frame)
    # Horizontal
    for y in y_grids:
        for i in range(len(x_grids)-1):
            add_beam(x_grids[i], y, x_grids[i+1], y)
            
    # Vertical
    for x in x_grids:
        for i in range(len(y_grids)-1):
            add_beam(x, y_grids[i], x, y_grids[i+1])

    doc.saveas(filename)
    print(f"Successfully created: {filename} with COLUMNS and BEAMS layers.")

if __name__ == "__main__":
    create_mansion_dxf()
