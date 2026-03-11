/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
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

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
/* USER CODE BEGIN PFP */
static void filter_periph_init(void);
static void adc_init(void);
static void dac_init(void);
static void tim6_init(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  /* USER CODE BEGIN 2 */
  filter_periph_init();
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1_BOOST);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV1;
  RCC_OscInitStruct.PLL.PLLN = 21;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOA_CLK_ENABLE();

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/*
 * filter_periph_init — top-level peripheral initialisation for the filter signal path.
 * Called once from main() after SystemClock_Config and MX_GPIO_Init.
 */
static void filter_periph_init(void)
{
	adc_init();
	dac_init();
	tim6_init();
}

/*
 * adc_init — configure ADC1 channel 1 (PA0) for software-triggered single conversion.
 *
 * Clock: synchronous HCLK/4 (42 MHz) via ADC12_COMMON CCR CKMODE=0b11.
 * Resolution: 12-bit.  Sampling time: 6.5 ADC cycles → total conversion 19 cycles = 452 ns.
 * Enable sequence per RM0440 §21.4.6: ADVREGEN → wait 20 µs → ADCAL → ADEN → ADRDY.
 */
static void adc_init(void)
{
	/* Enable ADC12 clock on AHB2 */
	RCC->AHB2ENR |= RCC_AHB2ENR_ADC12EN;

	/* PA0 to analogue mode (MODER bits 1:0 = 0b11) */
	GPIOA->MODER |= (3U << (0 * 2));

	/* ADC12 common clock: synchronous HCLK/4 (CKMODE = 0b11) */
	ADC12_COMMON->CCR = (3U << ADC_CCR_CKMODE_Pos);

	/* Exit deep power-down, enable voltage regulator */
	ADC1->CR &= ~ADC_CR_DEEPPWD;
	ADC1->CR |= ADC_CR_ADVREGEN;

	/* Wait ≥20 µs for regulator start-up (1 ms via HAL tick) */
	HAL_Delay(1);

	/* Calibrate (single-ended: ADCALDIF = 0) */
	ADC1->CR |= ADC_CR_ADCAL;
	while (ADC1->CR & ADC_CR_ADCAL)
	{
	}

	/* Enable ADC */
	ADC1->CR |= ADC_CR_ADEN;
	while (!(ADC1->ISR & ADC_ISR_ADRDY))
	{
	}

	/* Configure: 12-bit, software trigger, single conversion */
	ADC1->CFGR = 0;	/* CONT=0, EXTEN=00, RES=00 (12-bit) */

	/* Sequence: 1 conversion, channel 1 (PA0 = IN1) */
	ADC1->SQR1 = (1U << ADC_SQR1_SQ1_Pos);

	/* Sampling time for channel 1: 6.5 ADC cycles (SMP1 = 0b001) */
	ADC1->SMPR1 = (1U << ADC_SMPR1_SMP1_Pos);
}

/*
 * dac_init — configure DAC1 channel 1 (PA4) in software-trigger mode.
 *
 * DAC1 is on AHB2.  Output is written directly to DHR12R1 by the ISR.
 * PA4 MODER set to analogue to connect pin to DAC output buffer.
 */
static void dac_init(void)
{
	/* Enable DAC1 clock on AHB2 */
	RCC->AHB2ENR |= RCC_AHB2ENR_DAC1EN;

	/* PA4 to analogue mode (MODER bits 9:8 = 0b11) */
	GPIOA->MODER |= (3U << (4 * 2));

	/* Enable DAC1 channel 1 (no hardware trigger, output buffer enabled) */
	DAC1->CR = DAC_CR_EN1;
}

/*
 * tim6_init — configure TIM6 to fire an update interrupt at exactly 8 kHz.
 *
 * f = PCLK1 / ((PSC+1) * (ARR+1)) = 168 000 000 / (1 * 21 000) = 8 000 Hz.
 * IRQ is shared with DAC underrun; handler name: TIM6_DAC_IRQHandler.
 */
static void tim6_init(void)
{
	/* Enable TIM6 clock on APB1 */
	RCC->APB1ENR1 |= RCC_APB1ENR1_TIM6EN;

	/* PSC=0, ARR=20999 → 168 MHz / 21000 = 8000 Hz */
	TIM6->PSC = 0;
	TIM6->ARR = 20999;

	/* Generate an update event to load PSC and ARR into shadow registers */
	TIM6->EGR = TIM_EGR_UG;

	/* Clear the update flag set by the UG event above */
	TIM6->SR = 0;

	/* Enable update interrupt */
	TIM6->DIER = TIM_DIER_UIE;

	/* Enable TIM6_DAC IRQ in NVIC at default priority */
	NVIC_EnableIRQ(TIM6_DAC_IRQn);

	/* Start counter */
	TIM6->CR1 = TIM_CR1_CEN;
}

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
