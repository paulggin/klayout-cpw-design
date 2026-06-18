import pya
import os

# ── Locked design parameters (from the impedance sweep) ───────────────────────────────────
S_UM = 10.0    # center conductor width, um
W_UM =  6.0    # gap width, um
Z0   = 50.43   # confirmed impedance, Ohm (Wen 1969 formula)

# ── Layout setup ──────────────────────────────────────────────────────────────
layout = pya.Layout()
layout.dbu = 0.001    # 1 dbu = 1 nm
top = layout.create_cell("CPW_XSECTION_TEST")

layer_metal = layout.layer(1, 0)    # conductor
layer_gap   = layout.layer(2, 0)    # etch region
layer_chip  = layout.layer(3, 0)    # chip boundary (reference)


# ── Unit conversion ────────────────────────────────────────────────────────────
def um(x):
    """Convert microns to database units (integer nm)."""
    return int(round(x * 1000))


# ── CPW cross-section geometry ────────────────────────────────────────────────
s        = um(S_UM)
w        = um(W_UM)
gnd      = um(200)       # ground plane extent, each side
length   = um(1000)      # CPW segment length = 1 mm

half_s    = s // 2
gap_inner = half_s
gap_outer = half_s + w
gnd_outer = gap_outer + gnd

# CPW centered on y=0, running along x-axis from 0 to length

# Center conductor
top.shapes(layer_metal).insert(
    pya.Box(0, -half_s, length, half_s))

# Top gap
top.shapes(layer_gap).insert(
    pya.Box(0,  gap_inner, length,  gap_outer))

# Bottom gap
top.shapes(layer_gap).insert(
    pya.Box(0, -gap_outer, length, -gap_inner))

# Top ground plane
top.shapes(layer_metal).insert(
    pya.Box(0,  gap_outer, length,  gnd_outer))

# Bottom ground plane
top.shapes(layer_metal).insert(
    pya.Box(0, -gnd_outer, length, -gap_outer))

# Chip boundary
top.shapes(layer_chip).insert(
    pya.Box(-um(100), -gnd_outer - um(50),
             length  + um(100),  gnd_outer + um(50)))

# ── Verification printout ─────────────────────────────────────────────────────
print("=" * 50)
print("CPW GEOMETRY VERIFICATION")
print("=" * 50)
print(f"Design parameters:")
print(f"  s  = {S_UM} um  (center conductor width)")
print(f"  w  = {W_UM} um  (gap width)")
print(f"  Z0 = {Z0} Ohm  (Wen formula, silicon epsilon_r=11.7)")
print()
print(f"In dbu (1 dbu = 1 nm):")
print(f"  half_s    = {half_s} dbu = {half_s/1000:.1f} um")
print(f"  gap width = {w} dbu = {w/1000:.1f} um")
print(f"  length    = {length} dbu = {length/1000:.0f} um = {length/1e6:.1f} mm")
print()
print(f"Cross-section (y from centerline):")
print(f"  Center conductor : +/-{half_s/1000:.1f} um")
print(f"  Gap outer edge   : +/-{gap_outer/1000:.1f} um")
print(f"  Ground outer     : +/-{gnd_outer/1000:.1f} um")
print(f"  Total chip width : {2*gnd_outer/1000:.1f} um")
print()

# ── Write GDS ─────────────────────────────────────────────────────────────────
output_dir = r'C:\Users\Paul\OneDrive\Desktop\Portfolio Projects\CPW - KLayout\outputs\gds'
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, 'cpw_cross_section.gds')
layout.write(output_file)
print(f"GDS written to: {output_file}")
print("Open in KLayout and verify cross-section dimensions visually.")
