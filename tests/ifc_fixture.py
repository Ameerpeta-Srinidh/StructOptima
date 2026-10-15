"""Builds a tiny two-storey IFC4 frame for BIM loader tests (requires ifcopenshell)."""
import numpy as np
import ifcopenshell
import ifcopenshell.api


def build_frame_ifc(path: str, unit_mm: bool = True) -> None:
    """2 storeys x 3.5 m, 4 columns 300x450 at (0,0) (4.5,0) (0,4) (4.5,4) m,
    4 perimeter beams 230x400 per storey.  Geometry depths are passed to the
    ifcopenshell API in SI metres (the API converts to project units)."""
    f = ifcopenshell.file(schema="IFC4")
    project = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="Test")
    unit = ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT", prefix="MILLI") if unit_mm \
        else ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", f, units=[unit])
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", f, context_type="Model", context_identifier="Body",
                                target_view="MODEL_VIEW", parent=ctx)
    site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite", name="Site")
    bldg = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name="B")
    ifcopenshell.api.run("aggregate.assign_object", f, relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", f, relating_object=site, products=[bldg])
    s = 1000.0 if unit_mm else 1.0
    H = 3.5
    storeys = []
    for i in range(2):
        st = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name=f"L{i}")
        ifcopenshell.api.run("aggregate.assign_object", f, relating_object=bldg, products=[st])
        m = np.eye(4)
        m[2, 3] = i * H * s
        ifcopenshell.api.run("geometry.edit_object_placement", f, product=st, matrix=m, is_si=False)
        storeys.append(st)
    col_prof = f.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=0.3 * s, YDim=0.45 * s)
    beam_prof = f.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=0.23 * s, YDim=0.40 * s)
    pts = [(0, 0), (4.5, 0), (0, 4.0), (4.5, 4.0)]
    for i, st in enumerate(storeys):
        for (x, y) in pts:
            c = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcColumn")
            rep = ifcopenshell.api.run("geometry.add_profile_representation", f, context=body, profile=col_prof, depth=H)
            ifcopenshell.api.run("geometry.assign_representation", f, product=c, representation=rep)
            m = np.eye(4)
            m[0, 3], m[1, 3], m[2, 3] = x * s, y * s, i * H * s
            ifcopenshell.api.run("geometry.edit_object_placement", f, product=c, matrix=m, is_si=False)
            ifcopenshell.api.run("spatial.assign_container", f, relating_structure=st, products=[c])
        for (a, b) in [((0, 0), (4.5, 0)), ((0, 4.0), (4.5, 4.0)), ((0, 0), (0, 4.0)), ((4.5, 0), (4.5, 4.0))]:
            bm = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBeam")
            L = float(np.hypot(b[0] - a[0], b[1] - a[1]))
            rep = ifcopenshell.api.run("geometry.add_profile_representation", f, context=body, profile=beam_prof, depth=L)
            ifcopenshell.api.run("geometry.assign_representation", f, product=bm, representation=rep)
            d = np.array([b[0] - a[0], b[1] - a[1], 0.0])
            d /= np.linalg.norm(d)
            xax = np.array([0, 0, 1.0])
            m = np.eye(4)
            m[:3, 0], m[:3, 1], m[:3, 2] = xax, np.cross(d, xax), d
            m[0, 3], m[1, 3], m[2, 3] = a[0] * s, a[1] * s, (i + 1) * H * s
            ifcopenshell.api.run("geometry.edit_object_placement", f, product=bm, matrix=m, is_si=False)
            ifcopenshell.api.run("spatial.assign_container", f, relating_structure=st, products=[bm])
    f.write(path)
