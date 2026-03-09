"""
test_passthrough.py — Req 1 acceptance test

Verifies that a signal applied to PA0 (ADC1 IN1) appears unchanged at PA4 (DAC1 OUT1).

Pass condition:  0.8 <= V_out_pkpk / V_in_pkpk <= 1.2

Instruments:
  FY6800  — /dev/ttyUSB0 (115200 baud, pyserial)
  SDS824X — 192.168.0.87:5025 (SCPI/TCP)
"""

import re
import socket
import sys
import time

import serial


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

	def _ch(self, ch):
		return 'M' if ch == 0 else 'F'

	def set_wave(self, ch, code):
		self._cmd(f'W{self._ch(ch)}W{code:02d}')

	def set_freq(self, ch, hz):
		self._cmd(f'W{self._ch(ch)}F{int(hz * 1_000_000):014d}')

	def set_amp(self, ch, v):
		self._cmd(f'W{self._ch(ch)}A{v:.4f}')

	def set_offset(self, ch, v):
		self._cmd(f'W{self._ch(ch)}O{v:.4f}')

	def output(self, ch, on):
		self._cmd(f'W{self._ch(ch)}N{1 if on else 0}')

	def close(self):
		self.s.close()


# ---------------------------------------------------------------------------
# SDS824X HD helpers
# ---------------------------------------------------------------------------

def scope_send(sc, cmd):
	sc.sendall((cmd + '\n').encode())
	time.sleep(0.2)


def scope_query(sc, cmd, delay=1.5):
	sc.sendall((cmd + '\n').encode())
	time.sleep(delay)
	try:
		return sc.recv(65536).decode(errors='replace').strip()
	except Exception:
		return ''


def parse_pkpk(response):
	"""Extract peak-to-peak voltage from e.g. 'C1:PAVA PKPK,1.23E+00V'."""
	m = re.search(r'PKPK,([0-9.E+\-]+)V', response)
	if m:
		return float(m.group(1))
	return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
	print('=== Req 1 pass-through test ===')

	# --- FY6800: 100 Hz sine, 1.0 Vpp, 1.65 V offset ---
	print('Configuring FY6800 ...')
	fy = FY6800('/dev/ttyUSB0')
	fy.set_wave(0, 0)       # sine
	fy.set_freq(0, 100)     # 100 Hz
	fy.set_amp(0, 1.0)      # 1.0 Vpp
	fy.set_offset(0, 1.65)  # 1.65 V DC offset (centres signal in ADC range)
	fy.output(0, True)      # CH1 on
	fy.close()
	print('  100 Hz sine, 1.0 Vpp, 1.65 V offset, CH1 on')

	# --- SDS824X HD: configure C1 (input) and C2 (output) ---
	print('Configuring SDS824X HD ...')
	sc = socket.socket()
	sc.connect(('192.168.0.87', 5025))
	sc.settimeout(5)

	for ch in ('C1', 'C2'):
		scope_send(sc, f'{ch}:ATTN 10')
		scope_send(sc, f'{ch}:CPL D1M')
		scope_send(sc, f'{ch}:VDIV 500mV')
		scope_send(sc, f'{ch}:OFST -1.65V')

	scope_send(sc, 'TDIV 5ms')  # ~2 cycles of 100 Hz visible

	print('  C1/C2: 10x, DC 1MΩ, 500 mV/div, -1.65 V offset; TDIV 5 ms')
	print('  Settling ...')
	time.sleep(2.0)

	# --- Measure peak-to-peak on both channels ---
	r1 = scope_query(sc, 'C1:PAVA? PKPK')
	r2 = scope_query(sc, 'C2:PAVA? PKPK')
	sc.close()

	print(f'  C1 response: {r1}')
	print(f'  C2 response: {r2}')

	v_in  = parse_pkpk(r1)
	v_out = parse_pkpk(r2)

	if v_in is None or v_out is None:
		print('FAIL: could not parse scope measurement')
		sys.exit(1)

	ratio = v_out / v_in
	print(f'\n  V_in  = {v_in:.4f} V pk-pk')
	print(f'  V_out = {v_out:.4f} V pk-pk')
	print(f'  Ratio = {ratio:.4f}')

	if 0.8 <= ratio <= 1.2:
		print('\nPASS')
	else:
		print(f'\nFAIL: ratio {ratio:.4f} outside [0.8, 1.2]')
		sys.exit(1)


if __name__ == '__main__':
	main()
