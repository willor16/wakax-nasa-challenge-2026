import { BarChart, CustomChart, GaugeChart, LineChart } from 'echarts/charts'
import {
  DataZoomInsideComponent,
  DataZoomSliderComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TooltipComponent,
} from 'echarts/components'
import { registerTheme, use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { palette } from '~/utils/charts'

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
    // M4 interactive charts: wheel / pinch zoom, slider, max-min and pinned points, legend.
    DataZoomInsideComponent,
    DataZoomSliderComponent,
    MarkPointComponent,
    LegendComponent,
  ])

  // The holographic theme is built from the palette tokens in tokens.css.
  const c = palette()
  const axis = {
    axisLine: { lineStyle: { color: c.card } },
    axisLabel: { color: c.muted, fontSize: 10 },
    splitLine: { show: true, lineStyle: { color: c.guide, width: 1 } },
  }
  registerTheme('spacescan-hud', {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: '\'JetBrains Mono\', monospace', color: c.text },
    color: [c.ok, c.rem, c.navyEdge, c.crit],
    categoryAxis: axis,
    valueAxis: { ...axis, axisLine: { show: false } },
    timeAxis: axis,
    tooltip: {
      backgroundColor: c.inset,
      borderColor: c.edge,
      textStyle: { color: c.text, fontSize: 11 },
    },
  })
})
