# Repository Inventory

Snapshot of the KLayout CPW Design project.

## Install

Two separate installations are needed:

```bash
# Standard scientific Python (for the impedance sweep and OpenEMS post-processing)
pip install -r requirements.txt

# KLayout — geometry scripts run inside its built-in macro editor:
#   https://www.klayout.de/build.html

# OpenEMS — FDTD engine + Python bindings, install per:
#   https://docs.openems.de/install.html
```

## Layout

```
.
├── README.md
├── INVENTORY.md
├── LICENSE
├── .gitignore
├── requirements.txt
│
├── experiments/                              ← Python scripts
│   ├── cpw_impedance_sweep.py                ← Wen (1969) formula sweep over (s, w); writes contour plot
│   ├── cpw_cross_section.py                  ← KLayout: 1 mm straight CPW segment, three-rectangle cross-section
│   ├── cpw_full_layout.py                    ← KLayout: 5×3 mm chip — feedline + launchers + meander + coupling cap
│   └── cpw_em_openems.py                     ← OpenEMS FDTD: Z₀ and S-parameters vs frequency, 1–10 GHz
│
├── layouts/                                  ← GDS mask files
│   ├── cpw_cross_section.gds                 ← straight 1 mm segment, validates cross-section geometry
│   ├── cpw_full_layout.gds                   ← full 5×3 mm chip with all four elements
│   └── test_geometry.gds                     ← two-rectangle layer-write sanity check
│
└── plots/                                    ← figures referenced by README
    ├── cpw_impedance_sweep.png               ← Z₀ contour map on silicon, locked design point starred
    └── cpw_em_simulation.png                 ← regenerate by running experiments/cpw_em_openems.py
```

## Running the scripts

**Impedance sweep:**
```bash
python experiments/cpw_impedance_sweep.py
```
Writes `plots/cpw_impedance_sweep.png`.

**KLayout geometry scripts:** open KLayout, then File → Open from `experiments/`, then F5 to run. Each script writes a GDS file to `layouts/`.

**OpenEMS FDTD:**
```bash
python experiments/cpw_em_openems.py
```
Writes `plots/cpw_em_simulation.png` and an `.npz` of raw S-parameter data. Wall-clock is roughly one hour on a 16-thread laptop; the FDTD scratch directory is placed in the OS temp folder, not the repo.
