function readCssToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return val || fallback
}

export function buildCrewGaugeOption(score: number) {
  const okColor = readCssToken('--color-status-ok', '#2AEF4B')
  const critColor = readCssToken('--color-status-critical', '#D5110B')
  const navyEdge = readCssToken('--color-navy-edge', '#263BB0')
  const cardColor = readCssToken('--color-surface-card', '#15616D')
  const textColor = readCssToken('--color-text-primary', '#FFECD1')
  const mutedColor = readCssToken('--color-text-muted', '#C8B69C')

  const activeColor = score < 60 ? critColor : score < 80 ? navyEdge : okColor

  return {
    backgroundColor: 'transparent',
    series: [
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        radius: '92%',
        pointer: { show: false },
        progress: {
          show: true,
          overlap: false,
          roundCap: true,
          clip: false,
          itemStyle: { color: activeColor },
        },
        axisLine: {
          lineStyle: {
            width: 12,
            color: [[1, cardColor]],
          },
        },
        splitLine: { show: false },
        axisTick: { show: false },
        axisLabel: { show: false },
        data: [{ value: score, name: 'CREW SCORE' }],
        title: {
          offsetCenter: [0, '32%'],
          fontSize: 10,
          fontWeight: 700,
          color: mutedColor,
          fontFamily: "'Inter', sans-serif",
        },
        detail: {
          valueAnimation: false,
          offsetCenter: [0, '-6%'],
          fontSize: 28,
          fontWeight: 700,
          fontFamily: "'JetBrains Mono', monospace",
          color: textColor,
          formatter: '{value}',
        },
      },
    ],
  }
}
