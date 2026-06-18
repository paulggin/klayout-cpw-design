import numpy as np
import matplotlib.pyplot as plt
from scipy.special import ellipk

# ── Substrate ────────────────────────────────────────────────────────────────
epsilon_r = 11.7          # silicon
epsilon_eff = (1 + epsilon_r) / 2   # equal filling fraction approximation

# ── CPW Impedance (Wen 1969) ─────────────────────────────────────────────────
def cpw_impedance(s_um, w_um):
    s = s_um * 1e-6   # convert to metres (cancels out, but keeps units explicit)
    w = w_um * 1e-6

    k  = s / (s + 2 * w)
    kp = np.sqrt(1 - k**2)       # complementary modulus

    K  = ellipk(k**2)            # K(k)  — note: scipy takes k², not k
    Kp = ellipk(kp**2)           # K(k')

    Z0 = (30 * np.pi / np.sqrt(epsilon_eff)) * (Kp / K)
    return Z0

# ── Parameter sweep ──────────────────────────────────────────────────────────
s_values = np.linspace(5, 20, 200)    # center conductor width, µm
w_values = np.linspace(3, 15, 200)    # gap width, µm

S, W = np.meshgrid(s_values, w_values)
Z0_grid = cpw_impedance(S, W)

# ── Print a sample table ──────────────────────────────────────────────────────
print(f"\nCPW Impedance Table — Silicon (ε_r = {epsilon_r}, ε_eff = {epsilon_eff:.2f})")
print(f"{'s (µm)':>8}  {'w (µm)':>8}  {'k':>8}  {'Z₀ (Ω)':>10}")
print("-" * 42)
for s in [5, 8, 10, 12, 15, 20]:
    for w in [3, 5, 6, 8, 10]:
        k = s / (s + 2*w)
        z = cpw_impedance(s, w)
        print(f"{s:>8.1f}  {w:>8.1f}  {k:>8.4f}  {z:>10.2f}")
    print()

# ── Contour plot ──────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 7))

cf = ax.contourf(S, W, Z0_grid, levels=40, cmap='RdYlGn_r')
cbar = fig.colorbar(cf, ax=ax, label='Z₀ (Ω)')

# Highlight the 50 Ω contour
cs50 = ax.contour(S, W, Z0_grid, levels=[50], colors='blue', linewidths=2.5)
ax.clabel(cs50, fmt='50 Ω', fontsize=12, inline=True)

# Add contours at 40 and 60 Ω for reference
cs_ref = ax.contour(S, W, Z0_grid, levels=[40, 60], colors='white',
                    linewidths=1.2, linestyles='--')
ax.clabel(cs_ref, fmt='%d Ω', fontsize=10, inline=True)

# Mark a candidate design point
s_design, w_design = 10, 6
z_design = cpw_impedance(s_design, w_design)
ax.plot(s_design, w_design, 'b*', markersize=14, label=f's={s_design} µm, w={w_design} µm → Z₀={z_design:.1f} Ω')

ax.set_xlabel('Center conductor width s (µm)', fontsize=13)
ax.set_ylabel('Gap width w (µm)', fontsize=13)
ax.set_title(f'CPW Characteristic Impedance — Silicon (ε_r = {epsilon_r})\nWen (1969) Formula', fontsize=13)
ax.legend(fontsize=11)
plt.tight_layout()

# Save 
plt.savefig(r'C:\Users\Paul\OneDrive\Desktop\Portfolio Projects\CPW - KLayout\outputs\plots', dpi=150, bbox_inches='tight')
print("\nPlot saved.")
plt.show()
