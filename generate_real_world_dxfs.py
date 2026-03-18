import ezdxf
import os

class RealWorldDXFGenerator:
    def __init__(self, output_dir="real_world_dxfs"):
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
        # 1. Standard 3BHK Apartment (Approx 12x15m)
        # Living (5x6), Kit (3x4), Bed1 (4x4), Bed2 (3.5x4), Bed3 (3.5x3.5)
        # All dimensions in mm
        walls_1 = [
            # Outer Shell 12m x 15m
            ((0,0), (12000,0)), ((12000,0), (12000,15000)), 
            ((12000,15000), (0,15000)), ((0,15000), (0,0)),
            # Internal Dividing Walls
            # Central Hall vertical divide at x=5000
            ((5000,0), (5000,10000)), 
            # Kitchen/Dining horizontal at y=4000 (left side)
            ((0,4000), (5000,4000)),
            # Bedroom 1 (Master) top right 4x5m box: x=8000, y=10000
            ((8000,10000), (12000,10000)), ((8000,10000), (8000,15000)),
            # Bedroom 2 top left: x=5000, y=10000
            ((0,10000), (5000,10000)),
            # Toilets between beds?
            ((5000,10000), (8000,10000)),
            # Balcony attached to Hall (bottom right)
            ((5000,0), (8000,0)), ((8000,0), (8000,2000)), ((5000,2000), (8000,2000))
        ]
        self.create_dxf("real_1_3bhk_standard.dxf", walls_1, "Standard 3BHK Layout (12x15m)")

        # 2. Luxury 4BHK Villa (16x18m)
        # Large open span living, courtyard in middle?
        walls_2 = [
            # Outer
            ((0,0), (16000,0)), ((16000,0), (16000,18000)),
            ((16000,18000), (0,18000)), ((0,18000), (0,0)),
            # Central Courtyard (Open to sky, but walls around) - 4x4m in center
            # Center is 8,9. So 6,7 to 10,11
            ((6000,7000), (10000,7000)), ((10000,7000), (10000,11000)),
            ((10000,11000), (6000,11000)), ((6000,11000), (6000,7000)),
            # Cross walls
            ((0,7000), (6000,7000)), ((10000,7000), (16000,7000)),
            ((0,11000), (6000,11000)), ((10000,11000), (16000,11000)),
            # Vertical partitions
            ((8000,0), (8000,7000)), ((8000,11000), (8000,18000))
        ]
        self.create_dxf("real_2_4bhk_luxury_villa.dxf", walls_2, "Luxury 4BHK Villa with Courtyard")

        # 3. L-Shape Farmhouse (20x20m L)
        # Wing width 6m.
        walls_3 = [
            ((0,0), (20000,0)), ((20000,0), (20000,6000)), # Bottom leg outer
            ((20000,6000), (6000,6000)), # Inner corner horizontal
            ((6000,6000), (6000,20000)), # Inner corner vertical
            ((6000,20000), (0,20000)), ((0,20000), (0,0)), # Left leg outer
            # Internal partitions every 5m
            ((0,5000), (6000,5000)), ((0,10000), (6000,10000)), ((0,15000), (6000,15000)),
            ((5000,0), (5000,6000)), ((10000,0), (10000,6000)), ((15000,0), (15000,6000))
        ]
        self.create_dxf("real_3_l_shape_farmhouse.dxf", walls_3, "L-Shape Farmhouse (20x20m)")

        # 4. Duplex Ground Floor (Staircase + Double Height)
        # 10x12m. Staircase zone
        walls_4 = [
             ((0,0), (10000,0)), ((10000,0), (10000,12000)), 
             ((10000,12000), (0,12000)), ((0,12000), (0,0)),
             # Staircase well (2.5x5m) at right wall
             ((7500,4000), (10000,4000)), ((7500,4000), (7500,9000)), ((7500,9000), (10000,9000)),
             # Living Room (large span 7.5x6)
             ((0,6000), (7500,6000))
        ]
        self.create_dxf("real_4_duplex_ground.dxf", walls_4, "Duplex Ground Floor with Staircase")

        # 5. Irregular Plot (Trapezoid)
        # (0,0) -> (15000,0) -> (15000,10000) -> (5000,12000) -> (0,0)
        # Skewed top wall
        walls_5 = [
            ((0,0), (15000,0)), ((15000,0), (15000,10000)),
            ((15000,10000), (5000,12000)), # Slanted
            ((5000,12000), (0,0)), # Slanted
            # Internal orthogonal walls
            ((5000,0), (5000,5000)), ((5000,5000), (15000,5000)),
            ((5000,5000), (5000,12000)) # Meets slanted wall
        ]
        self.create_dxf("real_5_irregular.dxf", walls_5, "Irregular Trapezoidal Plot")

if __name__ == "__main__":
    gen = RealWorldDXFGenerator()
    gen.generate_all()
