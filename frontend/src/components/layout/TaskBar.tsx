import { ChevronUp, Circle, Coins, Play, Square, Terminal } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { useBackendStore } from '@/stores/backend'
import { useConnectionStore } from '@/stores/connection'
import { useTaskAction } from '@/api/tasks'
import { ApiError } from '@/api/client'
import { taskErrorKey } from '@/workspaces/tasks/translations'
import '@/workspaces/tasks/tasks.css'

export function TaskBar({ onOpenLogs }: { onOpenLogs: () => void }) {
  const { t } = useTranslation()
  const { t: tt } = useTranslation('tasks')
  const task = useBackendStore(state => state.currentTask)
  const progress = useBackendStore(state => state.progress)
  const connected = useConnectionStore(state => state.status === 'connected')
  const action = useTaskAction()
  const busy = !!task && !['idle', 'stopped', 'completed', 'failed'].includes(task.status)
  const total = progress?.total_line ?? 0
  const done = progress?.line ?? 0
  const active = task?.status === 'running' || task?.status === 'analysis'
  const percent = task?.mode === 'analysis' ? task.analysis_progress?.percent ?? 0 : total ? Math.min(100, Math.round(done / total * 100)) : 0
  const status = task?.status === 'completed' || task?.status === 'failed' ? tt(task.status) : task?.status === 'running' && task.mode === 'polish' ? tt('polishing') : t(`task.${task?.status ?? 'idle'}`)
  return <footer className="task-bar">
    <div className="task-status"><Circle size={8} className={active ? 'active-status' : ''} fill="currentColor"/><span>{status}</span></div>
    <div className="task-progress"><div className="progress-track" role="progressbar" aria-label={status} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}><span style={{ width: `${percent}%` }}/></div><span>{task?.mode === 'analysis' ? `${percent}%` : t('task.lines', { done, total })}</span></div>
    <div className="task-controls">
      {busy ? <Button size="sm" variant="secondary" disabled={!active || action.isPending || !connected} onClick={() => action.mutate({ mode: 'stop' })}><Square size={13}/>{tt('stop')}</Button> : <>
        <Button size="sm" disabled={!connected || !task?.project_id || action.isPending} onClick={() => action.mutate({ mode: 'translate' })}><Play size={13}/>{tt('translate')}</Button>
        <Button size="sm" variant="secondary" disabled={!connected || !task?.project_id || action.isPending} onClick={() => action.mutate({ mode: 'polish' })}>{tt('polish')}</Button>
        {task?.can_continue && <Button size="sm" variant="secondary" disabled={action.isPending || !connected} onClick={() => action.mutate({ mode: task.mode === 'polish' ? 'polish' : 'translate', resume: true })}>{tt('resume')}</Button>}
      </>}
    </div>
    <div className="task-metrics"><span>{t('task.tokens', { count: progress?.token ?? 0 })}</span><span className="cost" title={tt('costDetail')}><Coins size={13}/>{t('task.cost')}</span></div>
    <Button variant="ghost" size="sm" onClick={onOpenLogs} aria-label={t('task.openLogs')}><Terminal size={15}/><span>{t('task.logTitle')}</span><ChevronUp size={13}/></Button>
    {(action.error || task?.last_error) && <div className="task-action-error" role="alert">{tt(taskErrorKey(action.error instanceof ApiError ? action.error.code : task?.last_error ?? 'request'))}<button onClick={() => { action.reset(); onOpenLogs() }}>{t('task.openLogs')}</button></div>}
  </footer>
}
