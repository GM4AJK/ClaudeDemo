# Requirement 6: Combined Bode Plot (Magnitude + Phase)

## Goal

Produce a standard two-panel Bode plot for the IIR filter: magnitude (dB) on the top panel
and phase (degrees) on the bottom, both versus frequency on a log scale. A single frequency
sweep collects both measurements simultaneously at each point.

---

## Test Setup

| Parameter | Value |
|-----------|-------|
| Input signal | FY6800 CH1, sine wave, 1.0 Vpp, 1.65 V DC offset |
| Sweep range | 100 Hz – 800 Hz (20 log-spaced points) |
| Input channel | Scope C1, AC coupled, 200 mV/div |
| Output channel | Scope C2, AC coupled, 200 mV/div |

Both channels fixed at 200 mV/div throughout — no rescaling.

Lower bound 100 Hz: below this AC coupling is not settled and the SKEW measurement
returns a spurious -122 µs artefact.

Upper bound 800 Hz: above this the total phase delay (filter + ~170 µs system delay)
exceeds half the signal period and the scope SKEW measurement wraps.

---

## Measurements

At each frequency the script collects (N_AVG = 5 readings, averaged):

| Measurement | SCPI query | Derived quantity |
|-------------|-----------|-----------------|
| Input amplitude | `C1:PAVA? PKPK` | V_in |
| Output amplitude | `C2:PAVA? PKPK` | V_out |
| Channel skew | `C1-C2:MEAD? SKEW` | Δt (s) |

```
gain  (dB)  = 20 · log10(V_out / V_in)
phase (°)   = −Δt × f × 360
```

---

## System Delay Correction

A constant delay of approximately 170 µs (ADC sample period ~125 µs + RC reconstruction
filter group delay ~47 µs) adds a linear phase offset to every measurement. The script
estimates this from all data points using a median fit and subtracts it before plotting
and before the pass/fail checks.

---

## Theory

2nd-order Butterworth, fc = 500 Hz:

**Magnitude:**
```
|H(f)| = 1 / sqrt(1 + (f/500)^4)     →  gain (dB) = −10·log10(1 + (f/500)^4)
```

**Phase:**
```
φ(f) = −arctan(√2·(f/500) / (1 − (f/500)²))   degrees
```

Key values:

| Frequency | Gain   | Phase  |
|-----------|--------|--------|
| 100 Hz    | −0.0 dB | −16°  |
| 500 Hz    | −3.0 dB | −90°  |
| 800 Hz    | −16 dB  | −124° |

---

## Acceptance Criteria

| Check | Condition |
|-------|-----------|
| Gain at 500 Hz | −3 dB ± 1.5 dB (i.e. −1.5 to −4.5 dB) |
| Gain at 100 Hz | ≥ −1 dB (flat passband) |
| Corrected phase at 500 Hz | −90° ± 10° |
| Phase trend | Monotonically decreasing (more negative) with frequency |
