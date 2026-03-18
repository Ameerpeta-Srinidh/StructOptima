
"""
Site Guide Module
Contains static content and checklists for construction site execution
based on IS 456, IS 13920, and best practices.
"""

SITE_CHECKLISTS = {
    "Formwork & Preparation": """
### 🏗️ Phase 2: Formwork & Preparation CHECKLIST
**Reference: IS 456:2000 Cl. 11**

- [ ] **Surface Cleaning**: Are inner faces of forms free from sawdust, chippings, and nails?
- [ ] **Release Agent**: Has release agent (oil/grease) been applied *before* rebar placement?
- [ ] **Watertightness**: Are joints tight to prevent cement slurry loss (honeycombing risk)?
- [ ] **Dimensions**: Is deviation within **+12mm / -6mm** of drawing dimensions?
- [ ] **Props**: are props vertical and resting on firm ground/sole plates?
""",

    "Reinforcement (BBS)": """
### 🔗 Phase 3: Reinforcement Placement CHECKLIST
**Reference: IS 456 & IS 13920 (Seismic)**

- [ ] **Cover Blocks**: Are cover spacers (25mm for beams) placed at max **1.0m spacing**?
- [ ] **Plumb**: Is the cage vertically/horizontally aligned?
- [ ] **Cleanliness**: Is rebar free from loose rust, oil, mud, or paint?
- [ ] **Seismic Hooks**: Do stirrups have **135° hooks** with **6d extension** (>65mm)?
- [ ] **Spacing**: Is stirrup spacing closer (2d) near supports (Plastic Hinge Zone)?
- [ ] **Lapping**: Are laps staggered and NOT in the tension zone or joints?
- [ ] **Tying**: Are all crossing bars tied with binding wire? (NO TACK WELDING allowed).
""",

    "Concreting": """
### 🚛 Phase 4: Concreting (Pouring & Compaction)
**Reference: IS 456 Cl. 13**

- [ ] **Free Fall**: Is pouring height **< 1.5m** to prevent segregation?
- [ ] **Vibration**: Is a mechanical needle vibrator available and working?
- [ ] **Continuity**: Is the pour continuous? If stopped, is the joint vertical and at 1/3 span?
- [ ] **Slump**: Is the workability appropriate (Slump check)?
- [ ] **Cubes**: Have 6 cubes been cast for strength testing (7-day & 28-day)?
""",

    "Curing & Stripping": """
### 💦 Phase 5: Curing & Stripping
**Reference: IS 456 Cl. 13.5**

- [ ] **Curing Start**: Has wet curing started immediately after initial set?
- [ ] **Duration**: Keep wet for **min 7 days** (OPC) or **10 days** (Fly Ash/PPC).
- [ ] **Stripping Time**:
    - Beam Sides: 16-24 Hours
    - Beam Soffits (Bottoms): 7 Days (Props refixed immediately)
    - Removal of Props: 14 Days (<6m span) / 21 Days (>6m span)
"""
}

def get_site_guide_markdown():
    """Returns the full combined guide."""
    return "\n---\n".join(SITE_CHECKLISTS.values())
