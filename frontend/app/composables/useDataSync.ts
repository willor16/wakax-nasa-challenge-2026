// Shared change stamps, one per kind of crew data. Every saved entry (and every change
// announced on the live stream) moves the matching stamps forward, and each screen that
// shows that kind of data reloads at once instead of waiting for its next timed refresh.

export const SYNC_DOMAINS = ['vitals', 'vision', 'sleep', 'psych', 'auscultation', 'alerts', 'streaks'] as const
export type SyncDomain = typeof SYNC_DOMAINS[number]
export type SyncStamps = Record<SyncDomain, number>

const ROUTES: [RegExp, SyncDomain[]][] = [
  [/^\/measurements\b/, ['vitals', 'vision', 'alerts', 'streaks']],
  [/^\/psych\//, ['psych', 'sleep', 'alerts', 'streaks']],
  [/^\/sleep\b/, ['sleep', 'alerts', 'streaks']],
  [/^\/vision\b/, ['vision', 'alerts']],
  [/^\/auscultation\//, ['auscultation', 'alerts']],
  [/^\/(alerts|diagnosis)\//, ['alerts']],
  [/^\/comms\//, ['alerts']],
  [/^\/crew\b/, ['vitals', 'streaks']],
]

/** Which kinds of data a successful change on this server path can affect. */
export function domainsForPath(path: string): SyncDomain[] {
  const clean = path.split('?')[0] ?? ''
  for (const [pattern, domains] of ROUTES) {
    if (pattern.test(clean)) return domains
  }
  return []
}

/** Keeps only names that are real domains (the live stream is outside data). */
export function knownDomains(names: unknown): SyncDomain[] {
  if (!Array.isArray(names)) return []
  return names.filter((name): name is SyncDomain => (SYNC_DOMAINS as readonly string[]).includes(name))
}

export function useDataSync() {
  const stamps = useState<SyncStamps>('data-sync', () =>
    Object.fromEntries(SYNC_DOMAINS.map(domain => [domain, 0])) as SyncStamps)

  function bump(...domains: SyncDomain[]) {
    if (domains.length === 0) return
    const next = { ...stamps.value }
    for (const domain of new Set(domains)) next[domain] += 1
    stamps.value = next
  }

  /** A single number that changes whenever any of these domains changes. */
  function signature(domains: readonly SyncDomain[]) {
    return computed(() => domains.map(domain => stamps.value[domain]).join('.'))
  }

  return { stamps, bump, signature }
}
