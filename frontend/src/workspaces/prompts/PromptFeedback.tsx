import { useTranslation } from 'react-i18next'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import './translations'

export function PromptFeedback({ error, loading, retry }: { error?: unknown; loading?: boolean; retry?: () => void }) {
  const { t } = useTranslation('prompts')
  if (loading) return <p role="status">{t('load')}</p>
  if (!error) return null
  const code = error instanceof ApiError ? error.code : 'fallback'
  return <div className="table-feedback" role="alert"><span>{t(`errors.${code}`, { defaultValue: t('errors.fallback') })}</span>{retry && <Button variant="outline" onClick={retry}>{t('retry')}</Button>}</div>
}
