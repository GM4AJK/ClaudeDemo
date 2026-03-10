# Requirement 4: Step Response

## Goal

Apply a square wave input and verify the filter's time-domain step response matches
the expected 2nd-order Butterworth characteristic: ~4.3% overshoot and clean settling.

---

## Test Setup

| Parameter | Value |
|-----------|-------|
| Input signal | FY6800 CH1, square wave, 50 Hz, 1.0 Vpp, 1.65 V DC offset |
| Input channel | Scope C1, AC coupled, 200 mV/div |
| Output channel | Scope C2, AC coupled, 200 mV/div |
| Timebase | 1 ms/div, triggered on C1 rising edge |

A 50 Hz square wave gives a 10 ms half-period — approximately 5× the filter settling
time (~1.8 ms) — so the output is fully settled before the next edge.

---

## Theory

For a 2nd-order Butterworth (ζ = 1/√2 ≈ 0.707):

```
Overshoot = e^(−π·ζ / √(1−ζ²)) × 100%  =  e^(−π) × 100%  ≈  4.3%
```

---

## Measurement Method

With AC coupling the settled output is centred at 0 V. The scope PAVA measurements give:

- `C2:PAVA? AMPL` — settled amplitude (high − low), equivalent to Vpp at steady state
- `C2:PAVA? MAX`  — absolute peak including overshoot

```
overshoot % = (MAX − AMPL/2) / AMPL × 100
```

---

## Acceptance Criteria

| Check | Condition |
|-------|-----------|
| Overshoot | 1 % ≤ overshoot ≤ 8 % |
| DC gain | 0.9 ≤ C2 AMPL / C1 AMPL ≤ 1.1 |
