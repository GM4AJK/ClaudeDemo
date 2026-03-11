# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Real-time digital IIR filter demo on STM32G431KB6 with automated Bode plot verification via Python controlling a FY6800 signal generator and SDS824X HD oscilloscope.

- **MCU**: STM32G431KBT6 @ 168 MHz (HSI 16 MHz → PLL ×21 → /2)
- **Sample rate**: 8 kHz (TIM6 trigger)
- **Signal path**: FY6800 CH1 → PA0 ADC1 CH1 → IIR filter → PA4 DAC1 CH1 → scope CH2

## Build

Claude builds and flashes autonomously from WSL2 using `powershell.exe` to invoke the Windows toolchain. Build output: `Debug/ClaudeDemo.elf`.

Note: the toolchain PATH must be set inside the `powershell.exe -Command` call — it is not inherited from WSL2.

### Build
```bash
powershell.exe -Command "
\$env:PATH += ';C:\ST\STM32CubeIDE_1.12.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.14.3.rel1.win32_1.0.100.202602081740\tools\bin;C:\ST\STM32CubeIDE_1.12.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.400.202601091506\tools\bin';
& 'C:\ST\STM32CubeIDE_1.12.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.make.win32_2.2.100.202601091506\tools\bin\make.exe' -C 'C:\Users\kirkh\STM32CubeIDE\workspace_1.18.x\ClaudeDemo\Debug' all 2>&1"
```

### Flash
```bash
powershell.exe -Command "
\$env:PATH += ';C:\ST\STM32CubeIDE_1.12.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.win32_2.2.400.202601091506\tools\bin';
STM32_Programmer_CLI.exe -c port=SWD -w 'C:\Users\kirkh\STM32CubeIDE\workspace_1.18.x\ClaudeDemo\Debug\ClaudeDemo.elf' -rst 2>&1"
```

## Architecture

### Firmware (C)
- **`Core/Src/main.c`**: Entry point. Clock init (168 MHz), peripheral init, infinite loop.
- **`Core/Src/stm32g4xx_it.c`**: ISRs. TIM6 ISR drives ADC sample → IIR filter → DAC output.
- **`Core/Inc/stm32g4xx_hal_conf.h`**: Selects which HAL modules are compiled in.
- **`ClaudeDemo.ioc`**: STM32CubeMX config — do not hand-edit; peripheral config lives here.

The filter is a **2nd-order Biquad IIR (Direct Form I)** implemented in the TIM6 ISR using fixed-point Q15 arithmetic. No DSP libraries. All peripheral setup uses bare-metal register writes inside `USER CODE BEGIN/END` blocks (HAL calls for init scaffolding are acceptable, HAL peripheral APIs are not).

### Python Automation
Verification scripts live **alongside their requirements doc**, not in the repo root:

```
Docs/requirements/
  1-peripheral-pinout/
    README.md              ← requirements doc
    test_passthrough.py    ← verifies the requirement
  2-iir-filter/
    README.md
    test_bode.py
```

Scripts control instruments via serial/SCPI:
- **FY6800**: Serial at 115200 baud on `/dev/ttyUSB0` (busid 7-2, VID 1a86:7523).
- **SDS824X HD**: SCPI over TCP at `192.168.0.87:5025`.

See `FY6800.md` and `SDS824X.md` for protocol details.

## Coding Style

- **Bare-metal register writes only** — no HAL peripheral APIs (e.g., `HAL_ADC_Start`, `HAL_DAC_SetValue`)
- **Tabs**, not spaces
- **Always braces** on all control flow; body on its own line
- ISR code inside `/* USER CODE BEGIN */` / `/* USER CODE END */` blocks
- USART2 is not used — ignore any references to it in old docs

## Development Workflow

Per WORKFLOW.md:
1. Write requirements doc `Docs/requirements/<N>-<slug>/README.md`
2. Commit and push the doc
3. Create GitHub issue referencing the doc
4. Create feature branch
5. Implement firmware; write Python verification script at `Docs/requirements/<N>-<slug>/<script>.py`
6. Build and flash via CLI (see Build section above)
7. Run verification script
8. Commit, push, open PR, merge

## Hardware

| Peripheral | Pin | Role |
|-----------|-----|------|
| ADC1 CH1 | PA0 | Filter input (from FY6800) |
| DAC1 CH1 | PA4 | Filter output (to scope CH2) |
| TIM6 | — | 8 kHz sample trigger (168 MHz / 21000) |
| SWD | PA13/PA14 | Debug |

RAM: 32 KB @ 0x20000000. Flash: 128 KB @ 0x08000000.
