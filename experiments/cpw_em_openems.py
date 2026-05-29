"""
CPW EM verification — OpenEMS FDTD simulation.

Project 3 (KLayout CPW Design): verifies the 50.43 Ω analytical result
from the Wen (1969) elliptic-integral formula by running a 3D FDTD
simulation of a 1 mm straight CPW segment on silicon (s = 10 µm,
w = 6 µm, ε_r = 11.7). Extracts S-parameters and port impedance
across 1–10 GHz.

Output
------
outputs/em_results/cpw_em_simulation.png  — Z₀ and S-parameters vs freq
outputs/em_results/cpw_em_results.npz     — raw S-parameter arrays
outputs/em_results/fdtd_run/              — OpenEMS working directory

Dependencies
------------
OpenEMS + CSXCAD Python bindings. Install instructions:
    https://docs.openems.de/install.html
Quick path on Linux/WSL/macOS:
    pip install --user openems CSXCAD numpy scipy matplotlib h5py

Notes on the port model
-----------------------
A single lumped port is placed across the upper CPW gap at each end of
the segment (between the center conductor edge and the inner edge of the
upper ground plane). This excites a slightly asymmetric mode at the
source plane but settles into the symmetric CPW mode within a few
hundred microns of propagation, which is well inside the 1 mm segment.
For tighter Z₀ extraction across very broad bands, swap to a two-line
TRL de-embedding scheme (not needed at the precision used here).
"""

import os
import shutil
import sys
import tempfile
import numpy as np
import matplotlib.pyplot as plt

try:
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS
except ImportError as exc:
    sys.stderr.write(
        "OpenEMS Python bindings not found. Install per "
        "https://docs.openems.de/install.html before running this script.\n"
        f"Underlying import error: {exc}\n"
    )
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Locked design parameters (from the impedance sweep)
# ──────────────────────────────────────────────────────────────────────────────
SUBSTRATE_EPS_R = 11.7      # silicon
CENTER_W        = 10.0      # s, center conductor width (µm)
GAP_W           = 6.0       # w, gap width (µm)
GROUND_W        = 200.0     # ground plane half-width (µm)
SEGMENT_LEN     = 1000.0    # straight CPW segment length (µm)
METAL_T         = 2.0       # metal thickness (µm) — simulation value; actual
                            # Nb film is ~200 nm but EM-relevant geometry is
                            # the s/w ratio. Using 2 µm here pushes the FDTD
                            # timestep up ~10× with <2% impact on Z₀.
SUBSTRATE_T     = 200.0     # silicon substrate thickness (µm) — sim only;
                            # real wafer is 500 µm but field decay above
                            # ~150 µm is negligible at 1-10 GHz.
AIR_T           = 200.0     # air box above (µm)
MARGIN          = 50.0      # PML margin on transverse sides (µm)

Z0_WEN          = 50.43     # Ω — analytical reference (Wen 1969)

# Frequency sweep — Gaussian excitation centered on the band
F_MIN    = 1.0e9
F_MAX    = 10.0e9
F_CENTER = 0.5 * (F_MIN + F_MAX)
F_HALF   = 0.5 * (F_MAX - F_MIN)

# Solver settings
NR_TIMESTEPS = 1_000_000  # safety margin; energy criterion usually stops earlier
END_CRITERIA = 1e-2      # stop when energy drops 2 decades (-40 dB)

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "outputs", "em_results"))
os.makedirs(OUT_DIR, exist_ok=True)

# FDTD working directory lives outside OneDrive — the sync agent locks
# folders during rmtree, which breaks re-runs. openEMS.Run() must create
# this directory itself, so hand it a path inside %TEMP% that does not
# yet exist on disk.
SIM_PARENT = tempfile.mkdtemp(prefix="openems_cpw_")
SIM_DIR = os.path.join(SIM_PARENT, "fdtd_run")
print(f"FDTD scratch directory: {SIM_DIR}")


