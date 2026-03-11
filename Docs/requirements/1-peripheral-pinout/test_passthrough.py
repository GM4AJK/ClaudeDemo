#!/usr/bin/env python3
"""
Req 1 — Peripheral Pinout: pass-through verification.

Stimulates the MCU with a 100 Hz sine at 1.0 Vpp via FY6800 CH1 and measures
the peak-to-peak voltage on both scope channels.  Checks that the ADC→DAC
pass-through ratio is within ±20% of unity.

Hardware required:
  - FY6800 CH1 → PA0 (100 Ω series protection resistor recommended)
  - PA4 → 4.7 kΩ → scope C2 probe tip; 10 nF from junction to GND
  - Scope C1 probe on FY6800 output
  - Both probe grounds connected to system GND
"""

import socket
import time
import re
import serial
import sys

# ── Instrument addresses ─────────────────────────────────────────────────────
FY6800_PORT   = '/dev/ttyUSB0'
SCOPE_IP      = '192.168.0.87'
SCOPE_PORT    = 5025

# ── Test parameters ───────────────────────────────────────────────────────────
FREQ_HZ       = 100
AMP_VPP       = 1.0
OFFSET_V      = 1.65
RATIO_MIN     = 0.80
RATIO_MAX     = 1.20


# ── FY6800 helper ─────────────────────────────────────────────────────────────
class FY6800:
    def __init__(self, port=FY6800_PORT):
        self.s = serial.Serial(port, 115200, timeout=1)
        time.sleep(0.5)

    def _cmd(self, c, wait=0.15):
        self.s.write((c + '\n').encode())
        time.sleep(wait)
        return self.s.read_all().decode(errors='replace').strip()

    def set_wave(self, ch, code):
        pfx = 'M' if ch == 0 else 'F'
        self._cmd(f'W{pfx}W{code:02d}')

    def set_freq(self, ch, hz):
        pfx = 'M' if ch == 0 else 'F'
        uhz = int(hz * 1_000_000)
        self._cmd(f'W{pfx}F{uhz:014d}')

    def set_amp(self, ch, v):
        pfx = 'M' if ch == 0 else 'F'
        self._cmd(f'W{pfx}A{v:.4f}')

    def set_offset(self, ch, v):
        pfx = 'M' if ch == 0 else 'F'
        self._cmd(f'W{pfx}O{v:.4f}')

    def output(self, ch, on):
        pfx = 'M' if ch == 0 else 'F'
        self._cmd(f'W{pfx}N{1 if on else 0}')

    def close(self):
        self.s.close()


# ── Scope helper ──────────────────────────────────────────────────────────────
class Scope:
    def __init__(self, ip=SCOPE_IP, port=SCOPE_PORT):
        self.s = socket.socket()
        self.s.connect((ip, port))
        self.s.settimeout(5)

    def send(self, cmd):
        self.s.sendall((cmd + '\n').encode())
        time.sleep(0.15)

    def query(self, cmd, delay=1.0):
        self.s.sendall((cmd + '\n').encode())
        time.sleep(delay)
        try:
            return self.s.recv(65536).decode(errors='replace').strip()
        except Exception:
            return ''

    def pkpk(self, ch):
        raw = self.query(f'C{ch}:PAVA? PKPK', delay=0.5)
        m = re.search(r'PKPK,([0-9.E+\-]+)V', raw)
        if not m:
            raise RuntimeError(f'Could not parse PKPK from: {raw!r}')
        return float(m.group(1))

    def close(self):
        self.s.close()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print('=== Req 1: Pass-through verification ===')

    print(f'Configuring FY6800 CH1: {FREQ_HZ} Hz sine, {AMP_VPP} Vpp, '
          f'{OFFSET_V} V offset …')
    fy = FY6800()
    fy.set_wave(0, 0)
    fy.set_freq(0, FREQ_HZ)
    fy.set_amp(0, AMP_VPP)
    fy.set_offset(0, OFFSET_V)
    fy.output(0, True)
    fy.close()
    print('  FY6800 configured.')

    print('Configuring scope …')
    sc = Scope()
    sc.send(':FUNC1 OFF')

    for ch in (1, 2):
        sc.send(f'C{ch}:ATTN 10')
        sc.send(f'C{ch}:CPL A1M')
        sc.send(f'C{ch}:VDIV 200E-3')
        sc.send(f'C{ch}:OFST 0')

    sc.send('TDIV 5E-3')
    sc.send('TRMD AUTO')
    time.sleep(2.0)

    print('Measuring …')
    v_in  = sc.pkpk(1)
    v_out = sc.pkpk(2)
    sc.close()

    ratio = v_out / v_in if v_in > 0 else 0.0

    print(f'  C1 Vpp (input)  = {v_in*1000:.1f} mV')
    print(f'  C2 Vpp (output) = {v_out*1000:.1f} mV')
    print(f'  Ratio Vout/Vin  = {ratio:.3f}')

    if RATIO_MIN <= ratio <= RATIO_MAX:
        print(f'\n  PASS  ({RATIO_MIN} ≤ {ratio:.3f} ≤ {RATIO_MAX})')
        sys.exit(0)
    else:
        print(f'\n  FAIL  ratio {ratio:.3f} outside [{RATIO_MIN}, {RATIO_MAX}]')
        sys.exit(1)


if __name__ == '__main__':
    main()
