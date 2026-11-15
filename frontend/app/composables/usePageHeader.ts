// Each screen tells the top bar its title and the status shown in the right-hand pill.

export interface HeaderStatus {
  text: string
  tone: 'ok' | 'critical' | 'neutral'
}

export interface PageHeader {
  title: string
  subtitle?: string
  status?: HeaderStatus | null
}

export function usePageHeader(header?: MaybeRefOrGetter<PageHeader>) {
  const state = useState<PageHeader>('page-header', () => ({ title: '' }))
  if (header !== undefined) {
    watchEffect(() => {
      state.value = toValue(header)
    })
  }
  return state
}
