# Demo Project Briefing

## Background

This document briefs a new Claude Code session on a planned demo project. The developer
has been using Claude Code Terminal at home for the HAX7456 hobby project (STM32G431KBT6
PAL OSD chip replacement) and was impressed enough to volunteer a presentation at their
workplace, comparing Claude Code against GitHub Copilot (the company's current AI tool).

The goal is to demonstrate capabilities that go beyond what colleagues have seen AI do —
specifically: requirements-driven development, GitHub workflow automation, bare-metal
embedded coding, and automated hardware verification using a real oscilloscope.

---

## The Demo Project

**A real-time digital filter on an STM32G431KB6 with automated Bode plot verification.**

The STM32 implements a **no-library IIR filter** (derived and coded from scratch by Claude
together with the developer). The FY6800 signal generator sweeps sine waves into the
STM32 ADC; the filtered result appears on the DAC output. Claude commands the sweep,
reads the scope at each frequency step, computes the gain, and plots the Bode plot
automatically — proving the filter meets its requirements without anyone touching anything.

A UART command interface allows the cutoff frequency and filter type to be changed live,
with the Bode plot regenerating to show the new response.

### Why this beats the original signal generator idea
The FY6800 signal generator is now available under programmatic control (see FY6800.md).
This enables a **closed-loop automated test bench**:
- FY6800 → STM32 ADC input (stimulus)
- STM32 DAC output → scope (response)
- Python script controls both instruments and plots the result

This is far more impressive than the STM32 generating signals itself — it demonstrates
real DSP, real filter theory, real automated measurement, and real engineering proof.

### Why this impresses the audience
- Requirements are immediately understandable: "pass frequencies below 1kHz, reject above"
- Claude derives the filter coefficients from scratch (no CMSIS-DSP, no library)
- The Bode plot appears automatically, with the -3dB point marked and verified
- Change the cutoff via UART → Bode plot updates → proves it moved
- Non-technical people grasp "low frequencies pass, high frequencies don't" instantly
- Technical people are impressed that Claude derived and implemented fixed-point IIR in C

### Peripheral assignments (chosen by Claude, agreed before implementation)
| Peripheral | Pin | Function |
|-----------|-----|---------|
| ADC1 CH1 | PA0 | Filter input (from FY6800 CH1 via potential divider if needed) |
| DAC1 CH1 | PA4 | Filter output (to scope CH2) |
| TIM6 | — | ADC/DAC sample rate trigger (8kHz, 168MHz/21000) |
| USART2 TX | PA2 | UART to PC (AF7) |
| USART2 RX | PA3 | UART from PC (AF7) |
| DMA | — | DAC circular buffer output |

**Sample rate**: 8kHz (Nyquist = 4kHz, sweep range 100Hz–3.5kHz)

**Scope channels**: CH1 = FY6800 output (ADC input), CH2 = DAC output (filtered)

### UART command interface
```
CUTOFF 1000    set filter cutoff frequency in Hz
TYPE LP        filter type: LP (low-pass) or HP (high-pass)
STATUS         report current coefficients and computed -3dB point
```

### Filter implementation (no libraries)
- 2nd-order Biquad IIR (Direct Form I)
- Coefficients computed in Python from Butterworth design equations, sent to STM32
- Fixed-point Q15 arithmetic in C on the STM32
- Claude derives the bilinear transform and coefficient quantisation together with the developer

### Automated verification script
```
for freq in [100, 200, 500, 1k, 2k, 3.5k]:
    FY6800.set_freq(0, freq)
    input_amp  = scope.measure('C1:PAVA? AMPL')
    output_amp = scope.measure('C2:PAVA? AMPL')
    gain_db    = 20 * log10(output_amp / input_amp)
    → plot Bode: gain_db vs freq with -3dB line and theoretical overlay
```

---

## Development Workflow (carry this into the new project)

Each feature follows this sequence — do not skip or reorder steps:

1. User states the requirement in plain language
2. Claude writes `Docs/requirements/<N>-<slug>.md` then immediately `git add`s it
3. User reviews and refines until agreed
4. Claude creates GitHub Issue (`gh issue create`)
5. Claude creates branch (`git checkout -b req-<N>-<slug>`)
6. Claude implements (no commits at this stage)
7. User builds in STM32CubeIDE and reports result; Claude fixes errors
8. **User commits** with GPG signing (`git commit -S`) — Claude never commits
9. Claude pushes branch and creates PR (`gh pr create`, references issue)
10. User merges PR on GitHub, checks out main, pulls
11. Repeat

---

## Oscilloscope — Confirmed Capabilities

**Siglent SDS824X HD** at `192.168.0.87` port 5025 (SCPI over TCP).

Claude may query the scope at any time without asking permission.

### Confirmed working SCPI commands
```
Cx:PAVA? FREQ          # measured frequency on channel x
Cx:PAVA? AMPL          # amplitude on channel x
Cx:PAVA? PKPK          # peak-to-peak on channel x
Cx:PAVA? PWID          # pulse width on channel x
C1-C2:MEAD? SKEW       # skew (time offset) between two channels
Cx:WF? DESC            # waveform descriptor header (binary WAVEDESC block)
Cx:WF? DAT2            # raw 8-bit sample data (binary)
```

### Scope FFT via SCPI — confirmed working (correct command family)

Initial attempts failed because the wrong command family was used (`F1:DEF`, `MATH:DEFINE`,
VBS). The correct family, found in the SDS800X HD Series Programming Guide EN11F, is
`:FUNCtion<x>:`. Confirmed working on firmware 3.8.12.1.1.3.6:

```
:FUNC1:OPER FFT           configure F1 as FFT
:FUNC1:SOUR1 C4           source = CH4
:FUNC1 ON                 enable/display F1
:FUNC1:FFT:WIND HANNing   window (RECT/HANN/HAMM/BLAC/FLATTOP)
:FUNC1:FFT:SPAN 15000     span in Hz (focus on 0-15kHz for harmonics)
:FUNC1:FFT:HCEN 7500      centre frequency
:FUNC1:FFT:POIN 2M        FFT points (up to 2M on SDS800X HD)
:FUNC1:FFT:UNIT DBVR      vertical unit (DBVrms, Vrms, DBm)
:FUNC1:FFT:SEAR PEAK      enable peak search
:FUNC1:FFT:SEAR:THR -80   peak search threshold (dBVrms)
:FUNC1:FFT:SEAR:RES?      → "Peaks,1,<freq_Hz>,<amp_dBVrms>;2,..."
:FUNC1 OFF                disable F1 when done
```

**Important:** SCPI set commands return no response — do not wait for a reply or the
socket will timeout. Only query commands (`?`) return data.

**WAV:SOUR F1 / WAV:DATA? — NOT working:** Raw FFT bin data download via the WAVeform
interface times out. THD is computed from peak search results instead.

**THD/SINAD/SFDR PAVA parameters — not available** on this scope/firmware.

#### THD from peak search (fast, no sample download needed)
```python
peaks = parse(":FUNC1:FFT:SEAR:RES?")    # freq + dBVrms per peak
fund  = highest amplitude peak
harmonics = peaks matching fund*h ± 5%   for h in 2..10
THD = sqrt(sum(10^(Hn_dBVrms/10))) / 10^(H1/10) * 100  [%]
```

### FFT and THD — done manually in NumPy (confirmed working)
`Cx:WF? DAT2` transfers all 2.5M raw 8-bit samples at 500 MSa/s. Python post-processes:
- Parse `WAVEDESC` binary header for voltage scaling (v_min/v_max at offsets 184/192,
  horiz_interval at offset 176, num_points at offset 116)
- Convert int8 samples to voltage, remove DC offset
- `np.fft.rfft()` with Hanning window on full sample set (freq resolution = 200 Hz at 500MSa/s/2.5M)
- Find fundamental bin by peak search in ±200Hz around target frequency
- Read harmonics H2–H10 at exact multiples of fundamental bin index
- THD = √(ΣHn²) / H1 × 100%
- Plot: time domain (N cycles) + FFT spectrum with harmonic markers

**Demonstrated result:** function generator 1kHz sine, 0.894V p-p →
THD = 0.323% (-49.8 dBc). Plot generated as PNG. Total time ~3 seconds.

**Note on ADC resolution:** with a small signal the scope uses only ~30 of 256 ADC counts.
Adjust V/div so the signal fills the screen to maximise effective bits and lower the THD
noise floor.

### Python stack — confirmed present in WSL2
- Python 3.12.3
- NumPy 1.26.4
- Matplotlib 3.6.3

Capabilities confirmed: frequency sweep → scope readback → error/THD computation →
tolerance plot → harmonic spectrum, all automated from a single Python script.

---

## Hardware Setup

- **MCU**: STM32G431KB6 (LQFP32, Cortex-M4, same family as HAX7456 project)
- **IDE**: STM32CubeIDE 1.18.x (builds done here — do not attempt command-line builds)
- **Compiler**: arm-none-eabi-gcc, GNU Tools for STM32 14.3.rel1
- **UART**: USB-Serial cable on PA2 (TX) / PA3 (RX) — USART2, both directions needed
- **Signal input**: PA0 (ADC1 CH1) — from FY6800 CH1 output
- **Signal output**: PA4 (DAC1 CH1) — to scope CH2
- **Scope CH1**: FY6800 CH1 output (ADC input signal, reference)
- **Scope CH2**: STM32 PA4 DAC output (filtered signal)
- **Signal generator**: Feeltech FY6800 on /dev/ttyUSB0 (see FY6800.md for setup)

---

## Coding Style (carry from HAX7456)

- Bare-metal register writes only — no HAL peripheral APIs
- Tabs, not spaces
- Always `{}` on all control flow bodies, body always on its own line:
  ```c
  if (foo) {
      bar();
  }
  ```
- ISR code inside `/* USER CODE BEGIN/END */` blocks (CubeMX survival)
- Keep ISR code lean; defer work where possible

---

## What to Do First in the New Session

1. Confirm the GitHub repo URL and working directory
2. Read SDS824X.md and FY6800.md to load instrument knowledge
3. Confirm serial port for UART commands to STM32 (separate from FY6800 on /dev/ttyUSB0)
4. Confirm FY6800 is attached via usbipd-win (`usbipd attach --wsl --busid 7-2`)
5. Begin requirement 1: clock configuration and peripheral initialisation
