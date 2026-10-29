import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Plus, Save, ScanText, Trash2, Upload } from 'lucide-react'
import { useAnalysis, useSaveAnalysis, useAnalysisTables, analysisKey, type AnalysisDocument, type AnalysisView } from '@/api/analysis'
import { getApiClient, assertCurrentConnection, ApiError } from '@/api/client'
import { useCurrentProject, projectError } from '@/api/projects'
import { useTaskAction } from '@/api/tasks'
import { downloadFile, fileBase64 } from '@/api/files'
import { queryKeys } from '@/api/query-client'
import { useConnectionStore } from '@/stores/connection'
import { useBackendStore } from '@/stores/backend'
import { useUiContextStore } from '@/stores/ui-context'
import { PageState } from '@/components/common/PageState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import './translations'
import './styles.css'

const views: AnalysisView[] = ['characters', 'terms', 'non_translate']
const columns = { characters: ['source', 'recommended_translation', 'gender', 'occurrence_count', 'note'], terms: ['source', 'recommended_translation', 'category_path', 'occurrence_count', 'note'], non_translate: ['marker', 'category', 'occurrence_count', 'note'] } as const
const categoryField = { characters: 'gender', terms: 'category_path', non_translate: 'category' } as const
type Row = AnalysisDocument[AnalysisView][number]

