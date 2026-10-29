import { Terminal, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { PageHeading } from '@/components/common/PageHeading'
import { useBackendStore } from '@/stores/backend'

export function LogContent() {
  const { t, i18n } = useTranslation()
  const logs = useBackendStore(state => state.logs)
  const clear = useBackendStore(state => state.clearLogs)
  return <div className="log-content"><div className="log-toolbar"><span>{t('task.logTitle')} <span className="muted">({logs.length})</span></span><Button variant="ghost" size="sm" disabled={!logs.length} onClick={clear}><Trash2 size={14}/>{t('task.clear')}</Button></div>{logs.length ? <ol className="log-entries">{logs.map((entry, index) => <li key={`${entry.ts}-${index}`}><time>{new Date(entry.ts * 1000).toLocaleTimeString(i18n.language, { hour12: false })}</time><span className={`log-level ${entry.level.toLowerCase()}`}>{entry.level}</span><pre>{entry.message}</pre></li>)}</ol> : <div className="logs-empty"><Terminal size={26} strokeWidth={1.3}/><h3>{t('task.logsEmpty')}</h3><p>{t('task.logsDetail')}</p></div>}</div>
}

export function LogsPage() {
  const { t } = useTranslation()
  return <div className="workspace"><PageHeading title={t('nav.logs')} subtitle={t('task.taskDetail')}/><LogContent/></div>
}
