import { useEffect } from 'react'
import { ArrowUpRight, LoaderCircle, Power } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useShutdown, useVersion } from '@/api/system'
import { Button } from '@/components/ui/button'
import { useConnectionStore } from '@/stores/connection'

export function AboutPage() {
  const { t } = useTranslation()
  const { data } = useVersion()
  const connection = useConnectionStore(state => state.connection)
  const revision = useConnectionStore(state => state.revision)
  const shutdownRequested = useConnectionStore(state => state.shutdownRequested)
  const shutdown = useShutdown()
  const reset = shutdown.reset
  useEffect(() => { reset() }, [revision, reset])
  return <div className="workspace"><div className="about-card"><div className="brand-mark large">A</div><h1>{t('about.title')}</h1><p>{t('about.subtitle')}</p><span className="subtle-badge">{data?.version ?? 'AiNiee'}</span><p className="about-description">{t('about.description')}</p><a className="text-link" href="https://github.com/NEKOparapa/AiNiee" target="_blank" rel="noreferrer">{t('about.source')}<ArrowUpRight size={16}/></a><p className="workspace-tip">{t('about.note')}</p>
    <p>{t('about.exitHint')}</p>
    <Button variant="outline" disabled={!connection || shutdown.isPending || shutdownRequested} onClick={() => { if (window.confirm(t('about.confirmExit'))) shutdown.mutate() }}>{shutdown.isPending ? <LoaderCircle size={16} className="animate-spin"/> : <Power size={16}/>} {t(shutdown.isPending ? 'about.exitRequesting' : 'about.exit')}</Button>
    {shutdownRequested && <p role="status">{t('about.exitAccepted')}</p>}
    {shutdown.error && <p role="alert" className="form-error">{t('about.exitFailed')}</p>}
  </div></div>
}
