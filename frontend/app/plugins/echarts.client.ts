import { BarChart, CustomChart, GaugeChart, LineChart } from 'echarts/charts'
import { GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { registerTheme, use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

export default defineNuxtPlugin(() => {
  use([
    CanvasRenderer,
    LineChart,
    BarChart,
    GaugeChart,
    CustomChart,
    GridComponent,
    TooltipComponent,
    MarkLineComponent,
    MarkAreaComponent,
  ])

  registerTheme('spacescan-hud', {
    backgroundColor: 'rgba(4, 30, 46, 0.72)',
    textStyle: {
      fontFamily: "'JetBrains Mono', monospace",
      color: '#FFECD1',
    },
    color: ['#2AEF4B', '#2994A6', '#263BB0', '#D5110B'],
    categoryAxis: {
      axisLine: { lineStyle: { color: '#15616D' } },
      axisLabel: { color: '#C8B69C', fontSize: 10 },
      splitLine: { show: true, lineStyle: { color: 'rgba(38, 59, 176, 0.42)', width: 1 } },
    },
    valueAxis: {
      axisLine: { show: false },
      axisLabel: { color: '#C8B69C', fontSize: 10 },
      splitLine: { show: true, lineStyle: { color: 'rgba(38, 59, 176, 0.42)', width: 1 } },
    },
    tooltip: {
      backgroundColor: '#041E2E',
      borderColor: '#25899B',
      textStyle: { color: '#FFECD1', fontSize: 11 },
    },
  })
})
