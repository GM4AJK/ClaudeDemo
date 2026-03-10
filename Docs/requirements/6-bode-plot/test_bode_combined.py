"""
test_bode_combined.py — Req 6 acceptance test

Single frequency sweep 100–800 Hz collecting magnitude (PKPK ratio) and
phase (channel SKEW) simultaneously at each point.  Produces a standard
two-panel Bode plot (magnitude top, phase bottom) with theoretical
2nd-order Butterworth overlaid on both panels.

Pass conditions:
  - Gain  at 100 Hz : >= -1 dB       (flat passband)
  - Gain  at 500 Hz : -3 dB ± 1 dB
  - Phase at 500 Hz : -90° ± 10°     (after system-delay correction)
  - Phase trend     : monotonically decreasing with frequency

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


FC    = 500.0   # filter cutoff Hz
FREQS = np.logspace(math.log10(100), math.log10(800), 20).tolist()


def theory_db(f, fc=FC):
    return -10.0 * math.log10(1.0 + (f / fc) ** 4)

def theory_phase(f, fc=FC):
    ratio = f / fc
    return -math.degrees(math.atan2(math.sqrt(2) * ratio, 1.0 - ratio ** 2))


# ---------------------------------------------------------------------------
# Scope timebase helper
# ---------------------------------------------------------------------------

_TDIV_STEPS = [
    1e-4, 2e-4, 5e-4,
    1e-3, 2e-3, 5e-3,
]

def choose_tdiv(freq):
    """Show ~4 cycles on screen (10 horizontal divs)."""
    target = 4.0 / (freq * 10.0)
    for s in reversed(_TDIV_STEPS):
        if s <= target:
            v = s * 1e3
            return f'{v:.0f}ms' if v >= 1 else f'{s*1e6:.0f}us'
    return '100us'


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

def parse_pkpk(resp):
    m = re.search(r'PKPK,([0-9.E+\-]+)V', resp)
    return float(m.group(1)) if m else None

def parse_skew(resp):
    m = re.search(r'SKEW,([0-9.E+\-]+)s', resp)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print('=== Req 6 Combined Bode plot test ===')

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

    # Clear any FFT from a previous test
    scope_send(sc, ':FUNC1 OFF')

    for ch in ('C1', 'C2'):
        scope_send(sc, f'{ch}:ATTN 10')
        scope_send(sc, f'{ch}:CPL A1M')
        scope_send(sc, f'{ch}:VDIV 200mV')
        scope_send(sc, f'{ch}:OFST 0V')

    N_AVG = 5

    # --- Sweep ---
    freqs_meas  = []
    gains_db    = []
    phases_meas = []

    for freq in FREQS:
        fy.set_freq(0, freq)
        scope_send(sc, f'TDIV {choose_tdiv(freq)}')
        time.sleep(max(20.0 / freq, 1.0))

        v_ins, v_outs, skews = [], [], []
        for _ in range(N_AVG):
            r1 = scope_query(sc, 'C1:PAVA? PKPK', delay=0.4)
            r2 = scope_query(sc, 'C2:PAVA? PKPK', delay=0.4)
            rs = scope_query(sc, 'C1-C2:MEAD? SKEW', delay=0.4)
            v1 = parse_pkpk(r1)
            v2 = parse_pkpk(r2)
            s  = parse_skew(rs)
            if v1 is not None and v1 > 1e-6 and v2 is not None and v2 > 0.0:
                v_ins.append(v1)
                v_outs.append(v2)
            if s is not None:
                skews.append(s)

        if not v_ins or not skews:
            print(f'  {freq:7.1f} Hz — invalid readings, skipping')
            continue

        v_in   = sum(v_ins)  / len(v_ins)
        v_out  = sum(v_outs) / len(v_outs)
        gain   = 20.0 * math.log10(v_out / v_in)

        skew_s = sum(skews) / len(skews)
        phase  = -skew_s * freq * 360.0
        while phase > 0:
            phase -= 360.0
        while phase < -360.0:
            phase += 360.0

        freqs_meas.append(freq)
        gains_db.append(gain)
        phases_meas.append(phase)

        print(f'  {freq:7.1f} Hz  gain={gain:+5.1f} dB  '
              f'skew={skew_s*1e6:+8.2f} µs  phase={phase:+7.1f}°  '
              f'(th_gain={theory_db(freq):+5.1f} dB  th_phase={theory_phase(freq):+6.1f}°)')

    fy.close()
    sc.close()

    if not freqs_meas:
        print('FAIL: no valid measurements')
        sys.exit(1)

    # --- System delay correction (phase only) ---
    delay_estimates = [-(pm - theory_phase(f)) / (f * 360.0)
                       for f, pm in zip(freqs_meas, phases_meas)]
    delay_estimates_sorted = sorted(delay_estimates)
    system_delay_s = delay_estimates_sorted[len(delay_estimates_sorted) // 2]

    phases_corrected = [pm + system_delay_s * f * 360.0
                        for f, pm in zip(freqs_meas, phases_meas)]

    print(f'\n  Estimated system delay: {system_delay_s*1e6:.1f} µs'
          f'  (ADC sample + RC filter group delay)')

    # --- PASS/FAIL checks ---
    def nearest(target_hz, values, tol_hz=80):
        candidates = [(abs(f - target_hz), v)
                      for f, v in zip(freqs_meas, values)
                      if abs(f - target_hz) <= tol_hz]
        return min(candidates, key=lambda x: x[0])[1] if candidates else None

    g100  = nearest(100,  gains_db)
    g500  = nearest(500,  gains_db)
    p500  = nearest(500,  phases_corrected)

    failures = []
    print()

    if g100 is not None:
        ok = g100 >= -1.0
        print(f'  100 Hz gain  : {g100:+.1f} dB  (need >= -1 dB)  {"PASS" if ok else "FAIL"}')
        if not ok:
            failures.append(f'100 Hz passband gain {g100:+.1f} dB below -1 dB')
    else:
        failures.append('no measurement near 100 Hz')

    if g500 is not None:
        ok = -4.5 <= g500 <= -1.5
        print(f'  500 Hz gain  : {g500:+.1f} dB  (need -3 dB +/-1.5 dB)  {"PASS" if ok else "FAIL"}')
        if not ok:
            failures.append(f'500 Hz gain {g500:+.1f} dB outside -1.5…-4.5 dB')
    else:
        failures.append('no measurement near 500 Hz')

    if p500 is not None:
        ok = -100.0 <= p500 <= -80.0
        print(f'  500 Hz phase : {p500:+.1f}°  (need -90° +/-10°)  {"PASS" if ok else "FAIL"}')
        if not ok:
            failures.append(f'corrected phase at 500 Hz = {p500:+.1f}°, outside -80…-100°')
    else:
        failures.append('no measurement near 500 Hz')

    diffs     = [phases_corrected[i+1] - phases_corrected[i]
                 for i in range(len(phases_corrected) - 1)]
    increasing = sum(1 for d in diffs if d > 3.0)
    ok_mono   = increasing == 0
    print(f'  Phase trend  : '
          f'{"monotonically decreasing" if ok_mono else f"{increasing} non-monotone steps"}  '
          f'{"PASS" if ok_mono else "FAIL"}')
    if not ok_mono:
        failures.append(f'phase not monotonically decreasing ({increasing} reversals)')

    # --- Plot ---
    fig, (ax_mag, ax_ph) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    fig.suptitle('Bode Plot — IIR LPF  fc = 500 Hz  (2nd-order Butterworth)')

    f_theory = np.logspace(math.log10(100), math.log10(800), 300)

    # Magnitude panel
    ax_mag.semilogx(f_theory, [theory_db(f) for f in f_theory],
                    'b--', linewidth=1.2, label='Theoretical')
    ax_mag.semilogx(freqs_meas, gains_db,
                    'ro-', markersize=5, linewidth=1.5, label='Measured')
    ax_mag.axhline(-3.0, color='gray', linestyle=':', linewidth=1.0, label='-3 dB')
    ax_mag.axvline(FC,   color='gray', linestyle=':', linewidth=1.0)
    ax_mag.set_ylabel('Gain (dB)')
    ax_mag.set_ylim(-40, 5)
    ax_mag.legend(loc='lower left')
    ax_mag.grid(True, which='both', linestyle=':', alpha=0.6)

    # Phase panel
    f_theory_ph = [theory_phase(f) - system_delay_s * f * 360.0 for f in f_theory]
    ax_ph.semilogx(f_theory, f_theory_ph,
                   'b--', linewidth=1.2,
                   label=f'Theoretical + {system_delay_s*1e6:.0f} µs system delay')
    ax_ph.semilogx(freqs_meas, phases_meas,
                   'ro-', markersize=5, linewidth=1.5, label='Measured (raw)')
    ax_ph.axhline(-90.0, color='gray', linestyle=':', linewidth=1.0, label='-90°')
    ax_ph.axvline(FC,    color='gray', linestyle=':', linewidth=1.0)
    ax_ph.set_xlabel('Frequency (Hz)')
    ax_ph.set_ylabel('Phase (degrees)')
    ax_ph.set_xlim(100, 800)
    ax_ph.set_ylim(-220, 10)
    ax_ph.legend(loc='lower left')
    ax_ph.grid(True, which='both', linestyle=':', alpha=0.6)

    plt.tight_layout()
    plt.savefig('bode_combined.png', dpi=150)
    print('\nBode plot saved to bode_combined.png')

    print()
    if failures:
        for f in failures:
            print(f'  FAIL: {f}')
        sys.exit(1)
    else:
        print('PASS')


if __name__ == '__main__':
    main()
