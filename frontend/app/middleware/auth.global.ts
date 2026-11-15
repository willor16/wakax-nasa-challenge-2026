// Access levels in the cabin: three public screens, everything else behind the crew PIN.
const PUBLIC_PATHS = new Set(['/', '/login', '/crew-overview', '/crew-streaks'])

export default defineNuxtRouteMiddleware((to) => {
  const path = to.path.length > 1 ? to.path.replace(/\/+$/, '') : to.path
  if (path !== to.path) return navigateTo({ path, query: to.query, hash: to.hash }, { replace: true })
  const { isAuthenticated, isOperator } = useSession()
  if (PUBLIC_PATHS.has(path)) return
  if (!isAuthenticated.value) return navigateTo('/login')
  if (path === '/crew-management' && !isOperator.value) return navigateTo('/profile/personal')
})
