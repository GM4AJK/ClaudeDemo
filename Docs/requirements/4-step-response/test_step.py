"""
test_step.py — Req 4 acceptance test

Applies a 50 Hz square wave and verifies the filter's step response shows
the expected 2nd-order Butterworth overshoot (~4.3%) and unity DC gain.

Pass conditions:
  - Overshoot : 1 % ≤ overshoot ≤ 8 %
  - DC gain   : 0.9 ≤ C2 AMPL / C1 AMPL ≤ 1.1

Instruments:
  FY6800  — /dev/ttyUSB0 (pyserial)
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

def scope_query(sc, cmd, delay=1.5):
	sc.sendall((cmd + '\n').encode())
	time.sleep(delay)
	try:
		return sc.recv(65536).decode(errors='replace').strip()
	except Exception:
		return ''

def parse_pava(resp):
	"""Extract numeric value from e.g. 'C2:PAVA AMPL,1.02E+00V'."""
	m = re.search(r'[\d.E+\-]+V', resp)
	if m:
		return float(m.group().rstrip('V'))
	return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
	print('=== Req 4 Step response test ===')

	# --- FY6800: square wave ---
	print('Configuring FY6800 ...')
	fy = FY6800('/dev/ttyUSB0')
	fy.set_wave(0, 1)       # square wave (code 01)
	fy.set_freq(0, 50)      # 50 Hz — 10 ms half-period >> filter settling time
	fy.set_amp(0, 1.0)      # 1.0 Vpp
	fy.set_offset(0, 1.65)  # 1.65 V DC offset
	fy.output(0, True)
	fy.close()
	print('  50 Hz square wave, 1.0 Vpp, 1.65 V offset, CH1 on')

	# --- Scope ---
	print('Configuring SDS824X HD ...')
	sc = socket.socket()
	sc.connect(('192.168.0.87', 5025))
	sc.settimeout(5)

	# Clear any FFT overlay left by a previous test
	scope_send(sc, ':FUNC1 OFF')

	# C1 and C2: AC coupled, 200 mV/div
	for ch in ('C1', 'C2'):
		scope_send(sc, f'{ch}:ATTN 10')
		scope_send(sc, f'{ch}:CPL A1M')
		scope_send(sc, f'{ch}:VDIV 200mV')
		scope_send(sc, f'{ch}:OFST 0V')

	# Trigger on C1 rising edge
	scope_send(sc, 'TRIG_MODE AUTO')
	scope_send(sc, 'C1:TRIG_SLOPE POS')
	scope_send(sc, 'TRIG_SELECT EDGE,SR,C1')

	# Use 5 ms/div (50 ms window = 2.5 cycles) for measurements — AMPL and
	# PKPK need multiple complete cycles to be statistically accurate.
	scope_send(sc, 'TDIV 5ms')
	print('  Settling 2 s ...')
	time.sleep(2.0)

	# --- Measure at wide timebase ---
	r_pkpk_c1 = scope_query(sc, 'C1:PAVA? PKPK')
	r_ampl_c1 = scope_query(sc, 'C1:PAVA? AMPL')
	r_pkpk_c2 = scope_query(sc, 'C2:PAVA? PKPK')
	r_ampl_c2 = scope_query(sc, 'C2:PAVA? AMPL')

	# Switch to 1 ms/div so the step response is visible on screen
	scope_send(sc, 'TDIV 1ms')
	sc.close()

	print(f'  C1 PKPK  : {r_pkpk_c1}')
	print(f'  C1 AMPL  : {r_ampl_c1}')
	print(f'  C2 PKPK  : {r_pkpk_c2}')
	print(f'  C2 AMPL  : {r_ampl_c2}')

	pkpk_c1 = parse_pava(r_pkpk_c1)
	ampl_c1 = parse_pava(r_ampl_c1)
	pkpk_c2 = parse_pava(r_pkpk_c2)
	ampl_c2 = parse_pava(r_ampl_c2)

	if any(v is None for v in (pkpk_c1, ampl_c1, pkpk_c2, ampl_c2)):
		print('FAIL: could not parse scope measurements')
		sys.exit(1)

	if pkpk_c1 < 1e-6 or ampl_c2 < 1e-6:
		print('FAIL: amplitude too small to measure')
		sys.exit(1)

	# Overshoot: C2 PKPK includes the overshoot peaks on both edges.
	# overshoot % = (C2_pkpk / C1_pkpk - 1) * 100
	overshoot = (pkpk_c2 / pkpk_c1 - 1.0) * 100.0
	dc_gain   = ampl_c2 / ampl_c1

	print(f'\n  C1 pk-pk     : {pkpk_c1*1000:.1f} mV')
	print(f'  C2 pk-pk     : {pkpk_c2*1000:.1f} mV')
	print(f'  Overshoot    : {overshoot:.2f} %  (theoretical ~4.3 %)')
	print(f'  C1 amplitude : {ampl_c1*1000:.1f} mV')
	print(f'  C2 amplitude : {ampl_c2*1000:.1f} mV')
	print(f'  DC gain      : {dc_gain:.4f}')

	failures = []
	ok_over = 1.0 <= overshoot <= 8.0
	ok_gain = 0.9 <= dc_gain  <= 1.1
	print(f'\n  Overshoot {overshoot:.2f} % in [1, 8] %   : {"PASS" if ok_over else "FAIL"}')
	print(f'  DC gain   {dc_gain:.4f}  in [0.9, 1.1] : {"PASS" if ok_gain else "FAIL"}')

	if not ok_over: failures.append(f'overshoot {overshoot:.2f} % outside [1, 8] %')
	if not ok_gain: failures.append(f'DC gain {dc_gain:.4f} outside [0.9, 1.1]')

	print()
	if failures:
		for f in failures:
			print(f'  FAIL: {f}')
		sys.exit(1)
	else:
		print('PASS')


if __name__ == '__main__':
	main()
