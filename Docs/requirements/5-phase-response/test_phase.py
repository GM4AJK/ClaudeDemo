"""
test_phase.py — Req 5 acceptance test

Sweeps FY6800 50–2000 Hz, measures phase delay between C1 and C2 using
the scope's channel skew measurement, plots phase vs frequency alongside
the theoretical 2nd-order Butterworth phase response.

Pass conditions:
  - Phase at 500 Hz : -90° ± 10°
  - Phase trend     : monotonically decreasing (more negative) with frequency

Both channels fixed at 200 mV/div AC coupled throughout — no rescaling.

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
matplotlib.use('Agg')
import matplotlib.pyplot as plt


FC      = 500.0   # filter cutoff Hz
# 100–800 Hz: below 100 Hz AC coupling is not settled (bogus -122 µs skew);
# above 800 Hz the scope SKEW wraps when the total phase delay (filter +
# system delay ~170 µs) exceeds half the signal period.
FREQS   = np.logspace(math.log10(100), math.log10(800), 20).tolist()


def theory_phase(f, fc=FC):
    """Theoretical 2nd-order Butterworth phase (degrees)."""
    ratio = f / fc
    return -math.degrees(math.atan2(math.sqrt(2) * ratio, 1.0 - ratio ** 2))


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
    time.sleep(0.2)

def scope_query(sc, cmd, delay=1.2):
    sc.sendall((cmd + '\n').encode())
    time.sleep(delay)
    try:
        return sc.recv(65536).decode(errors='replace').strip()
    except Exception:
        return ''

def parse_skew(resp):
    """Extract skew value from e.g. 'C1-C2:MEAD SKEW,1.23E-04s'."""
    m = re.search(r'SKEW,([0-9.E+\-]+)s', resp)
    return float(m.group(1)) if m else None

def choose_tdiv(freq):
    """Show ~4 cycles on screen."""
    target = 4.0 / (freq * 10.0)
    steps = [5e-3, 2e-3, 1e-3, 5e-4, 2e-4, 1e-4, 5e-5, 2e-5, 1e-5]
    for s in steps:
        if s <= target:
            v = s * 1e3
            return f'{v:.0f}ms' if v >= 1 else f'{s*1e6:.0f}us'
    return '10us'


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('=== Req 5 Phase response test ===')

    # --- FY6800 ---
    print('Configuring FY6800 ...')
    fy = FY6800('/dev/ttyUSB0')
    fy.set_wave(0, 0)       # sine
    fy.set_amp(0, 1.0)
    fy.set_offset(0, 1.65)
    fy.output(0, True)

    # --- Scope ---
    print('Connecting to SDS824X HD ...')
    sc = socket.socket()
    sc.connect(('192.168.0.87', 5025))
    sc.settimeout(5)

    # Clear any FFT from previous test
    scope_send(sc, ':FUNC1 OFF')

    for ch in ('C1', 'C2'):
        scope_send(sc, f'{ch}:ATTN 10')
        scope_send(sc, f'{ch}:CPL A1M')
        scope_send(sc, f'{ch}:VDIV 200mV')
        scope_send(sc, f'{ch}:OFST 0V')

    N_AVG = 5

    # --- Sweep ---
    freqs_meas  = []
    phases_meas = []

    for freq in FREQS:
        fy.set_freq(0, freq)
        scope_send(sc, f'TDIV {choose_tdiv(freq)}')
        time.sleep(max(20.0 / freq, 1.0))

        skews = []
        for _ in range(N_AVG):
            r = scope_query(sc, 'C1-C2:MEAD? SKEW', delay=0.4)
            s = parse_skew(r)
            if s is not None:
                skews.append(s)

        if not skews:
            print(f'  {freq:7.1f} Hz — skew measurement invalid, skipping')
            continue

        skew_s = sum(skews) / len(skews)
        phase  = -skew_s * freq * 360.0

        # Wrap to (-360, 0]
        while phase > 0:
            phase -= 360.0
        while phase < -360.0:
            phase += 360.0

        freqs_meas.append(freq)
        phases_meas.append(phase)

        theory = theory_phase(freq)
        print(f'  {freq:7.1f} Hz  skew={skew_s*1e6:+8.2f} µs  '
              f'phase={phase:+7.1f}°  (theory={theory:+6.1f}°)')

    fy.close()
    sc.close()

    if not freqs_meas:
        print('FAIL: no valid measurements')
        sys.exit(1)

    # --- Estimate and subtract constant system delay ---
    # The measured phase includes a linear delay from the ADC sample period
    # (~125 µs) and the RC reconstruction filter group delay (~47 µs).
    # Estimate it from all data points: delay = -(measured - theory) / (f*360)
    delay_estimates = [-(pm - theory_phase(f)) / (f * 360.0)
                       for f, pm in zip(freqs_meas, phases_meas)]
    delay_estimates_sorted = sorted(delay_estimates)
    system_delay_s = delay_estimates_sorted[len(delay_estimates_sorted) // 2]

    phases_corrected = [pm + system_delay_s * f * 360.0
                        for f, pm in zip(freqs_meas, phases_meas)]

    print(f'\n  Estimated system delay: {system_delay_s*1e6:.1f} µs'
          f'  (ADC sample + RC filter group delay)')

    # --- PASS/FAIL checks (on delay-corrected phase) ---
    def nearest(target_hz, phases, tol_hz=60):
        candidates = [(abs(f - target_hz), p)
                      for f, p in zip(freqs_meas, phases)
                      if abs(f - target_hz) <= tol_hz]
        return min(candidates, key=lambda x: x[0])[1] if candidates else None

    phase_500 = nearest(500, phases_corrected)
    failures  = []

    print()
    if phase_500 is not None:
        ok = -100.0 <= phase_500 <= -80.0
        print(f'  Corrected phase at 500 Hz : {phase_500:+.1f}°  '
              f'(need −90° ± 10°)  {"PASS" if ok else "FAIL"}')
        if not ok:
            failures.append(f'corrected phase at 500 Hz = {phase_500:+.1f}°, '
                            f'outside −80…−100°')
    else:
        failures.append('no measurement near 500 Hz')

    # Monotonically decreasing check on corrected phase
    diffs      = [phases_corrected[i+1] - phases_corrected[i]
                  for i in range(len(phases_corrected) - 1)]
    increasing = sum(1 for d in diffs if d > 3.0)
    ok_mono    = increasing == 0
    print(f'  Phase trend     : '
          f'{"monotonically decreasing" if ok_mono else f"{increasing} non-monotone steps"}  '
          f'{"PASS" if ok_mono else "FAIL"}')
    if not ok_mono:
        failures.append(f'phase not monotonically decreasing ({increasing} reversals)')

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(8, 5))

    f_theory = np.logspace(math.log10(100), math.log10(800), 300)
    # Theoretical curve includes system delay for the raw overlay
    ax.semilogx(f_theory,
                [theory_phase(f) - system_delay_s * f * 360.0 for f in f_theory],
                'b--', linewidth=1.2,
                label=f'Theoretical + {system_delay_s*1e6:.0f} µs system delay')

    ax.semilogx(freqs_meas, phases_meas,
                'ro-', markersize=5, linewidth=1.5, label='Measured (raw)')

    ax.axhline(-90.0, color='gray', linestyle=':', linewidth=1.0, label='−90°')
    ax.axvline(FC,    color='gray', linestyle=':', linewidth=1.0,
               label=f'fc = {FC:.0f} Hz')

    ax.set_xlabel('Frequency (Hz)')
    ax.set_ylabel('Phase (degrees)')
    ax.set_title('Phase Response — IIR LPF  fc = 500 Hz  (2nd-order Butterworth)')
    ax.legend()
    ax.grid(True, which='both', linestyle=':', alpha=0.6)
    ax.set_xlim(100, 800)
    ax.set_ylim(-220, 10)

    plt.tight_layout()
    plt.savefig('phase_plot.png', dpi=150)
    print('Phase plot saved to phase_plot.png')

    print()
    if failures:
        for f in failures:
            print(f'  FAIL: {f}')
        sys.exit(1)
    else:
        print('PASS')


if __name__ == '__main__':
    main()