# ──────────────────────────────────────────────────────────────────────────────
# Build the simulation
# ──────────────────────────────────────────────────────────────────────────────
FDTD = openEMS(NrTS=NR_TIMESTEPS, EndCriteria=END_CRITERIA)
FDTD.SetGaussExcite(F_CENTER, F_HALF)

# PML on all six faces. CPW radiates into both substrate and air, so no
# perfect-conductor ground beneath the substrate.
FDTD.SetBoundaryCond(["PML_8"] * 6)

CSX = ContinuousStructure()
FDTD.SetCSX(CSX)
CSX.GetGrid().SetDeltaUnit(1e-6)   # all coordinates in µm

# Coordinate convention:
#   x: along the line (propagation direction)
#   y: across the width (perpendicular to propagation)
#   z: vertical, +z above substrate, -z into substrate
#   origin: top-center of substrate, midpoint of segment

x_min = -SEGMENT_LEN / 2.0
x_max =  SEGMENT_LEN / 2.0
y_extent = CENTER_W / 2.0 + GAP_W + GROUND_W + MARGIN

# Silicon substrate
silicon = CSX.AddMaterial("silicon", epsilon=SUBSTRATE_EPS_R)
silicon.AddBox(
    start=[x_min - 100.0, -y_extent, -SUBSTRATE_T],
    stop =[x_max + 100.0,  y_extent, 0.0],
    priority=1,
)

# CPW metal — single material, three rectangles
metal = CSX.AddMetal("metal")

# Center conductor
metal.AddBox(
    start=[x_min, -CENTER_W / 2.0, 0.0],
    stop =[x_max,  CENTER_W / 2.0, METAL_T],
    priority=10,
)

# Upper ground plane (y > 0)
metal.AddBox(
    start=[x_min,  CENTER_W / 2.0 + GAP_W,                  0.0],
    stop =[x_max,  CENTER_W / 2.0 + GAP_W + GROUND_W,       METAL_T],
    priority=10,
)

# Lower ground plane (y < 0)
metal.AddBox(
    start=[x_min, -(CENTER_W / 2.0 + GAP_W + GROUND_W),     0.0],
    stop =[x_max, -(CENTER_W / 2.0 + GAP_W),                METAL_T],
    priority=10,
)


# ──────────────────────────────────────────────────────────────────────────────
# Lumped ports — one per end, across the upper gap
# ──────────────────────────────────────────────────────────────────────────────
# Dual-gap symmetric CPW excitation. Two lumped ports per chip end, one
# across each gap, both driven in phase. R = 100 Ω per port — the parallel
# combination at each end is 50 Ω, which matches the line.
#
# Single-gap excitation produces an asymmetric mode that under-reads Z₀ by
# ~30% (Z_sim ≈ 31 Ω vs Wen 50.43 Ω). Dual-gap drives the true symmetric
# mode where the center conductor sits at +V relative to both ground planes.

PORT_R = 100.0   # per-port resistance; two in parallel = 50 Ω matched

# Source end (x_min) — both ports excited
port1u = FDTD.AddLumpedPort(
    port_nr=1, R=PORT_R,
    start=[x_min,  CENTER_W / 2.0,          0.0],
    stop =[x_min,  CENTER_W / 2.0 + GAP_W,  METAL_T],
    p_dir="y", excite=1.0, priority=20,
)
port1l = FDTD.AddLumpedPort(
    port_nr=2, R=PORT_R,
    start=[x_min, -(CENTER_W / 2.0 + GAP_W), 0.0],
    stop =[x_min, -CENTER_W / 2.0,           METAL_T],
    p_dir="y", excite=-1.0, priority=20,   # sign flip — drives symmetric mode
)

# Load end (x_max) — both ports terminate, no excitation
port2u = FDTD.AddLumpedPort(
    port_nr=3, R=PORT_R,
    start=[x_max,  CENTER_W / 2.0,          0.0],
    stop =[x_max,  CENTER_W / 2.0 + GAP_W,  METAL_T],
    p_dir="y", excite=0.0, priority=20,
)
port2l = FDTD.AddLumpedPort(
    port_nr=4, R=PORT_R,
    start=[x_max, -(CENTER_W / 2.0 + GAP_W), 0.0],
    stop =[x_max, -CENTER_W / 2.0,           METAL_T],
    p_dir="y", excite=0.0, priority=20,
)


