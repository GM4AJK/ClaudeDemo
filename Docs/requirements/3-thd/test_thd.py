"""
test_thd.py — Req 3 acceptance test

Measures THD of the IIR filter output using the SDS824X scope FFT.

Setup:
  - FY6800 CH1: 200 Hz sine, 1.0 Vpp, 1.65 V DC offset
  - Scope C1: input, AC coupled, 200 mV/div  (visible reference)
  - Scope C2: output, AC coupled, 200 mV/div
  - FUNC1 FFT on C2: FlatTop window, 0–4000 Hz span
  - FFT left on screen after test

Pass condition: THD < 1%

Instruments:
  FY6800  — /dev/ttyUSB0 (pyserial)
  SDS824X — 192.168.0.87:5025 (SCPI/TCP)
"""

import re
import socket
import sys
import time

import serial


FUND_FREQ   = 200.0    # Hz
N_HARMONICS = 10       # fundamental + harmonics 2–10
THD_LIMIT   = 1.0      # % pass threshold


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

def parse_peaks(resp):
	"""
	Parse ':FUNC1:FFT:SEAR:RES?' response.
	Format: 'Peaks,1,200.0,−9.2;2,400.0,−55.1;...'
	Returns list of (freq_hz, amp_dbvrms) tuples.
	"""
	return [(float(f), float(a))
	        for f, a in re.findall(r'\d+,([0-9.E+\-]+),([0-9.E+\-]+)', resp)]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
	print('=== Req 3 THD test ===')

	# --- FY6800 ---
	print('Configuring FY6800 ...')
	fy = FY6800('/dev/ttyUSB0')
	fy.set_wave(0, 0)
	fy.set_freq(0, FUND_FREQ)
	fy.set_amp(0, 1.0)
	fy.set_offset(0, 1.65)
	fy.output(0, True)
	fy.close()
	print(f'  {FUND_FREQ:.0f} Hz sine, 1.0 Vpp, 1.65 V offset, CH1 on')

	# --- Scope ---
	print('Configuring SDS824X HD ...')
	sc = socket.socket()
	sc.connect(('192.168.0.87', 5025))
	sc.settimeout(5)

	# C1: input waveform — stays on screen as reference
	scope_send(sc, 'C1:ATTN 10')
	scope_send(sc, 'C1:CPL A1M')
	scope_send(sc, 'C1:VDIV 200mV')
	scope_send(sc, 'C1:OFST 0V')

	# C2: output waveform
	scope_send(sc, 'C2:ATTN 10')
	scope_send(sc, 'C2:CPL A1M')
	scope_send(sc, 'C2:VDIV 200mV')
	scope_send(sc, 'C2:OFST 0V')

	# Timebase: 5 ms/div shows ~1 cycle of 200 Hz
	scope_send(sc, 'TDIV 5ms')

	# FUNC1 FFT on C2 — FlatTop, 0–4000 Hz, left on screen after test
	scope_send(sc, ':FUNC1:OPER FFT')
	scope_send(sc, ':FUNC1:SOUR1 C2')
	scope_send(sc, ':FUNC1:FFT:WIND FLATtop')
	scope_send(sc, ':FUNC1:FFT:SPAN 4000')
	scope_send(sc, ':FUNC1:FFT:HCEN 2000')
	scope_send(sc, ':FUNC1:FFT:POIN 2M')
	scope_send(sc, ':FUNC1:FFT:UNIT DBVR')
	scope_send(sc, ':FUNC1:FFT:MODE NORM')
	scope_send(sc, ':FUNC1 ON')

	# Peak search — threshold well below expected 1% harmonic level
	# 1% of fundamental (-9 dBVrms) = -49 dBVrms; use -60 dBVrms for margin
	scope_send(sc, ':FUNC1:FFT:SEAR PEAK')
	scope_send(sc, ':FUNC1:FFT:SEAR:THR -60.0')

	print('  FFT configured — settling 3 s ...')
	time.sleep(3.0)

	# --- Read peaks ---
	raw = scope_query(sc, ':FUNC1:FFT:SEAR:RES?', delay=2.0)
	sc.close()

	print(f'  Raw peak response: {raw}')
	peaks = parse_peaks(raw)

	if not peaks:
		print('FAIL: no FFT peaks returned')
		sys.exit(1)

	# --- Identify fundamental ---
	fund = None
	for f, a in peaks:
		if abs(f - FUND_FREQ) / FUND_FREQ < 0.1:   # within 10% of 200 Hz
			if fund is None or a > fund[1]:
				fund = (f, a)

	if fund is None:
		print(f'FAIL: fundamental not found near {FUND_FREQ:.0f} Hz in peaks: {peaks}')
		sys.exit(1)

	fund_freq, fund_db = fund
	print(f'\n  Fundamental: {fund_freq:.1f} Hz  {fund_db:.2f} dBVrms')

	# --- Identify harmonics 2–N ---
	harmonic_v2 = []
	for h in range(2, N_HARMONICS + 1):
		expected = FUND_FREQ * h
		candidates = [(f, a) for f, a in peaks
		              if abs(f - expected) / expected < 0.05]
		if candidates:
			hf, ha = max(candidates, key=lambda p: p[1])
			hv_rms = 10.0 ** (ha / 20.0)   # dBVrms → Vrms
			harmonic_v2.append(hv_rms ** 2)
			print(f'  Harmonic {h:2d}: {hf:7.1f} Hz  {ha:+.2f} dBVrms  '
			      f'({ha - fund_db:+.1f} dBc)')
		else:
			print(f'  Harmonic {h:2d}: {expected:7.1f} Hz  — below threshold')

	# --- Compute THD ---
	fund_v_rms = 10.0 ** (fund_db / 20.0)
	if harmonic_v2:
		thd = (sum(harmonic_v2) ** 0.5) / fund_v_rms * 100.0
	else:
		thd = 0.0

	print(f'\n  THD = {thd:.4f} %')

	if thd < THD_LIMIT:
		print(f'PASS  (limit: {THD_LIMIT} %)')
	else:
		print(f'FAIL  (limit: {THD_LIMIT} %)')
		sys.exit(1)


if __name__ == '__main__':
	main()
