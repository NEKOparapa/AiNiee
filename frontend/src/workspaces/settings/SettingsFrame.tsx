import { useId, type ReactNode } from 'react'
import { CircleCheck, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { useConfig } from '@/api/config'
import type { ApiConfig } from '@/api/types'
import { Button } from '@/components/ui/button'
import { useConnectionStore } from '@/stores/connection'

import './styles.css'

export function SettingsFrame({ page, children }: {
  page: 'task' | 'output' | 'advanced'
  children: (config: ApiConfig) => ReactNode
}) {
  const { t } = useTranslation('settings')
  const query = useConfig()
  const connected = useConnectionStore((state) => state.connection !== null)
  const id = useId()
  return <section className="settings-page" aria-labelledby={id}>
    <header className="settings-page-heading">
      <div><p className="settings-eyebrow">{t('eyebrow')}</p><h1 id={id}>{t(`${page}.title`)}</h1>
        <p className="settings-description">{t(`${page}.description`)}</p></div>
      <span className="settings-autosave"><CircleCheck size={15} />{t('autoSave')}</span>
    </header>
    {!connected && <div className="settings-load-error" role="status"><p>{t('connectRequired')}</p></div>}
    {connected && query.isPending && <div className="settings-loading" role="status" aria-label={t('loading')}>
      <span>{t('loading')}</span>{[0, 1, 2].map((item) => <div key={item} className="settings-skeleton" />)}
    </div>}
    {connected && query.isError && <div className="settings-load-error" role="alert"><p>{t('loadError')}</p>
      <Button variant="outline" onClick={() => { void query.refetch() }}><RefreshCw size={15} />{t('retry')}</Button></div>}
    {connected && query.data && !query.isError && children(query.data)}
  </section>
}
