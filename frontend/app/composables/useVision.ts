import type { components, paths } from '~/types/api'

export type VisionExamOut
  = paths['/api/v1/vision/{crew_id}']['get']['responses'][200]['content']['application/json']

export type VisionReviewCreateIn = components['schemas']['VisionReviewCreateIn']
export type VisionReviewCreatedOut
  = paths['/api/v1/vision/{crew_id}/review']['post']['responses'][201]['content']['application/json']

export type VisionStageFilter = 'ALL' | 'LAUNCH' | 'MISSION' | 'RETURN'
export type VisionClinicalMetric = components['schemas']['VisionClinicalMetricOut']
export type VisionPreventiveStep = components['schemas']['VisionPreventiveStepOut']

export function useVision() {
  const { activeCrew, authHeaders } = useSession()

  const selectedStage = ref<VisionStageFilter>('ALL')
  const exam = ref<VisionExamOut | null>(null)
  const isLoading = ref(true)
  const errorMessage = ref('')

  const effectiveCrewId = computed(() => activeCrew.value?.id ?? 'ID-01')

  async function loadVisionExam() {
    isLoading.value = true
    errorMessage.value = ''
    try {
      const query = selectedStage.value === 'ALL'
        ? undefined
        : { stage: selectedStage.value }
      const data = await $fetch<VisionExamOut>(
        `/api/v1/vision/${encodeURIComponent(effectiveCrewId.value)}`,
        {
          query,
          headers: authHeaders(),
        },
      )
      exam.value = data
    }
    catch {
      errorMessage.value = 'Unable to load bilateral ocular telemetry from local storage.'
    }
    finally {
      isLoading.value = false
    }
  }

  async function submitPhysicianReview(
    payload: VisionReviewCreateIn,
    targetCrewId?: string,
  ): Promise<VisionReviewCreatedOut> {
    const target = targetCrewId ?? effectiveCrewId.value
    const result = await $fetch<VisionReviewCreatedOut>(
      `/api/v1/vision/${encodeURIComponent(target)}/review`,
      {
        method: 'POST',
        headers: authHeaders(),
        body: payload,
      },
    )
    if (target === effectiveCrewId.value) {
      await loadVisionExam()
    }
    return result
  }

  watch([effectiveCrewId, selectedStage], () => {
    void loadVisionExam()
  })

  return {
    exam,
    selectedStage,
    effectiveCrewId,
    isLoading,
    errorMessage,
    loadVisionExam,
    submitPhysicianReview,
  }
}
