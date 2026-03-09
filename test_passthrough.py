"""
test_passthrough.py — Verify ADC→DAC pass-through on STM32G431KB

Sets FY6800 CH1 to 1 kHz sine at 1 Vpp, then reads input amplitude
on scope C1 (PA0) and output amplitude on scope C2 (PA4).
A pass-through ratio close to 1.0 confirms the firmware is running.
"""

import serial
import socket
import time

# ── FY6800 ────────────────────────────────────────────────────────────────────

FY_PORT = '/dev/ttyUSB0'
FY_BAUD = 115200

def fy_cmd(s, cmd, wait=0.15):
    s.write((cmd + '\n').encode())
    time.sleep(wait)
    return s.read_all().decode(errors='replace').strip()

def fy_setup(s, freq_hz, amp_v):
    uhz = int(freq_hz * 1_000_000)
    fy_cmd(s, f'WMW00')                   # sine
    fy_cmd(s, f'WMF{uhz:014d}')           # frequency
    fy_cmd(s, f'WMA{amp_v:.4f}')          # amplitude
    fy_cmd(s, f'WMO1.6500')               # +1.65 V DC bias — centres sine in ADC range (0–3.3 V)
    fy_cmd(s, 'WMN1')                     # output on

# ── SDS824X HD ────────────────────────────────────────────────────────────────

SCOPE_IP   = '192.168.0.87'
SCOPE_PORT = 5025

def scope_send(s, cmd):
    s.sendall((cmd + '\n').encode())
    time.sleep(0.2)

def scope_query(s, cmd, delay=1.0):
    s.sendall((cmd + '\n').encode())
    time.sleep(delay)
    try:
        return s.recv(65536).decode(errors='replace').strip()
    except socket.timeout:
        return ''

def scope_pkpk(s, ch):
    """Return peak-to-peak voltage on scope channel ch (1 or 2)."""
    raw = scope_query(s, f'C{ch}:PAVA? PKPK', delay=1.0)
    # Response: "C1:PAVA PKPK,1.00E+00V"
    try:
        value_str = raw.split(',')[1].rstrip('V').strip()
        return float(value_str)
    except Exception:
        print(f'  [warn] could not parse PKPK response: {repr(raw)}')
        return None

# ── Main ──────────────────────────────────────────────────────────────────────

FREQ_HZ = 100
AMP_V   = 1.0

print('=== Pass-through verification ===')
print(f'  Signal: {FREQ_HZ} Hz sine, {AMP_V} Vpp\n')

# Configure FY6800
print(f'Connecting to FY6800 on {FY_PORT}...')
fy = serial.Serial(FY_PORT, FY_BAUD, timeout=1)
time.sleep(0.5)
fy_setup(fy, FREQ_HZ, AMP_V)
print(f'  CH1 set: {FREQ_HZ} Hz sine, {AMP_V} Vpp, output ON')
fy.close()

# Allow signal to settle
time.sleep(1.0)

# Measure on scope
print(f'\nConnecting to scope at {SCOPE_IP}:{SCOPE_PORT}...')
sc = socket.socket()
sc.connect((SCOPE_IP, SCOPE_PORT))
sc.settimeout(5)

idn = scope_query(sc, '*IDN?', delay=0.5)
print(f'  Scope: {idn}')

# Configure scope for 1 kHz, ~1 Vpp signal
print('  Configuring scope...')
scope_send(sc, 'C1:TRA ON')          # CH1 on
scope_send(sc, 'C2:TRA ON')          # CH2 on
scope_send(sc, 'C1:ATTN 10')          # 10x probe on CH1
scope_send(sc, 'C2:ATTN 10')          # 10x probe on CH2
scope_send(sc, 'C1:CPL D1M')         # DC coupling CH1
scope_send(sc, 'C2:CPL D1M')         # DC coupling CH2
scope_send(sc, 'C1:VDIV 500MV')      # 500 mV/div → 1 Vpp fills ~2 div
scope_send(sc, 'C2:VDIV 500MV')
scope_send(sc, 'C1:OFST -1.65V')     # offset to centre DC-biased waveform
scope_send(sc, 'C2:OFST -1.65V')
scope_send(sc, 'TDIV 5MS')           # 5 ms/div → ~5 cycles of 100 Hz visible
scope_send(sc, 'TRMD AUTO')          # auto trigger so scope runs freely
scope_send(sc, 'TRIG_SELECT EDGE,SR,C1')  # edge trigger on CH1
time.sleep(2.0)                      # wait for scope to acquire and settle

pkpk_in  = scope_pkpk(sc, 1)   # C1 = PA0 (ADC input)
pkpk_out = scope_pkpk(sc, 2)   # C2 = PA4 (DAC output)

sc.close()

print(f'\n  C1 (PA0 input):  {pkpk_in:.3f} V p-p'  if pkpk_in  is not None else '\n  C1 (PA0 input):  measurement failed')
print(f'  C2 (PA4 output): {pkpk_out:.3f} V p-p' if pkpk_out is not None else '  C2 (PA4 output): measurement failed')

if pkpk_in and pkpk_out:
    ratio = pkpk_out / pkpk_in
    print(f'\n  Pass-through ratio (out/in): {ratio:.3f}')
    if 0.8 <= ratio <= 1.2:
        print('  PASS — ratio within ±20% of unity')
    else:
        print('  FAIL — ratio outside expected range (check connections and firmware)')
