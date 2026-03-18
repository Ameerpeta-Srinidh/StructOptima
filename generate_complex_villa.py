"""
Generate a complex multi-room building DXF for testing column placement.

Features:
- Main hall area
- Multiple bedrooms
- Kitchen and living areas  
- Balconies on 3 sides
- L-shaped corridor
- Stairwell core
- Bathroom blocks
"""

import ezdxf

def generate_complex_building():
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    doc.layers.add('WALLS', color=7)
    
    outer_walls = [
        ((0, 0), (18000, 0)),
        ((18000, 0), (18000, 12000)),
        ((18000, 12000), (0, 12000)),
        ((0, 12000), (0, 0)),
    ]
    
    for start, end in outer_walls:
        msp.add_line(start, end, dxfattribs={'layer': 'WALLS'})
        offset = 230
        if start[0] == end[0]:
            msp.add_line((start[0]-offset, start[1]), (end[0]-offset, end[1]), dxfattribs={'layer': 'WALLS'})
        else:
            msp.add_line((start[0], start[1]-offset), (end[0], end[1]-offset), dxfattribs={'layer': 'WALLS'})
    
    internal_walls = [
        ((6000, 0), (6000, 5000)),
        ((6000, 5000), (0, 5000)),
        
        ((6000, 7000), (0, 7000)),
        ((6000, 7000), (6000, 12000)),
        
        ((12000, 0), (12000, 5000)),
        ((12000, 5000), (6000, 5000)),
        
        ((12000, 7000), (6000, 7000)),
        ((12000, 7000), (12000, 12000)),
        
        ((6000, 5000), (6000, 7000)),
        
        ((15000, 0), (15000, 5000)),
        ((15000, 5000), (18000, 5000)),
        
        ((15000, 7000), (18000, 7000)),
        ((15000, 7000), (15000, 12000)),
        
        ((12000, 5000), (12000, 7000)),
        ((15000, 5000), (15000, 7000)),
        
        ((3000, 5000), (3000, 7000)),
        
        ((13500, 5000), (13500, 7000)),
    ]
    
    for start, end in internal_walls:
        msp.add_line(start, end, dxfattribs={'layer': 'WALLS'})
    
    balcony_walls = [
        ((-1500, 2000), (-1500, 5000)),
        ((-1500, 2000), (0, 2000)),
        ((-1500, 5000), (0, 5000)),
        
        ((-1500, 7000), (-1500, 10000)),
        ((-1500, 7000), (0, 7000)),
        ((-1500, 10000), (0, 10000)),
        
        ((18000, 2000), (19500, 2000)),
        ((19500, 2000), (19500, 5000)),
        ((19500, 5000), (18000, 5000)),
        
        ((18000, 7000), (19500, 7000)),
        ((19500, 7000), (19500, 10000)),
        ((19500, 10000), (18000, 10000)),
        
        ((6000, 12000), (6000, 13500)),
        ((6000, 13500), (12000, 13500)),
        ((12000, 13500), (12000, 12000)),
    ]
    
    for start, end in balcony_walls:
        msp.add_line(start, end, dxfattribs={'layer': 'WALLS'})
    
    stair_walls = [
        ((12500, 5500), (12500, 6500)),
        ((12500, 5500), (14500, 5500)),
        ((14500, 5500), (14500, 6500)),
        ((14500, 6500), (12500, 6500)),
    ]
    
    for start, end in stair_walls:
        msp.add_line(start, end, dxfattribs={'layer': 'WALLS'})
    
    filename = 'complex_villa.dxf'
    doc.saveas(filename)
    print(f"Generated {filename}")
    return filename

if __name__ == "__main__":
    generate_complex_building()
