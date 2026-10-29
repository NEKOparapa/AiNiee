import { AlertCircle, LoaderCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import './translations'

export function ProjectFeedback({ error, loading, retry }: { error?: unknown; loading?: boolean; retry?: () => void }) {
  const { t } = useTranslation('projects')
  if (loading) return <div className="project-feedback" role="status"><LoaderCircle size={16} className="animate-spin"/>{t('loading')}</div>
  if (!error) return null
  const code = error instanceof ApiError ? error.code : 'fallback'
  return <div className="project-feedback error" role="alert"><AlertCircle size={16}/><span>{t(`errors.${code}`, { defaultValue: t('errors.fallback') })}</span>{retry && <Button type="button" variant="outline" size="sm" onClick={retry}>{t('retry')}</Button>}</div>
}
