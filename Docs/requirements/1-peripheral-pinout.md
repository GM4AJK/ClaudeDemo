# Req 1 — Peripheral & Pinout Selection

## MCU
**STM32G431KBT6** — Cortex-M4F, 32-pin LQFP (KB package), 128 KB Flash, 32 KB RAM.
Clock: HSI 16 MHz → PLL ×21 → /2 = **168 MHz** system clock.

## Selected Peripherals and Pins

| Function | Peripheral | Pin | Justification |
|----------|-----------|-----|---------------|
| Analogue input (from FY6800) | ADC1 CH1 | PA0 | 12-bit SAR ADC; PA0 = ADC1_IN1 on the 32-pin package; no external components required; supports hardware trigger from TIM6 TRGO |
| Analogue output (to scope) | DAC1 CH1 | PA4 | 12-bit buffered DAC; PA4 = DAC1_OUT1; dedicated analogue pin; output buffer drives the scope load directly |
| Sample-rate timer | TIM6 | — | Basic timer; no GPIO needed; generates TRGO on update event to trigger the ADC at a precise, jitter-free rate |
| Debug / programming | SWD | PA13 / PA14 | Default SWD pins; reserved, not reassigned |

## Sample Rate

Target: **8 kHz** (well above audio-band LPF test range, Nyquist = 4 kHz).

TIM6 configuration:
- Input clock: 168 MHz (APB1 timer clock, no prescaler division at bus level)
- PSC = 0 → timer clock = 168 MHz
- ARR = 20999 → period = 21000 ticks
- Update rate = 168,000,000 / 21,000 = **8,000 Hz exactly**

TIM6 TRGO (trigger output) set to "Update event" → triggers ADC1 conversion on each tick.

## Signal Path

```
FY6800 CH1 ──► PA0 (ADC1 CH1) ──► [IIR filter in TIM6 ISR] ──► PA4 (DAC1 CH1) ──► Scope CH2
```

The TIM6 ISR:
1. Reads the ADC result register directly (bare-metal).
2. Runs one biquad IIR iteration.
3. Writes the output to the DAC data register directly (bare-metal).

## Out of Scope

- USART2 — not used; no serial link to the STM32.
- OPAMP — not required; signal levels from FY6800 are within ADC input range (0–3.3 V).
- DMA — not used for this demo; ISR-driven single-sample processing is sufficient at 8 kHz.
