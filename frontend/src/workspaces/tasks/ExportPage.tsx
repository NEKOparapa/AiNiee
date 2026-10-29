import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Download, Save } from 'lucide-react'
import { getApiClient, assertCurrentConnection, ApiError } from '@/api/client'
import { projectError } from '@/api/projects'
import { useConnectionStore } from '@/stores/connection'
import { useBackendStore } from '@/stores/backend'
import { useCurrentTask } from '@/api/tasks'
import { PageState } from '@/components/common/PageState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DirectoryBrowser } from '@/workspaces/projects/DirectoryBrowser'
import { taskErrorKey } from './translations'
import './tasks.css'

export function ExportPage() {
  const { t } = useTranslation('tasks')
  const revision = useConnectionStore(state => state.revision)
  const connected = useConnectionStore(state => state.connection !== null)
  const task = useBackendStore(state => state.currentTask)
  const current = useCurrentTask()
  const [path, setPath] = useState('')
  const [browsing, setBrowsing] = useState(false)
  const exporter = useMutation({ mutationFn: async () => {
    const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/export', { body: { output_path: path.trim() || undefined } })
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  } })
  const saver = useMutation({ mutationFn: async () => {
    const result = await getApiClient(assertCurrentConnection(revision)).POST('/api/v1/cache/save')
    if (!result.data) projectError(result.response.status, result.error)
    return result.data
  } })
  const resetExport = exporter.reset
  const resetSave = saver.reset
  useEffect(() => { resetExport(); resetSave(); setBrowsing(false) }, [revision, task?.project_id, resetExport, resetSave])
  const disabled = !connected || !task?.project_id || !['idle', 'stopped', 'completed', 'failed'].includes(task.status) || exporter.isPending || saver.isPending
  const error = exporter.error || saver.error
  return <div className="workspace"><header className="page-heading"><div><h1>{t('exportTitle')}</h1><p>{t('exportDetail')}</p></div></header>
    {!connected ? <PageState disconnected/> : current.isPending ? <PageState/> : current.isError ? <PageState error retry={() => void current.refetch()}/> : !task?.project_id ? <p role="status">{t('noProject')}</p> : <section className="settings-section export-card" aria-busy={exporter.isPending || saver.isPending}><label htmlFor="export-path">{t('output')}</label><div className="export-path"><Input id="export-path" value={path} disabled={exporter.isPending || saver.isPending} onChange={e => setPath(e.target.value)}/><Button variant="secondary" disabled={exporter.isPending || saver.isPending} onClick={() => setBrowsing(true)}>{t('browse')}</Button></div><p className="export-hint">{t('outputHint')}</p><div className="export-actions"><Button disabled={disabled} onClick={() => { saver.reset(); exporter.mutate() }}><Download size={16}/>{t(exporter.isPending ? 'exporting' : 'export')}</Button><Button variant="secondary" disabled={disabled} onClick={() => { exporter.reset(); saver.mutate() }}><Save size={16}/>{t(saver.isPending ? 'cacheSaving' : 'saveCache')}</Button></div>{(exporter.isPending || saver.isPending) && <p role="status">{t(exporter.isPending ? 'exporting' : 'cacheSaving')}</p>}</section>}
    {error && <p role="alert">{t(taskErrorKey(error instanceof ApiError ? error.code : 'request'))}</p>}
    {saver.isSuccess && <p role="status">{t('cacheSaved')}</p>}
    {exporter.data && <section className="settings-section export-results" role="status"><h2>{t('exported')}</h2><p>{exporter.data.output_path}</p><h3>{t('files')}</h3>{exporter.data.files.length ? <ul>{exporter.data.files.map(file => <li key={file}>{file}</li>)}</ul> : <p>{t('noFiles')}</p>}</section>}
    {browsing && <DirectoryBrowser initialPath={path} onSelect={value => { setPath(value); setBrowsing(false) }} onClose={() => setBrowsing(false)}/>}
  </div>
}
