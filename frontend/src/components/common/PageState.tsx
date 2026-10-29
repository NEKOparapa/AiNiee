import { AlertCircle, LoaderCircle, PlugZap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

export function PageState({ error = false, disconnected = false, retry }: { error?: boolean; disconnected?: boolean; retry?: () => void }) {
  const { t } = useTranslation()
  const Icon = disconnected ? PlugZap : error ? AlertCircle : LoaderCircle
  return <div className="page-state" role={error ? 'alert' : 'status'}><Icon className={!error && !disconnected ? 'animate-spin' : ''} size={28} /><p>{t(disconnected ? 'connection.required' : error ? 'common.error' : 'common.loading')}</p>{retry && <Button variant="outline" onClick={retry}>{t('common.retry')}</Button>}</div>
}
