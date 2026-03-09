# Requirement 1: Peripheral Pinout

## Goal

Select GPIO pins and peripherals on the STM32G431KBT6 (LQFP32) for:
- Analogue signal input — from the FY6800 signal generator
- Analogue signal output — to the SDS824X oscilloscope
- A hardware timer to drive a fixed sample rate

---

## Selected Peripherals and Pins

| Function       | Peripheral | GPIO | LQFP32 Pin |
|----------------|-----------|------|------------|
| ADC input      | ADC1 IN1  | PA0  | 5          |
| DAC output     | DAC1 OUT1 | PA4  | 9          |
| Sample trigger | TIM6      | —    | —          |

---

## Justification

### ADC input — PA0 / ADC1 IN1

PA0 is a true analogue pin on the STM32G431KBT6: it has no internal digital pull-up or
pull-down and connects directly to ADC1 channel 1. Using a dedicated ADC channel avoids
any need for external signal conditioning beyond a simple resistive divider (if required
to map the signal generator's output into the 0–3.3 V ADC range). ADC1 on the G4 family
supports 12-bit resolution at up to 4 Msps — far more than the 8 kHz sample rate needed
here, leaving ample margin.

### DAC output — PA4 / DAC1 OUT1

PA4 is the sole dedicated output pin for DAC1 channel 1 on this package. It produces a
true analogue voltage directly from the 12-bit DAC, requiring no PWM low-pass filter.
The output impedance is low enough to drive the 1 MΩ scope input without significant
attenuation.

### Sample-rate timer — TIM6

TIM6 is a basic 16-bit upcounter with no GPIO requirement. It generates a periodic
update interrupt (or trigger) that drives the ADC→filter→DAC pipeline at a fixed rate.
Using a dedicated timer (rather than SysTick or a general-purpose timer) keeps the
sample interrupt isolated from any future PWM or capture-compare use. At the system
clock of 168 MHz (HSI 16 MHz → PLL ×21 → /2 → 84 MHz APB1 × 2 = 168 MHz timer clock):

```
PSC = 0,  ARR = 20999
f_sample = 168,000,000 / (1 × 21,000) = 8,000 Hz exactly
```

8 kHz gives a Nyquist frequency of 4 kHz, which is well above the intended low-pass
cut-off and comfortably within the range the FY6800 and scope can measure.

---

## Supply Pin Prerequisites

Before testing, verify:
- **VDDA** (pin 15) connected to 3.3 V — analogue supply for ADC and DAC
- **VSSA** (pin 14) connected to GND — analogue ground for ADC and DAC

Without these connections the ADC and DAC will not function regardless of firmware.

---

## Acceptance Criteria

A pass-through test (IIR coefficients = all-pass) shall be verified by `test_passthrough.py`:
- FY6800 outputs a 100 Hz sine, 1.0 Vpp, 1.65 V DC offset on CH1
- Scope measures Vpeak-peak on CH1 (input) and CH2 (DAC output)
- Pass condition: `0.8 ≤ V_out / V_in ≤ 1.2`
