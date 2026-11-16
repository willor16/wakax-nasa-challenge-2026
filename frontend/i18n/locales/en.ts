// Single interface language: clear English, with no internal technology names.
export default defineI18nLocale(() => ({
  brand: {
    name: 'Scan Space',
    mission: 'ARES VII',
  },
  header: {
    missionClock: 'MISSION CLOCK',
    notifications: 'Notifications ({count})',
    notificationsLabel: 'Open notifications, {count} open',
  },
  nav: {
    publicLabel: 'Public crew views',
    cockpitLabel: 'Health modules',
    signIn: 'Sign In',
    crewOverview: 'Crew Overview',
    crewStreaks: 'Crew Streaks',
    vision: 'Vision',
    sleep: 'Sleep',
    auscultation: 'Auscultation',
    profile: 'Profile',
    capture: 'Capture',
    guide: 'Guide',
    comms: 'Comms',
    signOut: 'Sign Out',
  },
  profileTabs: {
    label: 'Profile sections',
    personal: 'Personal Data',
    psychological: 'Psychological',
    physical: 'Physical',
  },
  captureTabs: {
    label: 'Capture sections',
    auscultation: 'Auscultation Audio',
    physical: 'Physical & Labs',
    vision: 'Vision & Ocular',
    psychSleep: 'Psych, Motor & Sleep',
    feeds: 'DATA CAPTURE · FEEDS ALL MODULES',
  },
  status: {
    optimal: 'OPTIMAL',
    nominal: 'NOMINAL',
    attention: 'ATTENTION',
    noData: 'NO DATA',
  },
}))
