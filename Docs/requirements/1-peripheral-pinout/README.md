# Req 1: Peripheral Pinout

## Goal

Select and configure the analogue input, analogue output, and sample-rate timer on the
STM32G431KBT6, and verify that the signal path passes a 100 Hz sine through the MCU
with unity gain (pass-through — no filtering yet).

---

## Peripheral Choices and Justification

### ADC — PA0 / ADC1 Channel 1

**Pin**: PA0 (LQFP32 pin 5)
**Peripheral**: ADC1, input channel IN1

PA0 is a dedicated analogue I/O pin on the STM32G431KBT6 LQFP32 package. ADC1 is one
of two 12-bit successive-approximation ADCs on the device. ADC1 and ADC2 share the
AHB2 bus and a common clock/calibration register block (ADC12_COMMON). Channel 1
(IN1) maps directly to PA0 with no GPIO alternate-function configuration required —
setting PA0's MODER bits to Analogue (0b11) disconnects the digital path and connects
the pin to the ADC analogue input.

Clock source: synchronous HCLK/4 mode (CKMODE = 0b11 in ADC12_CCR). At 168 MHz system
clock this gives an ADC clock of 42 MHz. With 6.5-cycle sampling time and 12.5-cycle
conversion the total conversion time is 19 ADC cycles = 452 ns, well within the 125 µs
sample period.

### DAC — PA4 / DAC1 Channel 1

**Pin**: PA4 (LQFP32 pin 9)
**Peripheral**: DAC1, channel 1

PA4 is the dedicated analogue output pin for DAC1 channel 1 on the STM32G431KBT6.
DAC1 is a 12-bit buffered voltage-output DAC on the AHB2 bus. Setting PA4's MODER bits
to Analogue (0b11) connects the pin to the DAC output buffer. The DAC is enabled in
software-trigger mode; the ISR writes the 12-bit output value directly to DHR12R1.

#### RC Reconstruction Filter (hardware build step — required before testing)

The DAC produces a staircase waveform at 8 kHz (zero-order hold). An RC filter is
required between PA4 and the oscilloscope to smooth the steps.

**► Action:** Fit a 4.7 kΩ resistor in series with PA4, and a 10 nF capacitor from
the resistor's far end to GND. Connect the oscilloscope CH2 probe tip to the far side
of the resistor (after the capacitor junction).

Corner frequency: fc = 1 / (2π × 4700 × 10×10⁻⁹) ≈ **3.4 kHz**

This attenuates the 8 kHz sampling image by ~7.4 dB and passes 100 Hz essentially
unattenuated (< 0.1 dB loss). For the IIR filter requirement (Req 2) the cut-off
frequency of the digital filter will be set well below 3.4 kHz so the reconstruction
filter does not distort in-band measurements.

### Timer — TIM6 at 8 kHz

**Peripheral**: TIM6 (basic timer, APB1 bus)

TIM6 is chosen because it is a dedicated basic timer with no capture/compare channels
to configure. Its sole purpose is to generate a periodic update event which triggers
the ISR. The update interrupt fires when the counter overflows from ARR back to 0.

#### Register calculation

System clock: 168 MHz
Target sample rate: 8 000 Hz
Period: 168 000 000 / 8 000 = **21 000 timer ticks**

With PSC = 0 (prescaler divide-by-1) and ARR = 20 999:

```
f_TIM6 = f_CK / ((PSC + 1) × (ARR + 1))
       = 168 000 000 / (1 × 21 000)
       = 8 000 Hz  ✓
```

Reference: RM0440 §32.3.4–32.3.5 — the counter reloads to 0 after reaching ARR,
generating an update event every (PSC+1)×(ARR+1) clock cycles.

**IRQ note**: TIM6's interrupt is shared with the DAC underrun interrupt. The handler
must be named `TIM6_DAC_IRQHandler`.

---

## Signal Path

```
FY6800 CH1 ──► PA0 (ADC1 IN1) ──► TIM6 ISR ──► PA4 (DAC1 CH1) ──► 4k7/10nF ──► scope CH2
```

At this stage the ISR performs a direct pass-through: read ADC DR → write to DAC
DHR12R1. No filtering is applied.

---

## Test Setup

- FY6800 CH1: 100 Hz sine, 1.0 Vpp, 1.65 V DC offset
- Scope C1: FY6800 CH1 output (AC coupled, 200 mV/div, probe ×10)
- Scope C2: DAC output after RC filter (AC coupled, 200 mV/div, probe ×10)

The DC offset centres the ADC input in mid-scale (VDDA/2 ≈ 1.65 V) to use the full
12-bit dynamic range without clipping. AC coupling on the scope removes the DC offset
for display.

---

## Acceptance Criteria

**Pass**: 0.80 ≤ V_out_pkpk / V_in_pkpk ≤ 1.20

The 100 Hz test frequency is far below both the 3.4 kHz RC filter corner and the
4 kHz Nyquist limit, so the gain should be very close to unity. The ±20% window
accommodates probe calibration tolerances and scope measurement quantisation.

---

## Hardware Prerequisites

Before running the test script:

1. VDDA (LQFP32 pin 15) connected to 3.3 V
2. VSSA (LQFP32 pin 14) connected to GND
3. RC reconstruction filter fitted on PA4 (4.7 kΩ + 10 nF as above)
4. FY6800 CH1 connected to PA0 via a 100 Ω series resistor (protects MCU pin)
5. Scope C1 probe on FY6800 output; scope C2 probe on RC filter output
6. Scope probe grounds connected to system GND
