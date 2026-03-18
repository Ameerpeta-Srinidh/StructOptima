import ezdxf
from ezdxf.enums import TextEntityAlignment

def create_complex_arch_plan(filename="complex_mansion_arch.dxf"):
    doc = ezdxf.new()
    msp = doc.modelspace()

    # --- Layers ---
    doc.layers.new(name='WALLS', dxfattribs={'color': 7})   # White
    doc.layers.new(name='DOORS', dxfattribs={'color': 2})   # Yellow
    doc.layers.new(name='WINDOWS', dxfattribs={'color': 3}) # Green
    doc.layers.new(name='TEXT', dxfattribs={'color': 6})    # Magenta
    doc.layers.new(name='STAIRS', dxfattribs={'color': 1})  # Red
    doc.layers.new(name='FURNITURE', dxfattribs={'color': 8}) # Gray

    print(f"Generating Complex Architectural Plan: {filename}...")

    # --- Helper Functions ---
    def draw_wall(x1, y1, x2, y2, thickness=230):
        # Draw a rectangle representing the wall
        # Simplified: Just drawing the centerline or double box?
        # User wants "complex", so let's draw double lines (Outer/Inner)
        # But for Auto-Framer, simple centerlines or closed polylines are handled. 
        # Let's draw closed LWPolylines for walls to look solid.
        
        # Vector calculations for offset
        import math
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length == 0: return

        ux = dx / length
        uy = dy / length
        
        # Perpendicular vector
        px = -uy
        py = ux
        
        half = thickness / 2
        
        p1 = (x1 + px*half, y1 + py*half)
        p2 = (x2 + px*half, y2 + py*half)
        p3 = (x2 - px*half, y2 - py*half)
        p4 = (x1 - px*half, y1 - py*half)
        
        msp.add_lwpolyline([p1, p2, p3, p4], format='xy', close=True, dxfattribs={'layer': 'WALLS'})

    def draw_window(x, y, w, h, angle_deg=0):
        # Draw window symbol (Rectangle with mid line)
        # Center at x,y
        half_w = w/2
        half_h = h/2
        
        # Basic rect
        p1 = (x - half_w, y - half_h)
        p2 = (x + half_w, y - half_h)
        p3 = (x + half_w, y + half_h)
        p4 = (x - half_w, y + half_h)
        
        # Rotate points if needed (SKIP for simplicity, assumine aligned)
        if angle_deg == 90:
             p1 = (x - half_h, y - half_w)
             p2 = (x + half_h, y - half_w)
             p3 = (x + half_h, y + half_w)
             p4 = (x - half_h, y + half_w)
             # Mid line
             m1 = (x, y - half_w)
             m2 = (x, y + half_w)
        else:
             m1 = (x - half_w, y)
             m2 = (x + half_w, y)

        msp.add_lwpolyline([p1, p2, p3, p4], close=True, dxfattribs={'layer': 'WINDOWS'})
        msp.add_line(m1, m2, dxfattribs={'layer': 'WINDOWS'})

    def draw_door(x, y, width=900, angle=0):
        # Draw door arc + line
        # Simple representation
        pass # To be implemented inline or skipped for simple lines
    
    def add_text(text, x, y, height=300):
        msp.add_mtext(text, dxfattribs={'layer': 'TEXT', 'char_height': height}).set_location((x, y), attachment_point=5)

    # --- Layout Logic (20m x 15m) ---
    # Origin (0,0) bottom-left
    
    # 1. Main Outer Walls
    draw_wall(0, 0, 20000, 0)      # Bottom
    draw_wall(20000, 0, 20000, 15000) # Right
    draw_wall(20000, 15000, 0, 15000) # Top
    draw_wall(0, 15000, 0, 0)      # Left

    # 2. Internal Partition Walls
    # Central Hall (Living) - 8m wide, from X=6000 to X=14000
    draw_wall(6000, 0, 6000, 15000)  # Left Partition
    draw_wall(14000, 0, 14000, 15000) # Right Partition
    
    # Horizontal Partitions
    # Left Wing (Bedrooms)
    draw_wall(0, 5000, 6000, 5000)   # Bed 1 / Bath
    draw_wall(0, 10000, 6000, 10000) # Bath / Bed 2
    
    # Right Wing (Kitchen / Dining / Study)
    draw_wall(14000, 6000, 20000, 6000) # Kitchen / Dining
    draw_wall(14000, 11000, 20000, 11000) # Dining / Study

    # Toilet in Left Wing (Split middle room)
    draw_wall(3000, 5000, 3000, 10000) # Split Bath area

    # --- Room Labels ---
    add_text("MASTER BEDROOM\n(6m x 5m)", 3000, 12500)
    add_text("GUEST BEDROOM\n(6m x 5m)", 3000, 2500)
    add_text("TOILET 1", 1500, 7500, 200)
    add_text("TOILET 2", 4500, 7500, 200)
    
    add_text("GRAND LIVING HALL\n(8m x 15m)", 10000, 7500, 400)
    
    add_text("KITCHEN\n(6m x 6m)", 17000, 3000)
    add_text("DINING\n(6m x 5m)", 17000, 8500)
    add_text("STUDY / GYM\n(6m x 4m)", 17000, 13000)

    # --- Windows ---
    # Top Wall Windows
    draw_window(3000, 15000, 1500, 230)
    draw_window(10000, 15000, 2000, 230)
    draw_window(17000, 15000, 1500, 230)
    
    # Bottom Wall Windows
    draw_window(3000, 0, 1500, 230)
    draw_window(17000, 0, 1500, 230)
    
    # Side Windows
    draw_window(0, 2500, 230, 1500, 90)
    draw_window(0, 12500, 230, 1500, 90)
    draw_window(20000, 3000, 230, 1500, 90)
    draw_window(20000, 8500, 230, 1500, 90)

    # --- Doors (Represented as gaps or lines) ---
    # Entrance (Double Door)
    msp.add_line((9000, 0), (9000, -1000), dxfattribs={'layer': 'DOORS'})
    msp.add_line((11000, 0), (11000, -1000), dxfattribs={'layer': 'DOORS'})
    msp.add_arc((9000, 0), radius=1000, start_angle=270, end_angle=360, dxfattribs={'layer': 'DOORS'})
    msp.add_arc((11000, 0), radius=1000, start_angle=180, end_angle=270, dxfattribs={'layer': 'DOORS'})

    # Internal Doors
    # Bed 1 Door
    msp.add_line((6000, 2500), (6000-900, 2500-900), dxfattribs={'layer': 'DOORS'})
    
    # Staircase (Visual only)
    # Center of Hall
    sx, sy = 10000, 7500
    w, h = 3000, 2000
    msp.add_lwpolyline([(sx-w/2, sy-h/2), (sx+w/2, sy-h/2), (sx+w/2, sy+h/2), (sx-w/2, sy+h/2)], close=True, dxfattribs={'layer': 'STAIRS'})
    # Steps
    for i in range(10):
        step_x = (sx - w/2) + i * (w/10)
        msp.add_line((step_x, sy-h/2), (step_x, sy+h/2), dxfattribs={'layer': 'STAIRS'})

    doc.saveas(filename)
    print(f"Successfully created: {filename} (Complex Plan with Walls, Windows, Doors, Stairs)")

if __name__ == "__main__":
    create_complex_arch_plan()