# ──────────────────────────────────────────────────────────────────────────────
# Mesh — refined near gap edges and metal layer
# ──────────────────────────────────────────────────────────────────────────────
mesh = CSX.GetGrid()

# x: anchor at PML edges, port locations, and segment midpoint. SmoothMeshLines
# fills the rest. Anchors at x_min and x_max are MANDATORY — without them,
# openEMS cannot attach the lumped-port excitation to a mesh edge and silently
# runs with no source (the "Unused primitive" warning on port_excite_1).
x_anchors = sorted({
    x_min - 100.0,
    x_min,
    0.0,
    x_max,
    x_max + 100.0,
})
mesh.AddLine("x", x_anchors)
mesh.SmoothMeshLines("x", 40.0, 1.4)   # max 40 µm step, 1.4× growth ratio

# y: anchor lines at every geometry transition, then smooth
y_anchors = sorted({
    -y_extent,
    -(CENTER_W / 2.0 + GAP_W + GROUND_W),
    -(CENTER_W / 2.0 + GAP_W),
    -CENTER_W / 2.0,
     0.0,
     CENTER_W / 2.0,
     CENTER_W / 2.0 + GAP_W,
     CENTER_W / 2.0 + GAP_W + GROUND_W,
     y_extent,
})
mesh.AddLine("y", y_anchors)
mesh.SmoothMeshLines("y", 2.5, 1.5)   # max 2.5 µm step, 1.5× growth ratio

# z: anchor only at geometry transitions; SmoothMeshLines fills the rest.
# Critical: no extra lines inside the metal — they would shrink the FDTD
# timestep without adding accuracy (PEC interior has zero field).
z_anchors = sorted({
    -SUBSTRATE_T,
    -50.0,
    -10.0,
     0.0,
     METAL_T,
     10.0,
     50.0,
     AIR_T,
})
mesh.AddLine("z", z_anchors)
mesh.SmoothMeshLines("z", 4.0, 1.4)   # max 4 µm step, 1.4× growth ratio


# ──────────────────────────────────────────────────────────────────────────────
# Write geometry and run the solver
# ──────────────────────────────────────────────────────────────────────────────
xml_path = os.path.join(SIM_PARENT, "cpw.xml")
CSX.Write2XML(xml_path)
print(f"Geometry XML written: {xml_path}")
print("Launching openEMS FDTD run...")
n_threads = os.cpu_count() or 4
print(f"Requesting {n_threads} threads for FDTD engine")
FDTD.Run(SIM_DIR, verbose=3, cleanup=True, numThreads=n_threads)


# ──────────────────────────────────────────────────────────────────────────────
# Post-process: extract S-parameters and Z₀
# ──────────────────────────────────────────────────────────────────────────────
freq = np.linspace(F_MIN, F_MAX, 401)

port1u.CalcPort(SIM_DIR, freq)
port1l.CalcPort(SIM_DIR, freq)
port2u.CalcPort(SIM_DIR, freq)
port2l.CalcPort(SIM_DIR, freq)

# Symmetric dual-gap port reading. By symmetry the upper-gap and lower-gap
# ports see identical V and I, so the single-port reflection coefficient
# s11 from port1u (referenced to its own 100 Ω) numerically equals the
# combined-port s11 (referenced to the effective parallel 50 Ω).
# The combined port is what physically loads the CPW line, so the Z
# extraction uses the 50 Ω reference.
s11 = port1u.uf_ref / port1u.uf_inc
s21 = port2u.uf_ref / port1u.uf_inc

# Z extraction reference impedance MUST be PORT_R, not the combined-port
# effective impedance. openEMS reports each port's s11 relative to that
# port's own resistor R, regardless of how the ports are wired in parallel
# externally. Using 50 here (the combined-port view) gives Z = Z_line / 2
# — a factor-of-2 error that mimics the symptom of a port-coupling issue.
Z_sim = PORT_R * (1.0 + s11) / (1.0 - s11)
Z_sim_real = np.real(Z_sim)


