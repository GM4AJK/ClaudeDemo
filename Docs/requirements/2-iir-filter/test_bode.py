"""
test_bode.py — Req 2 acceptance test

Sweeps FY6800 CH1 from 50 Hz to 2000 Hz, measures V_in (scope C1) and
V_out (scope C2) at each frequency, plots the Bode magnitude, and checks
the -3 dB point is at 500 Hz ± 50 Hz.

Pass conditions:
  - Gain at 500 Hz : -3 dB ± 1 dB
  - Gain at 100 Hz : >= -1 dB  (flat passband)
  - Gain at 1000 Hz: <= -10 dB (roll-off present)

Instruments:
  FY6800  — /dev/ttyUSB0 (pyserial)
  SDS824X — 192.168.0.87:5025 (SCPI/TCP)
"""

import math
import re
import socket
import sys
import time

import numpy as np
import serial
import matplotlib
matplotlib.use('Agg')   # headless; swap to 'TkAgg' if display is available
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Frequency sweep points (log-spaced, 50 Hz – 2000 Hz)
# ---------------------------------------------------------------------------

FREQS = np.logspace(math.log10(50), math.log10(2000), 35).tolist()

# Theoretical 2nd-order Butterworth for reference overlay
FC = 500.0
def theory_db(f):
    return -10.0 * math.log10(1.0 + (f / FC) ** 4)


# ---------------------------------------------------------------------------
# Scope timebase helper
# ---------------------------------------------------------------------------

# Standard TDIV steps in seconds
_TDIV_STEPS = [
    1e-9, 2e-9, 5e-9,
    1e-8, 2e-8, 5e-8,
    1e-7, 2e-7, 5e-7,
    1e-6, 2e-6, 5e-6,
    1e-5, 2e-5, 5e-5,
    1e-4, 2e-4, 5e-4,
    1e-3, 2e-3, 5e-3,
    1e-2, 2e-2, 5e-2,
]

def _tdiv_str(sec):
    if sec >= 1e-3:
        return f'{sec * 1e3:.0f}ms'
    return f'{sec * 1e6:.0f}us'

def choose_tdiv(freq):
    """Return a TDIV string that shows ~4 cycles on screen (10 horizontal divs)."""
    target = 4.0 / (freq * 10.0)
    for s in reversed(_tdiv_steps := _TDIV_STEPS):
        if s <= target:
            return _tdiv_str(s)
    return _tdiv_str(_TDIV_STEPS[0])


# ---------------------------------------------------------------------------
# VDIV helper for C2 (output channel — amplitude varies with filter gain)
# ---------------------------------------------------------------------------

_VDIV_MV = [5, 10, 20, 50, 100, 200, 500, 1000, 2000]

def _vdiv_str(mv):
    return f'{mv // 1000}V' if mv >= 1000 else f'{mv}mV'

def choose_vdiv_c2(freq, vin_vpp_mv=1000.0):
    """Pick the smallest VDIV that keeps the expected output within ±3.5 divs."""
    gain = 1.0 / math.sqrt(1.0 + (freq / FC) ** 4)
    expected_half_vpp = vin_vpp_mv * gain / 2.0
    for mv in _VDIV_MV:
        if expected_half_vpp <= mv * 3.5:
            return _vdiv_str(max(mv, 10))
    return _vdiv_str(2000)


# ---------------------------------------------------------------------------
# FY6800 driver
# ---------------------------------------------------------------------------

class FY6800:
    def __init__(self, port='/dev/ttyUSB0'):
        self.s = serial.Serial(port, 115200, timeout=1)
        time.sleep(0.5)

    def _cmd(self, c):
        self.s.write((c + '\n').encode())
        time.sleep(0.15)
        self.s.read_all()

    def set_wave(self, ch, code):
        p = 'M' if ch == 0 else 'F'
        self._cmd(f'W{p}W{code:02d}')

    def set_freq(self, ch, hz):
        p = 'M' if ch == 0 else 'F'
        self._cmd(f'W{p}F{int(hz * 1_000_000):014d}')

    def set_amp(self, ch, v):
        p = 'M' if ch == 0 else 'F'
        self._cmd(f'W{p}A{v:.4f}')

    def set_offset(self, ch, v):
        p = 'M' if ch == 0 else 'F'
        self._cmd(f'W{p}O{v:.4f}')

    def output(self, ch, on):
        p = 'M' if ch == 0 else 'F'
        self._cmd(f'W{p}N{1 if on else 0}')

    def close(self):
        self.s.close()


# ---------------------------------------------------------------------------
# SDS824X HD helpers
# ---------------------------------------------------------------------------

def scope_send(sc, cmd):
    sc.sendall((cmd + '\n').encode())
    time.sleep(0.15)

def scope_query(sc, cmd, delay=1.2):
    sc.sendall((cmd + '\n').encode())
    time.sleep(delay)
    try:
        return sc.recv(65536).decode(errors='replace').strip()
    except Exception:
        return ''

