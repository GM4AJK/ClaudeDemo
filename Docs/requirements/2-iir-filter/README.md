# Requirement 2: IIR Low-Pass Filter

## Goal

Implement a real-time digital IIR low-pass filter on the STM32G431KBT6 such that the
−3 dB frequency is 500 Hz. Verify the response by sweeping the FY6800 across frequency
and measuring the Bode plot with the SDS824X oscilloscope.

---

## Filter Specification

| Parameter | Value |
|-----------|-------|
| Topology  | 2nd-order Biquad, Direct Form I |
| Response  | Butterworth (maximally flat passband) |
| −3 dB frequency | 500 Hz |
| Sample rate | 8 kHz |
| Arithmetic | Fixed-point Q15 |

---

## Coefficient Derivation (Bilinear Transform)

Pre-warp the analogue cutoff to compensate for bilinear frequency compression:

```
K = tan(π × fc / fs) = tan(π × 500 / 8000) = 0.198912
```

2nd-order Butterworth normalisation factor (Q = 1/√2):

```
norm = 1 + √2·K + K²  =  1 + 0.281304 + 0.039566  =  1.320870
```

Feed-forward coefficients:

```
b0 = b2 = K² / norm  =  0.039566 / 1.320870  =  0.029954
b1       = 2·K² / norm  =  0.059908
```

Feedback coefficients (H(z) = N(z) / (1 + a1·z⁻¹ + a2·z⁻²)):

```
a1 = 2·(K² − 1) / norm  =  −1.920868 / 1.320870  =  −1.45424
a2 = (K² − √2·K + 1) / norm  =  0.758266 / 1.320870  =  0.57404
```

DC gain check: H(1) = (b0+b1+b2) / (1+a1+a2) = (4K²/norm) / (4K²/norm) = 1.000 ✓

---

## Q15 Coefficients

Multiply floating-point values by 2¹⁵ = 32768 and round to nearest integer.
`a1` exceeds ±1 so it cannot fit in a signed 16-bit Q15 word; coefficients are stored
as `int32_t` and the accumulator uses `int64_t`.

| Symbol | Float value | Q15 integer |
|--------|------------|-------------|
| B0 = B2 | 0.029954 |  982 |
| B1      | 0.059908 | 1963 |
| A1      | −1.45424 | −47653 |
| A2      |  0.57404 |  18811 |

---

## Difference Equation (Direct Form I)

```
y[n] = (B0·x[n] + B1·x[n−1] + B2·x[n−2] − A1·y[n−1] − A2·y[n−2]) >> 15
```

Input/output centred on 0 (ADC value − 2048). DAC receives y[n] + 2048.

---

## Expected Frequency Response

| Frequency | Theoretical gain |
|-----------|-----------------|
| 100 Hz    | −0.02 dB |
| 250 Hz    | −0.26 dB |
| 500 Hz    | −3.01 dB |
| 1000 Hz   | −12.3 dB |
| 2000 Hz   | −24.1 dB |

Roll-off: 40 dB/decade (12 dB/octave).

---

## Acceptance Criteria

`test_bode.py` sweeps 50 Hz – 2000 Hz and plots the measured Bode magnitude.

**PASS** conditions:

1. Measured gain at 500 Hz is within −3 dB ± 1 dB (i.e. −2 to −4 dB).
2. Measured gain at 100 Hz is ≥ −1 dB (flat passband).
3. Measured gain at 1000 Hz is ≤ −10 dB (roll-off present).
