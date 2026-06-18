import pya
import os

# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

layout = pya.Layout()
layout.dbu = 0.001    # 1 dbu = 1 nm
top = layout.create_cell("CPW_CHIP")

# Layer convention:
#   1 = metal  (Nb/Al conductor + ground plane)
#   2 = gap    (etch region between conductor and ground)
#   3 = chip   (chip boundary outline)
#   4 = text   (labels)
LY_METAL = layout.layer(1, 0)
LY_GAP   = layout.layer(2, 0)
LY_CHIP  = layout.layer(3, 0)
LY_TEXT  = layout.layer(4, 0)


def um(x):
    """Convert microns to integer database units (nm)."""
    return int(round(x * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# LOCKED DESIGN PARAMETERS (from the impedance sweep)
# ═══════════════════════════════════════════════════════════════════════════════

S   = um(10)     # center conductor full width
W   = um(6)      # gap width
GND = um(150)    # ground plane width each side

HALF_S    = S // 2
GAP_INNER = HALF_S
GAP_OUTER = HALF_S + W
GND_OUTER = GAP_OUTER + GND

CHIP_W = um(5000)    # 5 mm chip width
CHIP_H = um(3000)    # 3 mm chip height


# ═══════════════════════════════════════════════════════════════════════════════
# DRAWING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def draw_cpw_segment(cell, x0, x1, y_center):
    yc = y_center
    cell.shapes(LY_METAL).insert(pya.Box(x0, yc - HALF_S,    x1, yc + HALF_S))
    cell.shapes(LY_GAP).insert(  pya.Box(x0, yc + GAP_INNER, x1, yc + GAP_OUTER))
    cell.shapes(LY_GAP).insert(  pya.Box(x0, yc - GAP_OUTER, x1, yc - GAP_INNER))
    cell.shapes(LY_METAL).insert(pya.Box(x0, yc + GAP_OUTER, x1, yc + GND_OUTER))
    cell.shapes(LY_METAL).insert(pya.Box(x0, yc - GND_OUTER, x1, yc - GAP_OUTER))


def draw_launcher(cell, x_tip, y_center, facing):
    PAD_W       = um(200)
    PAD_LEN     = um(300)
    TAPER_LEN   = um(400)
    PAD_GAP     = um(80)
    PAD_GND_W   = um(150)

    PAD_HALF    = PAD_W // 2
    PAD_G_IN    = PAD_HALF
    PAD_G_OUT   = PAD_HALF + PAD_GAP
    PAD_GND_OUT = PAD_G_OUT + PAD_GND_W

    yc = y_center
    x_taper_end = x_tip + facing * TAPER_LEN
    x_pad_end   = x_taper_end + facing * PAD_LEN

    # Tapered polygons (trapezoids): narrow at x_tip, wide at x_taper_end
    pts_conductor = [
        pya.Point(x_tip,       yc + HALF_S),
        pya.Point(x_taper_end, yc + PAD_HALF),
        pya.Point(x_taper_end, yc - PAD_HALF),
        pya.Point(x_tip,       yc - HALF_S),
    ]
    pts_top_gap = [
        pya.Point(x_tip,       yc + GAP_INNER),
        pya.Point(x_taper_end, yc + PAD_G_IN),
        pya.Point(x_taper_end, yc + PAD_G_OUT),
        pya.Point(x_tip,       yc + GAP_OUTER),
    ]
    pts_bot_gap = [
        pya.Point(x_tip,       yc - GAP_OUTER),
        pya.Point(x_taper_end, yc - PAD_G_OUT),
        pya.Point(x_taper_end, yc - PAD_G_IN),
        pya.Point(x_tip,       yc - GAP_INNER),
    ]
    pts_top_gnd = [
        pya.Point(x_tip,       yc + GAP_OUTER),
        pya.Point(x_taper_end, yc + PAD_G_OUT),
        pya.Point(x_taper_end, yc + PAD_GND_OUT),
        pya.Point(x_tip,       yc + GND_OUTER),
    ]
    pts_bot_gnd = [
        pya.Point(x_tip,       yc - GND_OUTER),
        pya.Point(x_taper_end, yc - PAD_GND_OUT),
        pya.Point(x_taper_end, yc - PAD_G_OUT),
        pya.Point(x_tip,       yc - GAP_OUTER),
    ]

    for pts, ly in [(pts_conductor, LY_METAL),
                    (pts_top_gap,   LY_GAP),
                    (pts_bot_gap,   LY_GAP),
                    (pts_top_gnd,   LY_METAL),
                    (pts_bot_gnd,   LY_METAL)]:
        cell.shapes(ly).insert(pya.Polygon(pts))

    # Uniform-width bond pad section
    x_lo = min(x_taper_end, x_pad_end)
    x_hi = max(x_taper_end, x_pad_end)
    cell.shapes(LY_METAL).insert(pya.Box(x_lo, yc - PAD_HALF,    x_hi, yc + PAD_HALF))
    cell.shapes(LY_GAP).insert(  pya.Box(x_lo, yc + PAD_G_IN,    x_hi, yc + PAD_G_OUT))
    cell.shapes(LY_GAP).insert(  pya.Box(x_lo, yc - PAD_G_OUT,   x_hi, yc - PAD_G_IN))
    cell.shapes(LY_METAL).insert(pya.Box(x_lo, yc + PAD_G_OUT,   x_hi, yc + PAD_GND_OUT))
    cell.shapes(LY_METAL).insert(pya.Box(x_lo, yc - PAD_GND_OUT, x_hi, yc - PAD_G_OUT))


def draw_meander(cell, x_start, y_center, seg_len, n_bends):
    PITCH  = 2 * GND_OUTER + um(80)   # lane-to-lane pitch (80 um clearance)
    BEND_W = GND_OUTER                 # U-turn block half-width

    x         = x_start
    y         = y_center
    direction = 1    # +1 = rightward, -1 = leftward
    x_end_seg = x    # initialise for return value

    for i in range(n_bends + 1):
        x_end_seg = x + direction * seg_len
        x0 = min(x, x_end_seg)
        x1 = max(x, x_end_seg)
        draw_cpw_segment(cell, x0, x1, y)

        if i < n_bends:
            turn_x = x_end_seg
            y_next = y + PITCH

            # Solid metal bridges the two lane ground planes
            cell.shapes(LY_METAL).insert(
                pya.Box(turn_x - BEND_W, y      - GND_OUTER,
                        turn_x + BEND_W, y_next + GND_OUTER))

            # Gap cutouts — incoming lane (bottom of bend)
            cell.shapes(LY_GAP).insert(
                pya.Box(turn_x - BEND_W, y + GAP_INNER, turn_x, y + GAP_OUTER))
            cell.shapes(LY_GAP).insert(
                pya.Box(turn_x - BEND_W, y - GAP_OUTER, turn_x, y - GAP_INNER))

            # Gap cutouts — outgoing lane (top of bend)
            cell.shapes(LY_GAP).insert(
                pya.Box(turn_x - BEND_W, y_next + GAP_INNER, turn_x, y_next + GAP_OUTER))
            cell.shapes(LY_GAP).insert(
                pya.Box(turn_x - BEND_W, y_next - GAP_OUTER, turn_x, y_next - GAP_INNER))

            # Vertical center conductor through bend
            cell.shapes(LY_METAL).insert(
                pya.Box(turn_x - HALF_S, y      - HALF_S,
                        turn_x + HALF_S, y_next + HALF_S))

            y = y_next
            direction *= -1
            x = x_end_seg

    return x_end_seg, y


def draw_coupling_cap(cell, x_pos, y_center):
    CAP_GAP = um(5)
    cell.shapes(LY_GAP).insert(
        pya.Box(x_pos - CAP_GAP // 2, y_center - HALF_S,
                x_pos + CAP_GAP // 2, y_center + HALF_S))
    t = pya.DText("Cc", x_pos / 1000.0, y_center / 1000.0 + 25)
    cell.shapes(LY_TEXT).insert(t)
    print(f"  Coupling cap: {CAP_GAP/1000:.1f} um gap at x = {x_pos/1000:.0f} um")


# ═══════════════════════════════════════════════════════════════════════════════
# CHIP ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════════════

print("Building CPW chip layout...")
print(f"  Chip  : {CHIP_W/1000:.0f} um x {CHIP_H/1000:.0f} um")
print(f"  s={S/1000:.0f} um  w={W/1000:.0f} um  Z0=50.43 Ohm  epsilon_eff=6.35")
print()

# Chip boundary
top.shapes(LY_CHIP).insert(pya.Box(0, 0, CHIP_W, CHIP_H))

# ── Feedline ──────────────────────────────────────────────────────────────────
MARGIN       = um(800)
Y_FEED       = CHIP_H // 3
X_FEED_START = MARGIN
X_FEED_END   = CHIP_W - MARGIN

print("Drawing feedline...")
draw_cpw_segment(top, X_FEED_START, X_FEED_END, Y_FEED)

# ── Launchers ─────────────────────────────────────────────────────────────────
print("Drawing launchers...")
draw_launcher(top, X_FEED_START, Y_FEED, facing=+1)    # left launcher
draw_launcher(top, X_FEED_END,   Y_FEED, facing=-1)    # right launcher

# ── Meander resonator ─────────────────────────────────────────────────────────
print("Drawing meander resonator...")
Y_MEANDER    = Y_FEED + GND_OUTER + um(500)
X_MEAN_START = MARGIN + um(500)
MEAN_SEG     = um(1000)
N_BENDS      = 3

x_end, y_end = draw_meander(top, X_MEAN_START, Y_MEANDER,
                             seg_len=MEAN_SEG, n_bends=N_BENDS)
total_mean_len = (N_BENDS + 1) * MEAN_SEG
print(f"  Meander: {N_BENDS+1} segments x {MEAN_SEG/1000:.0f} um = {total_mean_len/1000:.0f} um total")

# ── Coupling capacitor ────────────────────────────────────────────────────────
print("Drawing coupling capacitor...")
X_CAP = X_FEED_START + (X_FEED_END - X_FEED_START) * 3 // 4
draw_coupling_cap(top, X_CAP, Y_FEED)

# ── Write GDS ─────────────────────────────────────────────────────────────────
output_dir = r'C:\Users\Paul\OneDrive\Desktop\Portfolio Projects\CPW - KLayout\outputs\gds'
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, 'cpw_full_layout.gds')
layout.write(output_file)

print()
print("=" * 55)
print("LAYOUT COMPLETE")
print("=" * 55)
print(f"GDS written to: {output_file}")
print()
print("Elements:")
print(f"  Feedline     : {(X_FEED_END-X_FEED_START)/1000:.0f} um straight CPW")
print(f"  Launchers    : 2x tapered (200 um bond pad -> 10 um CPW)")
print(f"  Meander      : {N_BENDS+1} segments x {MEAN_SEG/1000:.0f} um = {total_mean_len/1000:.0f} um")
print(f"  Coupling cap : 5 um gap at x={X_CAP/1000:.0f} um")
print(f"  CPW params   : s={S/1000:.0f} um, w={W/1000:.0f} um, Z0=50.43 Ohm")
