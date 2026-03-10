# Requirement 5: Phase Response

## Goal

Sweep the FY6800 across frequency and measure the phase delay between the filter input
(C1) and output (C2) using the scope's channel skew measurement. Plot phase vs frequency
and verify it matches the theoretical 2nd-order Butterworth phase response.

---

## Test Setup

| Parameter | Value |
|-----------|-------|
| Input signal | FY6800 CH1, sine wave, 1.0 Vpp, 1.65 V DC offset |
| Sweep range | 50 Hz – 2000 Hz (same points as Bode magnitude sweep) |
| Input channel | Scope C1, AC coupled, 200 mV/div |
| Output channel | Scope C2, AC coupled, 200 mV/div |

Both channels fixed at 200 mV/div — no rescaling during sweep.

---

## Measurement Method

```
C1-C2:MEAD? SKEW   →  time delay Δt (seconds)
phase (degrees) = −Δt × f × 360
```

Negative sign because the output lags the input.

---

## Theory

2nd-order Butterworth phase response:

```
φ(f) = −arctan(2·ζ·(f/fc) / (1 − (f/fc)²))
     = −arctan(√2 · (f/500) / (1 − (f/500)²))   degrees
```

Key values:

| Frequency | Phase |
|-----------|-------|
| 100 Hz    | −16°  |
| 500 Hz    | −90°  |
| 1000 Hz   | −144° |

---

## Acceptance Criteria

| Check | Condition |
|-------|-----------|
| Phase at 500 Hz | −90° ± 10° |
| Phase trend | Monotonically decreasing (more negative) with frequency |
