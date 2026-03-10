# Requirement 3: THD Measurement

## Goal

Using the SDS824X scope FFT, measure the Total Harmonic Distortion of the IIR filter
output and confirm it is below 1%.

---

## Test Setup

| Parameter | Value |
|-----------|-------|
| Input signal | FY6800 CH1, 200 Hz sine, 1.0 Vpp, 1.65 V DC offset |
| Input channel | Scope C1, AC coupled, 200 mV/div |
| Output channel | Scope C2, AC coupled, 200 mV/div |
| Timebase | 5 ms/div (shows ~1 cycle of 200 Hz) |

---

## Scope FFT Configuration

FFT computed on C2 via FUNC1 and left visible on screen after the test.

| Parameter | Value |
|-----------|-------|
| Source | C2 |
| Window | FlatTop (best amplitude accuracy for THD) |
| Span | 4000 Hz |
| Centre | 2000 Hz |
| Coverage | 0–4000 Hz — captures harmonics 2nd–10th of 200 Hz |

---

## THD Calculation

The script uses the scope FFT peak search to locate the fundamental (200 Hz) and
harmonics 2nd–10th (400, 600, …, 2000 Hz), then computes:

```
THD = sqrt(V2² + V3² + … + V10²) / V1 × 100%
```

where Vn is the RMS voltage of the nth harmonic, derived from the dBVrms peak values
returned by the scope.

---

## Acceptance Criteria

**PASS: THD < 1%**

---

## Notes

- The FY6800 THD has been verified to be below the measurement floor and can be ignored.
- C1 remains on screen throughout so the audience can see the clean input sine alongside
  the output FFT.
- The FUNC1 FFT display is left active after the test completes.
