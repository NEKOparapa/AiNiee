import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Clock3, FolderOpen, LoaderCircle, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useDeleteHistory, useProjectHistory, type ProjectHistory as History } from '@/api/projects'
import { Button } from '@/components/ui/button'
import { ProjectFeedback } from './ProjectFeedback'

function DeleteDialog({ history, onClose, onDeleted }: { history: History; onClose: () => void; onDeleted: () => void }) {
  const { t } = useTranslation('projects')
  const dialog = useRef<HTMLDialogElement>(null)
  const deletion = useDeleteHistory()
  useEffect(() => { dialog.current?.showModal(); return () => dialog.current?.close() }, [])
  const remove = async () => {
    try { await deletion.mutateAsync(history.project_id); onDeleted() } catch { /* Keep the confirmation open with its error. */ }
  }
  return <dialog className="project-dialog" ref={dialog} aria-labelledby="delete-project-title" onCancel={event => { if (deletion.isPending) event.preventDefault(); else onClose() }}>
    <h2 id="delete-project-title">{t('deleteTitle')}</h2><p>{t('deleteDetail', { name: history.project_name })}</p>
    <ProjectFeedback error={deletion.error}/>
    <footer><Button variant="outline" onClick={onClose} disabled={deletion.isPending}>{t('cancel')}</Button><Button className="project-dialog-danger" disabled={deletion.isPending} onClick={() => void remove()}>{deletion.isPending && <LoaderCircle size={15} className="animate-spin"/>}{t(deletion.isPending ? 'deleting' : 'remove')}</Button></footer>
  </dialog>
}

export function ProjectHistory({ currentId, pending, onContinue }: { currentId?: string; pending: boolean; onContinue: (path: string) => void }) {
  const { t, i18n } = useTranslation('projects')
  const history = useProjectHistory()
  const [deleting, setDeleting] = useState<History | null>(null)
  const date = (value: string) => {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium', timeStyle: 'short' }).format(parsed)
  }
  return <section className="project-history" aria-labelledby="project-history-title">
    <div className="section-heading"><h2 id="project-history-title">{t('historyTitle')}</h2><p>{t('historyDetail')}</p></div>
    <ProjectFeedback loading={history.isPending} error={history.error} retry={() => void history.refetch()}/>
    {history.isSuccess && (history.data.length ? <div className="project-history-grid">{history.data.map(item => <article className="project-history-card" key={item.project_id} aria-label={item.project_name}>
      <header><FolderOpen size={21} strokeWidth={1.5}/><div><h3>{item.project_name}</h3><time dateTime={item.project_create_time}>{date(item.project_create_time)}</time></div><Button variant="ghost" size="icon-sm" aria-label={`${t('remove')} ${item.project_name}`} title={item.project_id === currentId ? t('deleteCurrentHint') : t('remove')} disabled={pending || item.project_id === currentId} onClick={() => setDeleting(item)}><Trash2 size={15}/></Button></header>
      <div className="project-history-progress"><span>{item.total_line > 0 ? t('historyProgress', { done: item.line, total: item.total_line }) : t('historyNoStats')}</span><span>{t(item.total_line > 0 ? item.is_complete ? 'complete' : 'pending' : 'notStarted')}</span></div><progress aria-label={`${item.project_name} ${t('progress')}`} value={item.line} max={item.total_line || 1}/>
      <footer>{item.project_id === currentId ? <><span className="subtle-badge">{t('current')}</span><Button asChild size="sm" variant="outline"><Link to="/project">{t('viewProject')}<ArrowRight size={14}/></Link></Button></> : <><span/><Button size="sm" variant="outline" disabled={pending} onClick={() => onContinue(item.cache_path)}>{pending ? <LoaderCircle size={14} className="animate-spin"/> : <ArrowRight size={14}/>} {t('continue')}</Button></>}</footer>
    </article>)}</div> : <div className="project-empty-state history-empty"><Clock3 size={30} strokeWidth={1.3}/><h2>{t('noHistory')}</h2><p>{t('noHistoryDetail')}</p></div>)}
    {deleting && <DeleteDialog history={deleting} onClose={() => setDeleting(null)} onDeleted={() => setDeleting(null)}/ >}
  </section>
}
