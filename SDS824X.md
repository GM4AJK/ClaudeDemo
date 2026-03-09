# Siglent SDS824X HD — SCPI Reference

Scope: **Siglent SDS824X HD** (model SDS08A0X803547)
Firmware: 3.8.12.1.1.3.6
Interface: TCP port 5025, SCPI over raw socket
Python: `socket.connect(('192.168.0.87', 5025))`

---

## Important Behavioural Notes

- **Set commands return no response.** Do not wait for a reply after a set command or
  the socket will block until timeout. Only query commands (ending `?`) return data.
- **Allow settling time** after configuring FFT before querying results (~1–2 seconds).
- Commands use short-form mnemonics (e.g. `FUNC1` not `FUNCtion1`).

---

## Time-Domain Measurements

```
Cx:PAVA? FREQ          measured frequency on channel x (x = 1–4)
Cx:PAVA? AMPL          amplitude (high–low)
Cx:PAVA? PKPK          peak-to-peak
Cx:PAVA? PWID          positive pulse width
Cx:PAVA? MEAN          mean voltage
Cx:PAVA? RMS           RMS voltage
C1-C2:MEAD? SKEW       time offset between two channels
```

Response format: `Cx:PAVA FREQ,1.00E+03Hz`

---

## Raw Waveform Data Transfer

```
Cx:WF? DESC            binary WAVEDESC header block
Cx:WF? DAT2            raw 8-bit signed sample data (binary)
```

### WAVEDESC binary offsets (all little-endian)
| Offset | Type | Field |
|--------|------|-------|
| 176 | float32 | horiz_interval (seconds per sample) |
| 116 | int32 | num_points |
| 184 | float32 | v_min (volts) |
| 192 | float32 | v_max (volts) |

### Typical acquisition parameters
- Sample rate: 500 MSa/s → horiz_interval = 2e-9 s
- Points: 2,500,000 (2.5M samples = 5ms of data)
- Data: 8-bit signed int (`np.frombuffer(..., dtype=np.int8)`)
- Scale: `volts = (raw - raw.min()) / (raw.max() - raw.min()) * (v_max - v_min) + v_min`

### Python snippet — fetch and scale samples
```python
import socket, time, struct
import numpy as np

s = socket.socket()
s.connect(('192.168.0.87', 5025))
s.settimeout(10)

def recv_all(s, timeout=8):
    data = b''
    s.settimeout(timeout)
    try:
        while True:
            chunk = s.recv(131072)
            if not chunk: break
            data += chunk
    except: pass
    return data

# Descriptor
s.sendall(b'C1:WF? DESC\n'); time.sleep(0.5)
desc = recv_all(s, 2)
wdesc = desc[desc.find(b'WAVEDESC'):]
horiz_int  = struct.unpack_from('<f', wdesc, 176)[0]
num_points = struct.unpack_from('<i', wdesc, 116)[0]
v_min      = struct.unpack_from('<f', wdesc, 184)[0]
v_max      = struct.unpack_from('<f', wdesc, 192)[0]

# Samples
s.sendall(b'C1:WF? DAT2\n'); time.sleep(1)
raw = recv_all(s, 8)
prefix = raw.find(b'#')
n_digits = int(raw[prefix+1:prefix+2])
data_len = int(raw[prefix+2:prefix+2+n_digits])
samples = np.frombuffer(raw[prefix+2+n_digits:prefix+2+n_digits+data_len], dtype=np.int8).astype(float)
s_min, s_max = samples.min(), samples.max()
volts = (samples - s_min) / (s_max - s_min) * (v_max - v_min) + v_min
volts -= volts.mean()  # remove DC
```

---

## FFT via SCPI

**Command family: `:FUNCtion<x>:` (abbreviated `FUNC<x>:`), where x = 1–4.**

Do NOT use `F1:DEF`, `MATH:DEFINE`, `MATH:FFT`, or VBS — these are wrong families for
this firmware and will timeout or return command errors.

### Configuration
```
:FUNC1:OPER FFT          set F1 operation to FFT
:FUNC1:SOUR1 C1          source channel (C1–C4)
:FUNC1 ON                enable and display F1
:FUNC1:FFT:WIND HANNing  window: RECT / HANNing / HAMMing / BLACkman / FLATtop
:FUNC1:FFT:SPAN 15000    frequency span in Hz
:FUNC1:FFT:HCEN 7500     centre frequency in Hz
:FUNC1:FFT:POIN 2M       FFT points: 1k / 2k / 5k / 10k / 20k / 50k / 100k / 200k / 500k / 1M / 2M
:FUNC1:FFT:UNIT DBVR     vertical unit: DBVrms / Vrms / DBm
:FUNC1:FFT:MODE NORM     acquisition mode: NORMal / MAXHold / AVERage
:FUNC1 OFF               disable F1 when done
```

