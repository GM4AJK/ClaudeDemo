/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    stm32g4xx_it.c
  * @brief   Interrupt Service Routines.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "stm32g4xx_it.h"
/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN TD */

/* USER CODE END TD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* Biquad IIR coefficients — 2nd-order Butterworth LPF, fc=500 Hz, fs=8 kHz
 * Derived via bilinear transform: K = tan(pi*500/8000) = 0.198912
 * Stored as Q15 integers (value * 2^15); accumulator is int64_t.
 * Sign convention: y[n] = (B0*x[n] + B1*x[n-1] + B2*x[n-2]
 *                        - A1*y[n-1] - A2*y[n-2]) >> 15
 */
#define BQ_B0	  982		/* b0 = b2 =  0.029954 */
#define BQ_B1	 1963		/* b1       =  0.059908 */
#define BQ_B2	  982
#define BQ_A1	(-47653)	/* a1       = -1.45424  */
#define BQ_A2	 18811		/* a2       =  0.57404  */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN PV */

/* Biquad delay-line state (centred values, DC offset removed) */
static int32_t bq_x1 = 0;
static int32_t bq_x2 = 0;
static int32_t bq_y1 = 0;
static int32_t bq_y2 = 0;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/* External variables --------------------------------------------------------*/

/* USER CODE BEGIN EV */

/* USER CODE END EV */

/******************************************************************************/
/*           Cortex-M4 Processor Interruption and Exception Handlers          */
/******************************************************************************/
/**
  * @brief This function handles Non maskable interrupt.
  */
void NMI_Handler(void)
{
  /* USER CODE BEGIN NonMaskableInt_IRQn 0 */

  /* USER CODE END NonMaskableInt_IRQn 0 */
  /* USER CODE BEGIN NonMaskableInt_IRQn 1 */
   while (1)
  {
  }
  /* USER CODE END NonMaskableInt_IRQn 1 */
}

/**
  * @brief This function handles Hard fault interrupt.
  */
void HardFault_Handler(void)
{
  /* USER CODE BEGIN HardFault_IRQn 0 */

  /* USER CODE END HardFault_IRQn 0 */
  while (1)
  {
    /* USER CODE BEGIN W1_HardFault_IRQn 0 */
    /* USER CODE END W1_HardFault_IRQn 0 */
  }
}

/**
  * @brief This function handles Memory management fault.
  */
void MemManage_Handler(void)
{
  /* USER CODE BEGIN MemoryManagement_IRQn 0 */

  /* USER CODE END MemoryManagement_IRQn 0 */
  while (1)
  {
    /* USER CODE BEGIN W1_MemoryManagement_IRQn 0 */
    /* USER CODE END W1_MemoryManagement_IRQn 0 */
  }
}

/**
  * @brief This function handles Prefetch fault, memory access fault.
  */
void BusFault_Handler(void)
{
  /* USER CODE BEGIN BusFault_IRQn 0 */

  /* USER CODE END BusFault_IRQn 0 */
  while (1)
  {
    /* USER CODE BEGIN W1_BusFault_IRQn 0 */
    /* USER CODE END W1_BusFault_IRQn 0 */
  }
}

/**
  * @brief This function handles Undefined instruction or illegal state.
  */
void UsageFault_Handler(void)
{
  /* USER CODE BEGIN UsageFault_IRQn 0 */

  /* USER CODE END UsageFault_IRQn 0 */
  while (1)
  {
    /* USER CODE BEGIN W1_UsageFault_IRQn 0 */
    /* USER CODE END W1_UsageFault_IRQn 0 */
  }
}

/**
  * @brief This function handles System service call via SWI instruction.
  */
void SVC_Handler(void)
{
  /* USER CODE BEGIN SVCall_IRQn 0 */

  /* USER CODE END SVCall_IRQn 0 */
  /* USER CODE BEGIN SVCall_IRQn 1 */

  /* USER CODE END SVCall_IRQn 1 */
}

/**
  * @brief This function handles Debug monitor.
  */
void DebugMon_Handler(void)
{
  /* USER CODE BEGIN DebugMonitor_IRQn 0 */

  /* USER CODE END DebugMonitor_IRQn 0 */
  /* USER CODE BEGIN DebugMonitor_IRQn 1 */

  /* USER CODE END DebugMonitor_IRQn 1 */
}

/**
  * @brief This function handles Pendable request for system service.
  */
void PendSV_Handler(void)
{
  /* USER CODE BEGIN PendSV_IRQn 0 */

  /* USER CODE END PendSV_IRQn 0 */
  /* USER CODE BEGIN PendSV_IRQn 1 */

  /* USER CODE END PendSV_IRQn 1 */
}

/**
  * @brief This function handles System tick timer.
  */
void SysTick_Handler(void)
{
  /* USER CODE BEGIN SysTick_IRQn 0 */

  /* USER CODE END SysTick_IRQn 0 */
  HAL_IncTick();
  /* USER CODE BEGIN SysTick_IRQn 1 */

  /* USER CODE END SysTick_IRQn 1 */
}

/******************************************************************************/
/* STM32G4xx Peripheral Interrupt Handlers                                    */
/* Add here the Interrupt Handlers for the used peripherals.                  */
/* For the available peripheral interrupt handler names,                      */
/* please refer to the startup file (startup_stm32g4xx.s).                    */
/******************************************************************************/

/* USER CODE BEGIN 1 */

/**
 * @brief  TIM6 update interrupt — 8 kHz sample tick.
 *         ADC1 CH1 (PA0) → 2nd-order Butterworth IIR LPF (fc=500 Hz) → DAC1 CH1 (PA4).
 */
void TIM6_DAC_IRQHandler(void)
{
	if (TIM6->SR & TIM_SR_UIF)
	{
		TIM6->SR = ~TIM_SR_UIF;  /* clear update interrupt flag */

		/* Trigger a single ADC conversion and wait for result */
		ADC1->CR |= ADC_CR_ADSTART;
		while (!(ADC1->ISR & ADC_ISR_EOC))
		{
		}

		/* Centre input: remove 12-bit mid-scale DC offset */
		int32_t x0 = (int32_t)(uint16_t)ADC1->DR - 2048;

		/* Direct Form I biquad — Q15 coefficients, int64 accumulator */
		int64_t acc = (int64_t)BQ_B0 * x0
		            + (int64_t)BQ_B1 * bq_x1
		            + (int64_t)BQ_B2 * bq_x2
		            - (int64_t)BQ_A1 * bq_y1
		            - (int64_t)BQ_A2 * bq_y2;

		int32_t y0 = (int32_t)(acc >> 15);

		/* Saturate to ±2048 to guard against transient overflow */
		if (y0 >  2047) { y0 =  2047; }
		if (y0 < -2048) { y0 = -2048; }

		/* Advance delay lines */
		bq_x2 = bq_x1;  bq_x1 = x0;
		bq_y2 = bq_y1;  bq_y1 = y0;

		/* Restore DC offset and write to DAC */
		DAC1->DHR12R1 = (uint32_t)(y0 + 2048);
	}
}

/* USER CODE END 1 */
