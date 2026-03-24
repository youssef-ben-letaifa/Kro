"""Kronos smoke test script."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import scipy.signal as signal
import sympy as sp

import control as ct

# ---------------------------
# Control systems test section
# ---------------------------
G = ct.tf([1.0], [1.0, 2.0, 1.0])
C = ct.tf([4.5, 6.0, 1.0], [1.0, 0.01])
T = ct.feedback(C * G, 1)

poles = ct.poles(T)
zeros = ct.zeros(T)
gm, pm, wg, wp = ct.margin(T)

t = np.linspace(0.0, 12.0, 1200)
t, y = ct.step_response(T, T=t)

try:
    step_info = ct.step_info(T)
except Exception:
    step_info = {}

# -----------------------------
# Signal processing test section
# -----------------------------
fs = 200.0
ts = np.arange(0.0, 4.0, 1.0 / fs)
x = np.sin(2 * np.pi * 2 * ts) + 0.3 * np.sin(2 * np.pi * 18 * ts)
b, a = signal.butter(4, 6 / (fs / 2), btype="low")
xf = signal.filtfilt(b, a, x)
fft_freq = np.fft.rfftfreq(ts.size, d=1.0 / fs)
fft_mag = np.abs(np.fft.rfft(xf))

# ----------------------
# Symbolic math section
# ----------------------
s = sp.symbols("s", complex=True)
t_sym = sp.symbols("t", positive=True, real=True)
expr = (s + 2) / (s**2 + 2 * s + 1)
expr_partial = sp.apart(expr, s)
expr_time = sp.inverse_laplace_transform(expr, s, t_sym)

# ----------------------
# Plotting test section
# ----------------------
fig, axs = plt.subplots(2, 2, figsize=(11, 7), facecolor="#08090e")
for ax in axs.flat:
    ax.set_facecolor("#08090e")
    ax.tick_params(colors="#6a7280")
    for spine in ax.spines.values():
        spine.set_color("#1e2128")
    ax.grid(True, color="#1a1f2a", linewidth=0.5)

axs[0, 0].plot(t, y, color="#1a6fff", linewidth=1.8)
axs[0, 0].set_title("Closed-Loop Step Response", color="#c8ccd4")
axs[0, 0].set_xlabel("Time (s)", color="#6a7280")
axs[0, 0].set_ylabel("Amplitude", color="#6a7280")

axs[0, 1].semilogx(fft_freq[1:], fft_mag[1:], color="#98c379", linewidth=1.4)
axs[0, 1].set_title("FFT Magnitude (Filtered Signal)", color="#c8ccd4")
axs[0, 1].set_xlabel("Frequency (Hz)", color="#6a7280")
axs[0, 1].set_ylabel("|X(f)|", color="#6a7280")

axs[1, 0].plot(ts, x, color="#e5c07b", linewidth=1.2, label="Raw")
axs[1, 0].plot(ts, xf, color="#61afef", linewidth=1.6, label="Filtered")
axs[1, 0].legend(facecolor="#0e1117", edgecolor="#1e2128", labelcolor="#c8ccd4")
axs[1, 0].set_title("Signal Filtering", color="#c8ccd4")
axs[1, 0].set_xlabel("Time (s)", color="#6a7280")
axs[1, 0].set_ylabel("Amplitude", color="#6a7280")

text = (
    f"Poles: {np.round(poles, 4)}\n"
    f"Zeros: {np.round(zeros, 4)}\n"
    f"GM: {gm:.4g}, PM: {pm:.3f} deg\n"
    f"ωg: {wg:.4g}, ωp: {wp:.4g}\n\n"
    f"Partial Fractions:\n{sp.sstr(expr_partial)}\n\n"
    f"Inverse Laplace:\n{sp.sstr(expr_time)}"
)
axs[1, 1].axis("off")
axs[1, 1].text(0.02, 0.98, text, va="top", ha="left", color="#c8ccd4", fontsize=9)

fig.suptitle("Kronos IDE Smoke Test", color="#c8ccd4", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.96])
plt.show()

print("Kronos smoke test completed.")
print(f"G = {G}")
print(f"C = {C}")
print(f"T = {T}")
print(f"PM = {pm:.3f} deg, GM = {gm:.4g}")
if step_info:
    print("Step info:", step_info)