def parse_pkpk(resp):
    m = re.search(r'PKPK,([0-9.E+\-]+)V', resp)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('=== Req 2 Bode plot test ===')

    # --- FY6800 initial setup ---
    print('Connecting to FY6800 ...')
    fy = FY6800('/dev/ttyUSB0')
    fy.set_wave(0, 0)       # sine
    fy.set_amp(0, 1.0)      # 1.0 Vpp
    fy.set_offset(0, 1.65)  # 1.65 V DC offset (keeps MCU ADC/DAC in mid-range)
    fy.output(0, True)

    # --- Scope initial setup ---
    print('Connecting to SDS824X HD ...')
    sc = socket.socket()
    sc.connect(('192.168.0.87', 5025))
    sc.settimeout(5)

    # Clear any FFT overlay left by a previous test
    scope_send(sc, ':FUNC1 OFF')

    # C1 and C2: AC coupled, fixed 200 mV/div — audience sees C2 amplitude
    # visibly dropping as frequency rises without any axis rescaling.
    for ch in ('C1', 'C2'):
        scope_send(sc, f'{ch}:ATTN 10')
        scope_send(sc, f'{ch}:CPL A1M')
        scope_send(sc, f'{ch}:VDIV 200mV')
        scope_send(sc, f'{ch}:OFST 0V')

    N_AVG = 5   # number of PKPK readings to average per frequency point

    # --- Sweep ---
    freqs_meas = []
    gains_db   = []

    for freq in FREQS:
        fy.set_freq(0, freq)

        tdiv = choose_tdiv(freq)
        scope_send(sc, f'TDIV {tdiv}')

        # Wait for the new timebase to take effect and the filter to settle.
        time.sleep(max(20.0 / freq, 1.0))

        # Take N_AVG readings and average to reduce measurement noise.
        v_ins, v_outs = [], []
        for _ in range(N_AVG):
            r1 = scope_query(sc, 'C1:PAVA? PKPK', delay=0.4)
            r2 = scope_query(sc, 'C2:PAVA? PKPK', delay=0.4)
            v1 = parse_pkpk(r1)
            v2 = parse_pkpk(r2)
            if v1 is not None and v1 > 1e-6 and v2 is not None and v2 > 0.0:
                v_ins.append(v1)
                v_outs.append(v2)

        if not v_ins:
            print(f'  {freq:7.1f} Hz — all {N_AVG} readings invalid, skipping')
            continue

        v_in  = sum(v_ins)  / len(v_ins)
        v_out = sum(v_outs) / len(v_outs)

        gain = 20.0 * math.log10(v_out / v_in)
        freqs_meas.append(freq)
        gains_db.append(gain)
        print(f'  {freq:7.1f} Hz  V_in={v_in*1000:6.1f} mV  V_out={v_out*1000:6.1f} mV  '
              f'gain={gain:+.1f} dB  (n={len(v_ins)}, tdiv={tdiv})')

    fy.close()
    sc.close()

    if not freqs_meas:
        print('FAIL: no valid measurements')
        sys.exit(1)

    # --- PASS/FAIL checks ---
    def gain_at(target_hz, tol_hz=80):
        """Interpolate measured gain at target frequency."""
        candidates = [(abs(f - target_hz), g) for f, g in zip(freqs_meas, gains_db)
                      if abs(f - target_hz) <= tol_hz]
        if not candidates:
            return None
        return min(candidates, key=lambda x: x[0])[1]

    g100  = gain_at(100)
    g500  = gain_at(500)
    g1000 = gain_at(1000)

    print()
    failures = []

    if g100 is not None:
        ok = g100 >= -1.0
        print(f'  100 Hz gain : {g100:+.1f} dB  (need ≥ −1 dB)  {"PASS" if ok else "FAIL"}')
        if not ok: failures.append('100 Hz passband gain too low')
    else:
        print('  100 Hz gain : no measurement near 100 Hz')

    if g500 is not None:
        ok = -4.0 <= g500 <= -2.0
        print(f'  500 Hz gain : {g500:+.1f} dB  (need −2 to −4 dB)  {"PASS" if ok else "FAIL"}')
        if not ok: failures.append(f'500 Hz gain {g500:+.1f} dB outside −2…−4 dB window')
    else:
        print('  500 Hz gain : no measurement near 500 Hz')
        failures.append('no 500 Hz measurement')

    if g1000 is not None:
        ok = g1000 <= -10.0
        print(f'  1000 Hz gain: {g1000:+.1f} dB  (need ≤ −10 dB)  {"PASS" if ok else "FAIL"}')
        if not ok: failures.append('1000 Hz roll-off insufficient')
    else:
        print('  1000 Hz gain: no measurement near 1000 Hz')

    # --- Bode plot ---
    fig, ax = plt.subplots(figsize=(8, 5))

    f_theory = np.logspace(math.log10(50), math.log10(2000), 300)
    ax.semilogx(f_theory, [theory_db(f) for f in f_theory],
                'b--', linewidth=1.2, label='Theoretical (2nd-order Butterworth)')

    ax.semilogx(freqs_meas, gains_db,
                'ro-', markersize=5, linewidth=1.5, label='Measured')

    ax.axhline(-3.0, color='gray', linestyle=':', linewidth=1.0, label='−3 dB')
    ax.axvline(FC,   color='gray', linestyle=':', linewidth=1.0, label=f'fc = {FC:.0f} Hz')

    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Gain (dB)')
    ax.set_title('Bode Magnitude Plot — IIR LPF  fc = 500 Hz  (2nd-order Butterworth)')
    ax.legend()
    ax.grid(True, which='both', linestyle=':', alpha=0.6)
    ax.set_xlim(50, 2000)
    ax.set_ylim(-40, 5)

    out_file = 'bode_plot.png'
    plt.tight_layout()
    plt.savefig(out_file, dpi=150)
    print(f'\nBode plot saved to {out_file}')

    # --- Final verdict ---
    print()
    if failures:
        for f in failures:
            print(f'  FAIL: {f}')
        sys.exit(1)
    else:
        print('PASS')


if __name__ == '__main__':
    main()
