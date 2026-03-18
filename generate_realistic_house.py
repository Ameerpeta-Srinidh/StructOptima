"""
Generate a realistic complex Indian residential house floor plan (G+2).
Based on typical 40ft x 60ft (12m x 18m) plot with setbacks.

This creates a proper architectural DXF that tests the auto-framer with:
- Multiple rooms with varying sizes
- L-shaped and irregular wall configurations
- Internal partition walls
- Staircase enclosure
- Balconies and cantilevers
"""

import ezdxf

def create_complex_house_dxf(filename):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    for layer_name in ['WALLS', 'DOORS', 'WINDOWS', 'STAIRS', 'TEXT']:
        doc.layers.add(layer_name)
    
    WALL_THICK = 230
    HT = WALL_THICK / 2
    
    def draw_wall(x1, y1, x2, y2):
        """Draw double-line wall (architectural style)"""
        dx = x2 - x1
        dy = y2 - y1
        length = (dx**2 + dy**2)**0.5
        if length == 0:
            return
        
        nx = -dy / length * HT
        ny = dx / length * HT
        
        msp.add_line((x1 + nx, y1 + ny), (x2 + nx, y2 + ny), dxfattribs={'layer': 'WALLS'})
        msp.add_line((x1 - nx, y1 - ny), (x2 - nx, y2 - ny), dxfattribs={'layer': 'WALLS'})
        msp.add_line((x1 + nx, y1 + ny), (x1 - nx, y1 - ny), dxfattribs={'layer': 'WALLS'})
        msp.add_line((x2 + nx, y2 + ny), (x2 - nx, y2 - ny), dxfattribs={'layer': 'WALLS'})
    
    PLOT_W = 12000
    PLOT_L = 18000
    SETBACK_FRONT = 1500
    SETBACK_BACK = 1000
    SETBACK_SIDE = 750
    
    BUILD_W = PLOT_W - 2 * SETBACK_SIDE 
    BUILD_L = PLOT_L - SETBACK_FRONT - SETBACK_BACK
    
    OX = SETBACK_SIDE
    OY = SETBACK_BACK
    
    print(f"Building: {BUILD_W}mm x {BUILD_L}mm = {BUILD_W/1000}m x {BUILD_L/1000}m")
    print(f"Origin at: ({OX}, {OY})")
    
    draw_wall(OX, OY, OX + BUILD_W, OY)
    draw_wall(OX + BUILD_W, OY, OX + BUILD_W, OY + BUILD_L)
    draw_wall(OX + BUILD_W, OY + BUILD_L, OX, OY + BUILD_L)
    draw_wall(OX, OY + BUILD_L, OX, OY)
    
    LIVING_W = 4500
    LIVING_L = 5000
    draw_wall(OX, OY + LIVING_L, OX + LIVING_W, OY + LIVING_L)
    draw_wall(OX + LIVING_W, OY, OX + LIVING_W, OY + LIVING_L)
    
    DINING_W = BUILD_W - LIVING_W
    DINING_L = 4000
    draw_wall(OX + LIVING_W, OY + DINING_L, OX + BUILD_W, OY + DINING_L)
    
    KITCHEN_L = 3500
    draw_wall(OX + LIVING_W, OY + DINING_L, OX + LIVING_W, OY + DINING_L + KITCHEN_L)
    draw_wall(OX + LIVING_W, OY + DINING_L + KITCHEN_L, OX + BUILD_W, OY + DINING_L + KITCHEN_L)
    
    STAIR_W = 2500
    STAIR_L = 3000
    STAIR_X = OX + LIVING_W - STAIR_W
    STAIR_Y = OY + LIVING_L
    
    draw_wall(STAIR_X, STAIR_Y, STAIR_X + STAIR_W, STAIR_Y)
    draw_wall(STAIR_X + STAIR_W, STAIR_Y, STAIR_X + STAIR_W, STAIR_Y + STAIR_L)
    draw_wall(STAIR_X + STAIR_W, STAIR_Y + STAIR_L, STAIR_X, STAIR_Y + STAIR_L)
    draw_wall(STAIR_X, STAIR_Y + STAIR_L, STAIR_X, STAIR_Y)
    
    BED1_START_Y = OY + LIVING_L + STAIR_L
    BED1_W = LIVING_W
    BED1_L = BUILD_L - LIVING_L - STAIR_L
    
    draw_wall(OX, BED1_START_Y, OX + BED1_W, BED1_START_Y)
    
    TOILET_W = 1800
    TOILET1_X = OX + BED1_W - TOILET_W
    draw_wall(TOILET1_X, BED1_START_Y, TOILET1_X, OY + BUILD_L - 1500)
    
    BED2_START_Y = OY + DINING_L + KITCHEN_L
    BED2_W = DINING_W
    
    TOILET2_X = OX + BUILD_W - TOILET_W
    draw_wall(TOILET2_X, BED2_START_Y, TOILET2_X, OY + BUILD_L - 1500)
    
    BALCONY_DEPTH = 1200
    BALCONY_Y = OY + BUILD_L
    draw_wall(OX + 1000, BALCONY_Y, OX + 1000, BALCONY_Y + BALCONY_DEPTH)
    draw_wall(OX + 1000, BALCONY_Y + BALCONY_DEPTH, OX + 3500, BALCONY_Y + BALCONY_DEPTH)
    draw_wall(OX + 3500, BALCONY_Y + BALCONY_DEPTH, OX + 3500, BALCONY_Y)
    
    msp.add_text("LIVING ROOM", dxfattribs={'layer': 'TEXT', 'height': 200}).set_placement(
        (OX + LIVING_W/2 - 500, OY + LIVING_L/2))
    msp.add_text("DINING", dxfattribs={'layer': 'TEXT', 'height': 200}).set_placement(
        (OX + LIVING_W + DINING_W/2 - 300, OY + DINING_L/2))
    msp.add_text("KITCHEN", dxfattribs={'layer': 'TEXT', 'height': 200}).set_placement(
        (OX + LIVING_W + DINING_W/2 - 300, OY + DINING_L + KITCHEN_L/2))
    msp.add_text("STAIRCASE", dxfattribs={'layer': 'TEXT', 'height': 150}).set_placement(
        (STAIR_X + 200, STAIR_Y + STAIR_L/2))
    msp.add_text("BEDROOM 1", dxfattribs={'layer': 'TEXT', 'height': 200}).set_placement(
        (OX + 800, BED1_START_Y + BED1_L/2))
    msp.add_text("BEDROOM 2", dxfattribs={'layer': 'TEXT', 'height': 200}).set_placement(
        (OX + LIVING_W + 800, BED2_START_Y + 1500))
    msp.add_text("BALCONY", dxfattribs={'layer': 'TEXT', 'height': 150}).set_placement(
        (OX + 1800, BALCONY_Y + 400))

    doc.saveas(filename)
    print(f"\nSaved: {filename}")
    
    return {
        'build_w': BUILD_W,
        'build_l': BUILD_L,
        'origin': (OX, OY),
        'rooms': ['Living Room', 'Dining', 'Kitchen', 'Staircase', 'Bedroom 1', 'Bedroom 2', 'Toilets', 'Balcony']
    }

if __name__ == '__main__':
    info = create_complex_house_dxf('realistic_indian_house.dxf')
    print(f"\nBuilding dimensions: {info['build_w']/1000}m x {info['build_l']/1000}m")
    print(f"Rooms: {', '.join(info['rooms'])}")
