#!/usr/bin/env python3
"""
Tilted desk stand for the Noritake CU20029ECPB-W1J VFD (146 x 43 mm module).

One module holds one display. Print it twice and bolt the two side by side
through the inner gussets (2x M3x10 + nuts) - left channel + right channel.
The whole two-display stand (~310 mm) would not fit a typical print bed.

Generates stand_vfd.stl. Edit the parameters below and re-run:
    pip install trimesh manifold3d
    python make_stand_vfd.py

Print on its side (one gusset flat on the bed) - no supports needed.
"""

import math
import numpy as np
import trimesh
from trimesh.creation import extrude_polygon, cylinder
from shapely.geometry import Polygon, box

# ---- VFD module (datasheet CU20029ECPB) -------------------------------------
PCB_W = 146.0     # PCB width
PCB_H = 43.0      # PCB height
HOLE_DX = 139.0   # mounting hole spacing, horizontal
HOLE_DZ = 36.0    # mounting hole spacing, vertical
HOLE_D = 2.2      # M2.5 self-tapping into plastic (2.8 = clearance + nut)

# 2x7 header at the left edge (seen from the front), pins 1.7-5.3 mm from the edge
CONN_X = 9.0      # slot width from the PCB's left edge
CONN_H = 24.0     # slot height, centred vertically

# ---- stand -----------------------------------------------------------------
TILT = 25.0       # degrees back from vertical
MARGIN = 4.0      # frame border outside the PCB (2x MARGIN = gap between displays)
T = 3.0           # frame plate thickness
RIM = 8.0         # window rim measured from the PCB edge (carries the standoffs)
SPACER_H = 5.0    # standoff height (clears parts on the back of the PCB)
SPACER_D = 6.5
DEPTH = 60.0      # footprint depth behind the frame
GUSSET_T = 4.0
BAR_H = 8.0
CORNER_R = 3.0
JOIN_D = 3.4      # M3 clearance for joining two modules
SEGS = 48

W = PCB_W + 2 * MARGIN
H = PCB_H + 2 * MARGIN


