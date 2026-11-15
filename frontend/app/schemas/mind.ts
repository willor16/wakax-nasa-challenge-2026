import { z } from 'zod'

// Messages are locale keys (i18n/locales/en.ts); the page shows them with $t.
const SCALE_ERROR = 'mind.capture.errors.scale'
const CLOCK_ERROR = 'mind.capture.errors.clock'

// Nothing is chosen in advance: the crew member must pick every scale.
const scale = z.number({ required_error: SCALE_ERROR, invalid_type_error: SCALE_ERROR }).int().min(1, SCALE_ERROR).max(5, SCALE_ERROR)
// The sleep window is optional; an empty field means "not reported".
const clock = z.union([z.literal(''), z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, CLOCK_ERROR)])

export const psychCheckinSchema = z.object({
  moodState: z.enum(['CALM', 'FOCUSED', 'TIRED', 'STRESSED']).nullable(),
  mood: scale,
  stress: scale,
  isolation: scale,
  motivation: scale,
  sleepOnsetUtc: clock,
  wakeUtc: clock,
})

export type PsychCheckin = z.infer<typeof psychCheckinSchema>