### Query configuration back
```
:FUNC1:OPER?    → FFT
:FUNC1:SOUR1?   → C1
:FUNC1:FFT:WIND?  → HANNing
:FUNC1:FFT:SPAN?  → 1.50E+04
:FUNC1:FFT:POIN?  → 2M
:FUNC1:FFT:UNIT?  → DBVrms
```

### Peak search
```
:FUNC1:FFT:SEAR PEAK         enable peak detection
:FUNC1:FFT:SEAR:THR -80.0    threshold in dBVrms (try -80 first, lower to -100 if needed)
:FUNC1:FFT:SEAR:RES?         query results
```

Response format:
```
Peaks,1,9.536743E+02,-9.201436E+00;2,2.000000E+03,-7.53E+01;
       ^  ^freq (Hz)  ^amp (dBVrms)
```

### NOT working
- `WAV:SOUR F1` / `WAV:SOUR FUNC1` + `WAV:DATA?` — times out; raw FFT bin download
  is documented in EN11F but does not work in practice on this firmware
- `Cx:PAVA? THD`, `PACU? THD`, `Cx:PAVA? SINAD`, `Cx:PAVA? SFDR` — not available

---

## THD Calculation from Peak Search

FlatTop window gives best amplitude accuracy for THD. Hanning is fine for frequency
measurement. Narrow the span to just above the highest harmonic of interest.

```python
import re, numpy as np, socket, time

def send(s, cmd): s.sendall((cmd+'\n').encode()); time.sleep(0.2)
def query(s, cmd, delay=1.5):
    s.sendall((cmd+'\n').encode()); time.sleep(delay)
    try: return s.recv(65536).decode(errors='replace').strip()
    except: return ''

s = socket.socket(); s.connect(('192.168.0.87', 5025)); s.settimeout(4)

# Configure
send(s, ':FUNC1:OPER FFT')
send(s, ':FUNC1:SOUR1 C1')
send(s, ':FUNC1 ON')
send(s, ':FUNC1:FFT:WIND FLATTOP')
send(s, ':FUNC1:FFT:SPAN 15000')
send(s, ':FUNC1:FFT:HCEN 7500')
send(s, ':FUNC1:FFT:POIN 2M')
send(s, ':FUNC1:FFT:UNIT DBVR')
send(s, ':FUNC1:FFT:SEAR PEAK')
send(s, ':FUNC1:FFT:SEAR:THR -80.0')
time.sleep(2.0)  # let FFT settle

raw = query(s, ':FUNC1:FFT:SEAR:RES?', delay=2.0)
peaks = [(float(f), float(a)) for f, a in re.findall(r'\d+,([0-9.E+\-]+),([0-9.E+\-]+)', raw)]

# Find fundamental (highest amplitude)
fund_freq, fund_db = max(peaks, key=lambda p: p[1])

# Find harmonics within 5% of expected frequency
harmonic_dbs = []
for h in range(2, 11):
    expected = fund_freq * h
    candidates = [(f, a) for f, a in peaks if abs(f - expected) / expected < 0.05]
    if candidates:
        hf, ha = max(candidates, key=lambda p: p[1])
        harmonic_dbs.append(ha - fund_db)  # dBc

thd_pct = np.sqrt(sum(10**(db/10) for db in harmonic_dbs)) * 100 if harmonic_dbs else 0.0
thd_dbc = 20 * np.log10(thd_pct / 100 + 1e-12)
print(f'Fundamental: {fund_freq:.2f} Hz  {fund_db:.2f} dBVrms')
print(f'THD = {thd_pct:.4f}%  ({thd_dbc:.1f} dBc)')

send(s, ':FUNC1 OFF')
s.close()
```

---

## NumPy FFT Alternative (when scope FFT isn't needed)

Slower (~3s for 2.5M sample download) but gives full spectrum plot and works without
configuring the scope's math channel. See waveform fetch snippet above, then:

```python
N = len(volts)
window   = np.hanning(N)
fft_vals = np.fft.rfft(volts * window)
freqs    = np.fft.rfftfreq(N, d=horiz_int)
mag      = np.abs(fft_vals)
mag_db   = 20 * np.log10(mag / mag.max() + 1e-12)

# Fundamental: search around known frequency
lo = np.argmin(np.abs(freqs - target_freq * 0.8))
hi = np.argmin(np.abs(freqs - target_freq * 1.2))
fund_bin = lo + np.argmax(mag[lo:hi])

# Harmonics: exact bin multiples
harmonic_mags = [mag[fund_bin * h] for h in range(2, 11) if fund_bin * h < len(mag)]
thd_pct = np.sqrt(sum(m**2 for m in harmonic_mags)) / mag[fund_bin] * 100
```

**Freq resolution** = sample_rate / num_points = 500e6 / 2.5e6 = **200 Hz per bin**.
For better resolution on low frequencies, reduce scope timebase to capture more cycles
with fewer total samples, or use the scope FFT (which handles this internally).

---

## Identification

```
*IDN?  →  Siglent Technologies,SDS824X HD,SDS08A0X803547,3.8.12.1.1.3.6
```