def rounded_rect(w, h, r, cx=0.0, cy=0.0):
    return box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2).buffer(
        -r).buffer(r, join_style=1, resolution=8) if r > 0 else box(
        cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def frame_local():
    """Frame plate in the XZ plane, thickness along +Y (Y=0 is the front)."""
    outline = rounded_rect(W, H, CORNER_R, W / 2, H / 2)
    window = rounded_rect(PCB_W - 2 * RIM, PCB_H - 2 * RIM, 3.0, W / 2, H / 2)
    # slot behind the 2x7 header so the ribbon plugs in from the back
    slot = box(MARGIN + 0.5, H / 2 - CONN_H / 2, MARGIN + RIM + 2, H / 2 + CONN_H / 2)
    slot = slot.union(box(MARGIN + 0.5, H / 2 - CONN_H / 2, MARGIN + CONN_X, H / 2 + CONN_H / 2))
    plate2d = outline.difference(window).difference(slot)

    plate = extrude_polygon(plate2d, T)                  # extruded along +Z
    plate.apply_transform(trimesh.transformations.rotation_matrix(
        math.pi / 2, [1, 0, 0]))                         # XY -> XZ, thickness -> -Y
    plate.apply_translation([0, T, 0])                   # front face at Y=0

    holes = [(W / 2 + sx * HOLE_DX / 2, H / 2 + sz * HOLE_DZ / 2)
             for sx in (-1, 1) for sz in (-1, 1)]

    parts = [plate]
    for hx, hz in holes:
        sp = cylinder(radius=SPACER_D / 2, height=SPACER_H + 0.01, sections=SEGS)
        sp.apply_transform(trimesh.transformations.rotation_matrix(
            math.pi / 2, [1, 0, 0]))
        sp.apply_translation([hx, -SPACER_H / 2, hz])
        parts.append(sp)
    solid = trimesh.boolean.union(parts, engine="manifold")

    drills = []
    for hx, hz in holes:
        d = cylinder(radius=HOLE_D / 2, height=SPACER_H + T + 2, sections=SEGS)
        d.apply_transform(trimesh.transformations.rotation_matrix(
            math.pi / 2, [1, 0, 0]))
        d.apply_translation([hx, (T - SPACER_H) / 2, hz])
        drills.append(d)
    return trimesh.boolean.difference([solid] + drills, engine="manifold")


def tilt_matrix():
    # lean the top back: rotate about X so +Z tips toward +Y
    return trimesh.transformations.rotation_matrix(
        -math.radians(TILT), [1, 0, 0])


def gusset_profile():
    """Side gusset outline in the (Y, Z) plane."""
    t = math.radians(TILT)
    # back face of the frame plate after tilting
    yb0 = T * math.cos(t)
    top = 0.8 * H
    e = (yb0 + top * math.sin(t), top * math.cos(t))

    c = (yb0 + DEPTH, BAR_H)
    ctrl = (yb0 + DEPTH * 0.2, BAR_H + 2)
    curve = []
    for i in range(25):
        s = i / 24
        y = (1 - s) ** 2 * c[0] + 2 * (1 - s) * s * ctrl[0] + s ** 2 * e[0]
        z = (1 - s) ** 2 * c[1] + 2 * (1 - s) * s * ctrl[1] + s ** 2 * e[1]
        curve.append((y, z))

    # overlap 1 mm into the plate so the union is watertight
    inner = [(yb0 - 1.0 + top * math.sin(t), top * math.cos(t)),
             (yb0 - 1.0, 0)]
    return Polygon([(yb0 - 1.0, 0), (yb0 + DEPTH, 0)] + curve + inner)


def join_holes():
    """(Y, Z) of the two M3 holes that bolt neighbouring modules together."""
    yb0 = T * math.cos(math.radians(TILT))
    return [(yb0 + 20.0, 14.0), (yb0 + DEPTH - 8.0, BAR_H / 2)]


def gusset(x0):
    g = extrude_polygon(gusset_profile(), GUSSET_T)       # in YZ, extruded along "Z" of shapely
    # shapely (Y,Z) -> world: X = extrusion, Y = poly x, Z = poly y
    g.apply_transform(np.array([[0, 0, 1, 0],
                                [1, 0, 0, 0],
                                [0, 1, 0, 0],
                                [0, 0, 0, 1]], dtype=float))
    g.apply_translation([x0, 0, 0])
    return g


def rear_bar():
    yb0 = T * math.cos(math.radians(TILT))
    bar = trimesh.creation.box([W, GUSSET_T, BAR_H])
    bar.apply_translation([W / 2, yb0 + DEPTH - GUSSET_T / 2, BAR_H / 2])
    return bar


def build():
    frame = frame_local()
    frame.apply_transform(tilt_matrix())
    parts = [frame, gusset(0), gusset(W - GUSSET_T), rear_bar()]
    stand = trimesh.boolean.union(parts, engine="manifold")
    # the tilted plate's bottom-back edge dips below the floor - trim it flat
    floor = trimesh.creation.box([W + 10, 200, 20])
    floor.apply_translation([W / 2, 50, -10])
    cuts = [stand, floor]
    # M3 holes through both side gussets (either side can be the joint)
    for y, z in join_holes():
        d = cylinder(radius=JOIN_D / 2, height=W + 2, sections=SEGS)
        d.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
        d.apply_translation([W / 2, y, z])
        cuts.append(d)
    stand = trimesh.boolean.difference(cuts, engine="manifold")
    stand.apply_translation([0, -stand.bounds[0][1], 0])
    return stand


if __name__ == "__main__":
    m = build()
    assert m.is_watertight, "mesh is not watertight"
    m.export("stand_vfd.stl")
    ext = m.extents
    print(f"stand_vfd.stl  {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm, "
          f"volume {m.volume / 1000:.1f} cm3  (print 2x)")
