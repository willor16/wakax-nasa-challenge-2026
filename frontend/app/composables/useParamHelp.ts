// Plain-language help for every parameter on screen, loaded once from the onboard server.
export interface ParamHelp {
  key: string
  label_en: string
  unit: string
  summary_en: string
  interpretation_en: string
  operational_impact_en: string
  nominal_min: number | null
  nominal_max: number | null
}

export function useParamHelp() {
  const entries = useState<Record<string, ParamHelp>>('param-help', () => ({}))
  const loading = useState<Promise<void> | null>('param-help-loading', () => null)
  const { api } = useApi()

  function load(): Promise<void> {
    if (Object.keys(entries.value).length) return Promise.resolve()
    loading.value ??= api<ParamHelp[]>('/metrics/help')
      .then((items) => {
        entries.value = Object.fromEntries(items.map(item => [item.key, item]))
      })
      .catch(() => {
        // Help text is optional; the button retries the next time it opens.
        loading.value = null
      })
    return loading.value
  }

  return { entries, load }
}