export function AnalysisPage() {
  const { t } = useTranslation('analysis')
  const revision = useConnectionStore(state => state.revision)
  const connection = useConnectionStore(state => state.connection)
  const task = useBackendStore(state => state.currentTask)
  const current = useCurrentProject()
  const projectId = current.data?.project?.project_id
  const analysis = useAnalysis(projectId)
  const save = useSaveAnalysis()
  const taskAction = useTaskAction()
  const client = useQueryClient()
  const [view, setView] = useState<AnalysisView>('characters')
  const [draft, setDraft] = useState<AnalysisDocument | null>(null)
  const [dirty, setDirty] = useState(false)
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [page, setPage] = useState(0)
  const [tableId, setTableId] = useState('')
  const [moveCategory, setMoveCategory] = useState('')
  const [message, setMessage] = useState('')
  const tables = useAnalysisTables(view)
  const upload = useRef<HTMLInputElement>(null)
  const context = useRef({ revision, projectId })
  context.current = { revision, projectId }
  useEffect(() => { setDraft(null); setDirty(false); setSelected(new Set()); setMessage('') }, [projectId, revision])
  useEffect(() => { const value = analysis.data; if (!dirty && value && value.project_id === projectId) setDraft(value) }, [analysis.data, projectId, dirty])
  useEffect(() => { setSelected(new Set()); setCategory(''); setQ(''); setPage(0); setTableId(''); setMessage('') }, [view])
  useEffect(() => { useUiContextStore.getState().setSelectedItemIds([...selected].map(index => `analysis:${projectId}:${view}:${index}`)); useUiContextStore.getState().setFilters({ view, q, category }) }, [selected, projectId, view, q, category])
  const rows: Row[] = draft?.[view] ?? []
  const filtered = rows.flatMap((row, index) => (!category || String(row[categoryField[view]]) === category) && columns[view].some(key => String(row[key] ?? '').toLowerCase().includes(q.toLowerCase())) ? [index] : [])
  const pages = Math.max(1, Math.ceil(filtered.length / 50))
  const actualPage = Math.min(page, pages - 1)
  const visible = filtered.slice(actualPage * 50, actualPage * 50 + 50)
  const categories = [...new Set(rows.map(row => String(row[categoryField[view]] ?? '')).filter(Boolean))].sort()
  const busy = !!task && !['idle', 'completed', 'stopped', 'failed'].includes(task.status)
  const replaceRows = (next: Row[]) => { if (draft) { setDraft({ ...draft, [view]: next } as AnalysisDocument); setDirty(true); setMessage('') } }
  const accept = (document: AnalysisDocument) => { if (context.current.projectId === document.project_id && context.current.revision === revision) { setDraft(document); setDirty(false); setSelected(new Set()); client.setQueryData([...analysisKey(revision), document.project_id], document) } }
  const action = useMutation({ mutationFn: async (operation: { kind: 'import'; file: File } | { kind: 'export' | 'publish' | 'move' }) => {
    if (!projectId || !draft) return
    const api = getApiClient(assertCurrentConnection(revision))
    const identities = (selected.size ? [...selected] : filtered).map(index => String(rows[index]?.[view === 'non_translate' ? 'marker' : 'source'] ?? '')).filter(Boolean)
    const params = { path: { view } }
    if (operation.kind === 'import') {
      const result = await api.POST('/api/v1/projects/current/analysis/{view}/import', { params, body: { project_id: projectId, content_base64: await fileBase64(operation.file) } })
      if (!result.data) projectError(result.response.status, result.error)
      accept(result.data.document); setMessage(t('imported', result.data))
    } else if (operation.kind === 'export') {
      const result = await api.GET('/api/v1/projects/current/analysis/{view}/export', { params: { ...params, query: { project_id: projectId, category: category || undefined, q } } })
      if (!result.data) projectError(result.response.status, result.error)
      downloadFile(result.data)
    } else if (operation.kind === 'publish') {
      const result = await api.POST('/api/v1/projects/current/analysis/{view}/publish', { params, body: { project_id: projectId, table_id: tableId || null, identities } })
      if (!result.data) projectError(result.response.status, result.error)
      setMessage(t('published', { count: result.data.added }))
      await client.invalidateQueries({ queryKey: [...queryKeys.connection(revision), 'tables'] })
    } else {
      const result = await api.POST('/api/v1/projects/current/analysis/{view}/move', { params, body: { project_id: projectId, identities, target: view === 'characters' ? 'terms' : 'characters', category: moveCategory || (view === 'characters' ? 'Other' : '其他') } })
      if (!result.data) projectError(result.response.status, result.error)
      accept(result.data)
    }
  } })
  const disabled = busy || save.isPending || action.isPending
  const error = action.error || save.error || taskAction.error || analysis.error || current.error
  const errorCode = error instanceof ApiError ? error.code : error instanceof Error ? error.message : ''
  return <div className="workspace analysis-workspace"><header className="page-heading"><div><h1>{t('title')}</h1><p>{t('description')}</p></div><Button disabled={!projectId || disabled || dirty || taskAction.isPending} onClick={() => { if (window.confirm(t('confirmStart'))) taskAction.mutate({ mode: 'analysis' }) }}><ScanText size={16}/>{t('start')}</Button></header>
    {!connection ? <PageState disconnected/> : current.isPending || analysis.isPending && projectId ? <PageState/> : !projectId ? <p>{t('noProject')}</p> : <>
      <section className="analysis-progress"><div><strong>{task?.mode === 'analysis' ? task.analysis_progress?.phase_label || t('title') : t('title')}</strong><p>{task?.mode === 'analysis' ? task.analysis_progress?.message : t('startHint')}</p></div>{task?.mode === 'analysis' && <span>{task.analysis_progress?.percent ?? 0}%</span>}</section>
      <div className="analysis-tabs" role="tablist">{views.map(name => <button role="tab" aria-selected={view === name} key={name} onClick={() => setView(name)}>{t(name)}<small>{draft?.[name].length ?? 0}</small></button>)}</div>
      <div className="analysis-toolbar"><Input aria-label={t('search')} placeholder={t('search')} value={q} onChange={e => { setQ(e.target.value); setPage(0) }}/><select aria-label={t('filterCategory')} value={category} onChange={e => { setCategory(e.target.value); setPage(0) }}><option value="">{t('allCategories')}</option>{categories.map(value => <option key={value}>{value}</option>)}</select><span>{t('total', { count: filtered.length })}</span></div>
      <div className="analysis-actions"><Button disabled={disabled} variant="outline" onClick={() => { const row = view === 'characters' ? { source: '', recommended_translation: '', gender: category || '其他', occurrence_count: 1, note: '' } : view === 'terms' ? { source: '', recommended_translation: '', category_path: category || 'Other', occurrence_count: 1, note: '' } : { marker: '', category: category || 'Other', occurrence_count: 1, note: '' }; replaceRows([...rows, row]); setQ(''); setPage(Math.floor(rows.length / 50)) }}><Plus size={15}/>{t('add')}</Button><Button disabled={disabled || !selected.size} variant="outline" onClick={() => { if (window.confirm(t('removeConfirm'))) { replaceRows(rows.filter((_, index) => !selected.has(index))); setSelected(new Set()) } }}><Trash2 size={15}/>{t('remove')}</Button><Button disabled={disabled || !dirty} onClick={() => { if (draft) save.mutate(draft, { onSuccess: value => { accept(value); setMessage(t('saved')) } }) }}><Save size={15}/>{t('save')}</Button>{dirty && <><span className="dirty">{t('dirty')}</span><Button variant="ghost" onClick={() => { setDirty(false); setDraft(analysis.data ?? null) }}>{t('discard')}</Button></>}<Button variant="ghost" disabled={disabled || dirty} onClick={() => upload.current?.click()}><Upload size={15}/>{t('import')}</Button><Button variant="ghost" disabled={disabled || dirty || !filtered.length} onClick={() => action.mutate({ kind: 'export' })}><Download size={15}/>{t('export')}</Button><input ref={upload} type="file" accept=".json" hidden onChange={e => { const file = e.target.files?.[0]; if (file) action.mutate({ kind: 'import', file }); e.target.value = '' }}/></div>
      <div className="analysis-grid-wrap"><table className="analysis-grid"><thead><tr><th><input type="checkbox" aria-label={t('all')} checked={visible.length > 0 && visible.every(index => selected.has(index))} onChange={e => { const next = new Set(selected); visible.forEach(index => e.target.checked ? next.add(index) : next.delete(index)); setSelected(next) }}/></th>{columns[view].map(key => <th key={key}>{t(key)}</th>)}</tr></thead><tbody>{visible.map(index => <tr key={`${view}:${index}`} className={selected.has(index) ? 'selected' : ''}><td><input type="checkbox" aria-label={`${index + 1}`} checked={selected.has(index)} onChange={e => { const next = new Set(selected); if (e.target.checked) next.add(index); else next.delete(index); setSelected(next) }}/></td>{columns[view].map(key => <td key={key} className={key === 'note' ? 'analysis-note' : ''}>{key === 'occurrence_count' ? <Input type="number" min={1} aria-label={`${t(key)} ${index + 1}`} value={Number(rows[index][key] ?? 1)} disabled={disabled} onChange={e => replaceRows(rows.map((row, i) => i === index ? { ...row, [key]: Math.max(1, Number(e.target.value)) } : row))}/> : <textarea rows={2} aria-label={`${t(key)} ${index + 1}`} value={String(rows[index][key] ?? '')} disabled={disabled} onChange={e => replaceRows(rows.map((row, i) => i === index ? { ...row, [key]: e.target.value } : row))}/>}</td>)}</tr>)}</tbody></table>{!visible.length && <p className="analysis-empty">{t('empty')}</p>}</div>
      <div className="analysis-pagination"><span>{t('selected', { count: selected.size })}</span><Button variant="ghost" disabled={!actualPage} onClick={() => setPage(actualPage - 1)}>{t('previous')}</Button><span>{t('page', { page: actualPage + 1, total: pages })}</span><Button variant="ghost" disabled={actualPage >= pages - 1} onClick={() => setPage(actualPage + 1)}>{t('next')}</Button></div>
      <div className="analysis-actions"><select aria-label={t('publishTarget')} value={tableId} onChange={e => setTableId(e.target.value)}><option value="">{t('defaultTable')}</option>{tables.data?.tables.map(table => <option key={table.id} value={table.id}>{table.name}</option>)}</select><Button variant="secondary" disabled={disabled || dirty || !filtered.length} onClick={() => action.mutate({ kind: 'publish' })}>{t('publish')}</Button>{view !== 'non_translate' && <><Input aria-label={t('moveCategory')} placeholder={t('moveCategory')} value={moveCategory} onChange={e => setMoveCategory(e.target.value)}/><Button variant="outline" disabled={disabled || dirty || !selected.size} onClick={() => { if (window.confirm(t('moveConfirm'))) action.mutate({ kind: 'move' }) }}>{t(view === 'characters' ? 'toTerms' : 'toCharacters')}</Button></>}</div>
      {message && <p className="analysis-message" role="status">{message}</p>}
    </>}{error && <div className="inline-error" role="alert">{t(['project_changed', 'operation_busy', 'file_too_large'].includes(errorCode) ? errorCode : 'error')}<Button variant="ghost" onClick={() => { setDirty(false); void current.refetch(); void analysis.refetch() }}>{t('reload')}</Button></div>}</div>
}
