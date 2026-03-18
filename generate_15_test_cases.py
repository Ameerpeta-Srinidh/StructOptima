import ezdxf
import os

class DXFGenerator:
    def __init__(self, output_dir="test_dxfs"):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.output_dir = output_dir

    def create_dxf(self, filename, walls, description):
        doc = ezdxf.new()
        msp = doc.modelspace()
        
        # Layers
        doc.layers.new(name='WALLS', dxfattribs={'color': 7})
        doc.layers.new(name='ANNOTATION', dxfattribs={'color': 3})
        
        # Draw Walls
        # walls is list of ((x1, y1), (x2, y2))
        for start, end in walls:
            msp.add_line(start, end, dxfattribs={'layer': 'WALLS'})
            
        # Add description text
        msp.add_text(description, dxfattribs={
            'height': 250, 
            'layer': 'ANNOTATION',
            'insert': (0, -1000)
        })
        
        filepath = os.path.join(self.output_dir, filename)
        doc.saveas(filepath)
        print(f"Generated {filepath}: {description}")
        return filepath

    def generate_all(self):
        # 1. Small Rectangle (6m x 8m)
        self.create_dxf("case_01_small_rect.dxf", [
            ((0,0), (6000,0)), ((6000,0), (6000,8000)), 
            ((6000,8000), (0,8000)), ((0,8000), (0,0))
        ], "Small Rectangle 6x8m")

        # 2. Medium Rectangle (10m x 12m) with cross wall
        self.create_dxf("case_02_medium_rect.dxf", [
            ((0,0), (10000,0)), ((10000,0), (10000,12000)), 
            ((10000,12000), (0,12000)), ((0,12000), (0,0)),
            ((0, 6000), (10000, 6000)), # Horiz mid
            ((5000, 0), (5000, 12000)) # Vert mid
        ], "Medium Rect 10x12m with cross walls")

        # 3. Large Rect (20m x 30m) - Large Grid
        walls_03 = [((0,0), (20000,0)), ((20000,0), (20000,30000)), 
                    ((20000,30000), (0,30000)), ((0,30000), (0,0))]
        # Add internal grid walls every 5m/6m
        for x in [5000, 10000, 15000]:
            walls_03.append(((x,0), (x,30000)))
        for y in [6000, 12000, 18000, 24000]:
            walls_03.append(((0,y), (20000,y)))
        self.create_dxf("case_03_large_grid.dxf", walls_03, "Large Grid 20x30m")

        # 4. L-Shape
        # Main: 0,0 to 12,0 to 12,10 to 6,10 to 6,5 to 0,5 to 0,0
        # Actually (0,0) -> (12,0) -> (12,10) -> (0,10) with cut out (0,5) to (6,10) NO
        # Vert: left 0->10, right 12->0. Top 0->12. Bot... L shape
        # Let's do: (0,0) -> (12000,0) -> (12000, 5000) -> (5000, 5000) -> (5000, 10000) -> (0, 10000) -> (0,0)
        walls_04 = [
            ((0,0), (12000,0)), ((12000,0), (12000,5000)), 
            ((12000,5000), (5000,5000)), ((5000,5000), (5000,10000)), 
            ((5000,10000), (0,10000)), ((0,10000), (0,0))
        ]
        self.create_dxf("case_04_l_shape.dxf", walls_04, "L-Shape Building")

        # 5. C-Shape (Courtyard)
        # Outer: 15x15. Inner cutout 5x5 from one side?
        # Outer box (0,0) to (15,15). Inner Courtyard (5,0) to (10,5) open? 
        # C Shape: Open to Right
        # (0,0)->(10000,0)->(10000,5000)->(5000,5000)->(5000,10000)->(10000,10000)->(10000,15000)->(0,15000)->(0,0)
        walls_05 = [
            ((0,0), (10000,0)), ((10000,0), (10000,5000)), 
            ((10000,5000), (5000,5000)), ((5000,5000), (5000,10000)),
            ((5000,10000), (10000,10000)), ((10000,10000), (10000,15000)),
            ((10000,15000), (0,15000)), ((0,15000), (0,0))
        ]
        self.create_dxf("case_05_c_shape.dxf", walls_05, "C-Shape / Courtyard")

        # 6. T-Shape
        # Top Bar: 15x5, Stem: 5x10
        # (0,10)-(15,10)-(15,15)-(0,15)-(0,10) top bar
        # (5,0)-(10,0)-(10,10)...(5,10)-(5,0) stem
        walls_06 = [
            ((0,10000), (15000,10000)), ((15000,10000), (15000,15000)),
            ((15000,15000), (0,15000)), ((0,15000), (0,10000)),
            ((5000,0), (10000,0)), ((10000,0), (10000,10000)), ((5000,10000), (5000,0))
        ]
        self.create_dxf("case_06_t_shape.dxf", walls_06, "T-Shape Building")

        # 7. H-Shape
        # Left wing 5x20, Right wing 5x20, Bridge 5x5 in middle
        # Left: (0,0)-(5,0)-(5,20)-(0,20)-(0,0)
        # Right: (10,0)-(15,0)-(15,20)-(10,20)-(10,0)
        # Bridge: (5,7.5)-(10,7.5), (5,12.5)-(10,12.5)
        walls_07 = [
            ((0,0), (5000,0)), ((5000,0), (5000,20000)), ((5000,20000), (0,20000)), ((0,20000), (0,0)), # Left
            ((10000,0), (15000,0)), ((15000,0), (15000,20000)), ((15000,20000), (10000,20000)), ((10000,20000), (10000,0)), # Right
            ((5000,8000), (10000,8000)), ((5000,12000), (10000,12000)) # Bridge walls
        ]
        self.create_dxf("case_07_h_shape.dxf", walls_07, "H-Shape Building")

        # 8. Long Narrow (Row House)
        # 5m x 20m
        walls_08 = [
            ((0,0), (5000,0)), ((5000,0), (5000,20000)), 
            ((5000,20000), (0,20000)), ((0,20000), (0,0)),
            ((0,5000), (5000,5000)), ((0,10000), (5000,10000)), ((0,15000), (5000,15000))
        ]
        self.create_dxf("case_08_long_narrow.dxf", walls_08, "Long Narrow 5x20m")

        # 9. Small Rooms Cluster
        # 9x9m outer, divided into 9 3x3 rooms
        walls_09 = [((0,0), (9000,0)), ((9000,0), (9000,9000)), ((9000,9000), (0,9000)), ((0,9000), (0,0))]
        for i in [3000, 6000]:
            walls_09.append(((i,0), (i,9000))) # Vert
            walls_09.append(((0,i), (9000,i))) # Horiz
        self.create_dxf("case_09_small_rooms.dxf", walls_09, "Small Rooms 3x3m Cluster")

        # 10. Open Hall (Gap Fill Test)
        # 15m x 15m No internal walls
        walls_10 = [
            ((0,0), (15000,0)), ((15000,0), (15000,15000)), 
            ((15000,15000), (0,15000)), ((0,15000), (0,0))
        ]
        self.create_dxf("case_10_open_hall.dxf", walls_10, "Open Hall 15x15m (Gap Fill)")

        # 11. Balcony House
        # Core 10x10, Balcony 1.5m offset all sides (or 2 sides)
        # Core: (1500,1500) to (11500,11500)
        # Balcony: (0,0) to (13000,13000)? 
        # Balcony usually just floor/railing, but here represented as wall for boundary?
        # Let's say Balcony is envelope line.
        # Core walls
        walls_11 = [
            ((1500,1500), (11500,1500)), ((11500,1500), (11500,11500)), 
            ((11500,11500), (1500,11500)), ((1500,11500), (1500,1500)),
            # Balcony edges (represented as walls for parser)
            ((0,0), (13000,0)), ((13000,0), (13000,13000)),
            ((13000,13000), (0,13000)), ((0,13000), (0,0))
        ]
        self.create_dxf("case_11_balcony.dxf", walls_11, "House with 1.5m Perimeter Balcony")

        # 12. Corridor Plan
        # 8m x 15m. Central corridor 2m wide.
        # Outer
        walls_12 = [((0,0), (8000,0)), ((8000,0), (8000,15000)), ((8000,15000), (0,15000)), ((0,15000), (0,0))]
        # Corridor at x=3000 to x=5000
        walls_12.append(((3000,0), (3000,15000)))
        walls_12.append(((5000,0), (5000,15000)))
        self.create_dxf("case_12_corridor.dxf", walls_12, "Corridor Plan")

        # 13. Large Span + Short Span Mix
        # 10x10 room next to 2x2 toilet
        walls_13 = [
            ((0,0), (10000,0)), ((10000,0), (10000,10000)), ((10000,10000), (0,10000)), ((0,10000), (0,0)), # Big room
            ((10000,0), (12000,0)), ((12000,0), (12000,2000)), ((12000,2000), (10000,2000)) # Toilet extension
        ]
        self.create_dxf("case_13_mixed_spans.dxf", walls_13, "Mixed Large and Short Spans")

        # 14. Zig-Zag / Stepped
        # (0,0)-(5,0)-(5,5)-(10,5)-(10,10)-(15,10)-(15,15)-...
        walls_14 = [
             ((0,0), (5000,0)), ((5000,0), (5000,5000)), ((5000,5000), (10000,5000)),
             ((10000,5000), (10000,10000)), ((10000,10000), (0,10000)), ((0,10000), (0,0))
        ] 
        self.create_dxf("case_14_stepped.dxf", walls_14, "Stepped Building")

        # 15. The Real Villa (copy logic or simplified version)
        # Using the complex villa logic roughly
        walls_15 = [
            ((-1500,-115), (19500,-115)), # Bottom
            ((-1500,-115), (-1500,13500)), # Left
            ((-1500,13500), (19500,13500)), # Top
            ((19500,13500), (19500,-115)), # Right
            # Inner Main
            ((0,0), (18000,0)),
            ((0,0), (0,12000)),
            ((18000,0), (18000,12000)),
            ((0,12000), (18000,12000))
        ]
        self.create_dxf("case_15_complex_villa_sim.dxf", walls_15, "Complex Villa Simulation")


if __name__ == "__main__":
    gen = DXFGenerator()
    gen.generate_all()
