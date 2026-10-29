import { useTranslation } from 'react-i18next'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import './translations'

export function TableFeedback({ error, loading, retry }: { error?: unknown; loading?: boolean; retry?: () => void }) {
  const { t } = useTranslation('tables')
  if (loading) return <p role="status">{t('loading')}</p>
  if (!error) return null
  const code = error instanceof ApiError ? error.code : 'fallback'
  return <div className="table-feedback" role="alert"><span>{t(`errors.${code}`, { defaultValue: t('errors.fallback') })}</span>{retry && <Button variant="outline" onClick={retry}>{t('retry')}</Button>}</div>
}
