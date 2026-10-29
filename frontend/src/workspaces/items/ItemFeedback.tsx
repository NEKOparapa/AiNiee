import { useTranslation } from 'react-i18next'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import './translations'

export function ItemFeedback({ error, retry }: { error: unknown; retry?: () => void }) {
  const { t } = useTranslation('items')
  if (!error) return null
  const code = error instanceof ApiError ? error.code : 'fallback'
  return <div className="items-feedback" role="alert">{t(`errors.${code}`, { defaultValue: t('errors.fallback') })}{retry && <Button variant="outline" size="sm" onClick={retry}>{t('retry')}</Button>}{code === 'project_changed' && <Button variant="outline" size="sm" onClick={() => window.location.reload()}>{t('reload')}</Button>}</div>
}