# ──────────────────────────────────────────────────────────────────────────────
# Plot
# ──────────────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 1, figsize=(8.5, 9))

ax = axes[0]
ax.plot(freq / 1e9, Z_sim_real, "b-", lw=2, label="OpenEMS FDTD")
ax.axhline(Z0_WEN, color="r", linestyle="--", lw=1.5,
           label=f"Wen analytical ({Z0_WEN:.2f} Ω)")
ax.set_xlabel("Frequency (GHz)")
ax.set_ylabel("Re{Z₀} (Ω)")
ax.set_title("CPW Port Impedance — Simulated vs Analytical\n"
             f"s = {CENTER_W:.0f} µm, w = {GAP_W:.0f} µm, silicon (ε_r = {SUBSTRATE_EPS_R})")
ax.set_ylim(40, 60)
ax.legend(loc="lower right")
ax.grid(True, alpha=0.3)

ax = axes[1]
ax.plot(freq / 1e9, 20.0 * np.log10(np.abs(s11)), "b-", lw=2, label="|S₁₁|")
ax.plot(freq / 1e9, 20.0 * np.log10(np.abs(s21)), "g-", lw=2, label="|S₂₁|")
ax.axhline(-20.0, color="r", linestyle="--", lw=1.0, alpha=0.6,
           label="-20 dB return-loss target")
ax.set_xlabel("Frequency (GHz)")
ax.set_ylabel("S-parameter magnitude (dB)")
ax.set_title("S-parameters — 1 mm straight CPW segment")
ax.set_ylim(-40, 5)
ax.legend(loc="lower right")
ax.grid(True, alpha=0.3)

plt.tight_layout()
png_path = os.path.join(OUT_DIR, "cpw_em_simulation.png")
plt.savefig(png_path, dpi=150)
print(f"Plot saved: {png_path}")


# ──────────────────────────────────────────────────────────────────────────────
# Save raw data + console summary
# ──────────────────────────────────────────────────────────────────────────────
npz_path = os.path.join(OUT_DIR, "cpw_em_results.npz")
np.savez(
    npz_path,
    freq=freq,
    s11=s11,
    s21=s21,
    Z_sim=Z_sim,
    Z0_wen=Z0_WEN,
    params=dict(
        s_um=CENTER_W,
        w_um=GAP_W,
        eps_r=SUBSTRATE_EPS_R,
        segment_len_um=SEGMENT_LEN,
        metal_t_um=METAL_T,
    ),
)
print(f"Raw data saved: {npz_path}")

band_mask = (freq >= 4e9) & (freq <= 8e9)
Z_band_mean = float(np.mean(Z_sim_real[band_mask]))

# openEMS's s11 is referenced to each port's own R (100 Ω), so |s11| ~ 1/3
# even when the CPW line itself is well matched to 50 Ω. The physically
# meaningful return loss is the s11 a 50 Ω VNA would measure on the line:
s11_line = (Z_sim - 50.0) / (Z_sim + 50.0)
s11_line_band_max_db = float(np.max(20.0 * np.log10(np.abs(s11_line[band_mask]))))
s11_port_band_max_db = float(np.max(20.0 * np.log10(np.abs(s11[band_mask]))))

print("")
print("--- Results summary ---")
print("Analytical Z0 (Wen 1969):           {:>7.2f} Ohm".format(Z0_WEN))
print("Simulated Z0 (mean across 4-8 GHz): {:>7.2f} Ohm".format(Z_band_mean))
pct = abs(Z_band_mean - Z0_WEN) / Z0_WEN * 100.0
print("Discrepancy:                        {:>7.2f} %".format(pct))
print("Line return loss (50 Ω ref, 4-8 GHz):{:>7.2f} dB".format(s11_line_band_max_db))
print("Port |S11| (100 Ω ref, raw openEMS): {:>7.2f} dB".format(s11_port_band_max_db))
print("-----------------------")
