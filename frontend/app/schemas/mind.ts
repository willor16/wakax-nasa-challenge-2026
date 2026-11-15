import { z } from 'zod'

const scale = z.number().int().min(1, 'Choose a value from 1 to 5.').max(5, 'Choose a value from 1 to 5.')
const clock = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Use a time like 22:18.')

export const psychCheckinSchema = z.object({
  moodState: z.enum(['CALM', 'FOCUSED', 'TIRED', 'STRESSED']),
  mood: scale,
  stress: scale,
  isolation: scale,
  motivation: scale,
  sleepOnsetUtc: clock,
  wakeUtc: clock,
})

export type PsychCheckin = z.infer<typeof psychCheckinSchema>
