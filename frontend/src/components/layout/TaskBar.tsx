import { ChevronUp, Circle, Coins, Terminal } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useBackendStore } from '@/stores/backend'

export function TaskBar({ onOpenLogs }: { onOpenLogs: () => void }) {
  const { t } = useTranslation()
  const task = useBackendStore(state => state.currentTask)
  const progress = useBackendStore(state => state.progress)
  const total = progress?.total_line ?? 0
  const done = progress?.line ?? 0
  const active = task?.status === 'running'
  return <footer className="task-bar"><div className="task-status"><Circle size={8} className={active ? 'active-status' : ''} fill="currentColor"/><span>{t(`task.${task?.status ?? 'idle'}`)}</span></div><div className="task-progress"><div className="progress-track" role="progressbar" aria-label={t(`task.${task?.status ?? 'idle'}`)} aria-valuemin={0} aria-valuemax={100} aria-valuenow={total ? Math.min(100, Math.round(done / total * 100)) : 0}><span style={{ width: `${total ? Math.min(100, done / total * 100) : 0}%` }}/></div><span>{t('task.lines', { done, total })}</span></div><div className="task-metrics"><span>{t('task.tokens', { count: progress?.token ?? 0 })}</span><span className="cost"><Coins size={13}/>{t('task.cost')}</span></div><Button variant="ghost" size="sm" onClick={onOpenLogs} aria-label={t('task.openLogs')}><Terminal size={15}/><span>{t('task.logTitle')}</span><ChevronUp size={13}/></Button></footer>
}
