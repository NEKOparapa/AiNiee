import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { components } from './generated/schema'
import { assertCurrentConnection, getApiClient } from './client'
import { projectError } from './projects'
import { itemKeys } from './items'
import { queryKeys } from './query-client'
import { useConnectionStore } from '@/stores/connection'

export type CheckResult = components['schemas']['CheckResponse']
export type CheckIssue = components['schemas']['CheckIssue']
export type RuleOptions = components['schemas']['RuleOptions']
export type LanguageOptions = components['schemas']['LanguageCheckRequest']
export type TerminologyOptions = components['schemas']['TerminologyCheckRequest']
type CheckInput = { kind: 'rule'; body: components['schemas']['RuleCheckRequest'] } | { kind: 'language'; body: LanguageOptions } | { kind: 'terminology'; body: TerminologyOptions }

export function useRunCheck() {
  const revision = useConnectionStore(s => s.revision)
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (input: CheckInput) => {
      const api = getApiClient(assertCurrentConnection(revision))
      const result = input.kind === 'rule' ? await api.POST('/api/v1/checks/rule', { body: input.body }) : input.kind === 'language' ? await api.POST('/api/v1/checks/language', { body: input.body }) : await api.POST('/api/v1/checks/terminology', { body: input.body })
      if (!result.data) projectError(result.response.status, result.error)
      return result.data
    },
    onSettled: async () => {
      if (useConnectionStore.getState().revision !== revision) return
      await Promise.all([
        client.invalidateQueries({ queryKey: itemKeys.all(revision) }),
        client.invalidateQueries({ queryKey: queryKeys.config(revision) }),
      ])
    },
  })
}
