import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ChevronLeft, ChevronRight, FileText, Flag, Search } from 'lucide-react'
import { useItems, usePatchItem, type Item, type ItemQuery } from '@/api/items'
import { useCurrentProject, useProjectFiles } from '@/api/projects'
import { useConnectionStore } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { PageState } from '@/components/common/PageState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ItemFeedback } from './ItemFeedback'
import './translations'
import './styles.css'

const PAGE_SIZE = 100
const ROW_HEIGHT = 128
const statuses = [0, 1, 2, 7, 8] as const
type TextField = 'source_text' | 'translated_text'

export function VirtualItemTable({ items, selected, highlighted, onSelect, onSelectAll, onSave, pending }: {
  items: Item[]; selected: string[]; highlighted: number | null; onSelect: (id: string) => void;
  onSelectAll: () => void; onSave: (item: Item, field: TextField, value: string) => Promise<unknown>; pending: boolean;
}) {
  const { t } = useTranslation('items')
  const scrollRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [height, setHeight] = useState(640)
  const [editing, setEditing] = useState<{ id: string; field: TextField; text: string } | null>(null)
  const selectedSet = useMemo(() => new Set(selected), [selected])
  const allSelected = useMemo(() => items.length > 0 && items.every(item => selectedSet.has(item.id)), [items, selectedSet])
  const highlightedPosition = useMemo(() => highlighted === null ? -1 : items.findIndex(item => item.index === highlighted), [items, highlighted])
  useEffect(() => {
    const element = scrollRef.current
    if (!element) return
    const update = () => setHeight(element.clientHeight || 640)
    update()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    if (highlightedPosition < 0 || !scrollRef.current) return
    scrollRef.current.scrollTop = highlightedPosition * ROW_HEIGHT
    setScrollTop(highlightedPosition * ROW_HEIGHT)
  }, [highlightedPosition])
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - 3)
  const end = Math.min(items.length, Math.ceil((scrollTop + height) / ROW_HEIGHT) + 3)
  async function save(item: Item) {
    if (!editing || pending) return
    try { await onSave(item, editing.field, editing.text); setEditing(null) } catch { /* The page exposes the mutation error. */ }
  }
  return <div className="item-table" role="table" aria-label={t('title')} aria-rowcount={items.length + 1}>
    <div className="item-table-heading" role="row"><div role="columnheader"><input type="checkbox" aria-label={t('selectPage')} checked={allSelected} onChange={onSelectAll}/></div><div role="columnheader">{t('file')} / {t('line')}</div><div role="columnheader">{t('source')}</div><div role="columnheader">{t('translation')}</div></div>
    <div className="item-table-scroll" ref={scrollRef} onScroll={event => setScrollTop(event.currentTarget.scrollTop)}>
      <div className="item-table-spacer" style={{ height: items.length * ROW_HEIGHT }}>
        {items.slice(start, end).map((item, offset) => <div key={item.id} className={`item-table-row ${selectedSet.has(item.id) ? 'selected' : ''} ${item.index === highlighted ? 'highlighted' : ''}`} role="row" aria-rowindex={start + offset + 2} style={{ top: (start + offset) * ROW_HEIGHT, height: ROW_HEIGHT }}>
          <div role="cell"><input type="checkbox" checked={selectedSet.has(item.id)} aria-label={t('select', { index: item.position + 1 })} onChange={() => onSelect(item.id)}/></div>
          <div role="cell" className="item-location"><span title={item.file}><FileText size={13}/>{item.file}</span><b>#{item.position + 1}</b><small>{t(`states.${item.translation_status}`, { defaultValue: String(item.translation_status) })}</small>{item.flagged && <Flag size={13} aria-label={t('flagged')}/>}</div>
          {(['source_text', 'translated_text'] as const).map(field => <div role="cell" className="item-text-cell" key={field}>
            {editing?.id === item.id && editing.field === field ? <div className="item-editor"><textarea autoFocus aria-label={t('edit', { field: t(field === 'source_text' ? 'source' : 'translation') })} value={editing.text} disabled={pending} onChange={event => setEditing({ ...editing, text: event.target.value })} onKeyDown={event => { if (event.key === 'Escape' && !pending) setEditing(null); if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void save(item) } }}/><div><Button size="sm" onClick={() => void save(item)} disabled={pending}>{t(pending ? 'saving' : 'save')}</Button><Button variant="ghost" size="sm" disabled={pending} onClick={() => setEditing(null)}>{t('cancel')}</Button></div></div> : <button className="item-text-button" disabled={pending} onClick={() => setEditing({ id: item.id, field, text: item[field] })} aria-label={t('edit', { field: t(field === 'source_text' ? 'source' : 'translation') })} title={item[field]}>{item[field] || '—'}</button>}
          </div>)}
        </div>)}
      </div>
    </div>
  </div>
}

export function ItemsPage() {
  const { t } = useTranslation('items')
  const connection = useConnectionStore(s => s.connection)
  const revision = useConnectionStore(s => s.revision)
  const current = useCurrentProject()
  const projectId = current.data?.project?.project_id
  const files = useProjectFiles(Boolean(connection && projectId))
  const [params, setParams] = useSearchParams()
  const statusValue = Number(params.get('status'))
  const query: ItemQuery = {
    file: params.get('file') || undefined,
    status: params.has('status') && statuses.some(status => status === statusValue) ? statusValue as 0 | 1 | 2 | 7 | 8 : undefined,
    q: params.get('q') ?? '', regex: params.get('regex') === 'true', flagged: params.get('flagged') === 'true' ? true : undefined,
    page: Math.max(1, Number(params.get('page')) || 1), size: PAGE_SIZE,
  }
  const [search, setSearch] = useState(query.q ?? '')
  const selected = useUiContextStore(s => s.selectedItemIds)
  const items = useItems(projectId, query)
  const mutation = usePatchItem()
  const highlight = params.has('index') ? Number(params.get('index')) : null
  const previousProject = useRef(projectId)
  useEffect(() => {
    if (previousProject.current && previousProject.current !== projectId) {
      setParams({}); setSearch(''); mutation.reset()
    }
    previousProject.current = projectId
  }, [projectId, setParams, mutation])
  useEffect(() => { useUiContextStore.getState().setFilters(Object.fromEntries(params)); }, [params])
  useEffect(() => { setSearch(params.get('q') ?? '') }, [params])
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value); else next.delete(key)
    if (key !== 'page') { next.delete('page'); next.delete('index') }
    setParams(next)
  }
  const select = (id: string) => useUiContextStore.getState().setSelectedItemIds(selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id])
  const rows = items.data && items.data.project_id === projectId ? items.data.items : []
  const selectAll = () => {
    const ids = rows.map(item => item.id)
    const pageIds = new Set(ids)
    const selectedIds = new Set(selected)
    useUiContextStore.getState().setSelectedItemIds(ids.every(id => selectedIds.has(id)) ? selected.filter(id => !pageIds.has(id)) : [...new Set([...selected, ...ids])])
  }
  const page = query.page ?? 1
  const pages = Math.max(1, Math.ceil((items.data?.total ?? 0) / PAGE_SIZE))
  return <div className="workspace items-workspace">
    <header className="page-heading"><div><h1>{t('title')}</h1><p>{t('description')}</p></div></header>
    {!connection ? <PageState disconnected/> : current.isPending ? <PageState/> : current.isError ? <ItemFeedback error={current.error} retry={() => void current.refetch()}/> : !projectId ? <div className="items-empty"><FileText size={32}/><p>{t('noProject')}</p><Button asChild><Link to="/">{t('openProject')}</Link></Button></div> : <>
      <form className="items-filters" onSubmit={event => { event.preventDefault(); update('q', search) }}>
        <label>{t('file')}<select aria-label={t('file')} value={query.file ?? ''} onChange={event => update('file', event.target.value)}><option value="">{t('allFiles')}</option>{(files.data ?? []).map(file => <option key={file.path} value={file.path}>{file.path}</option>)}</select></label>
        <label>{t('status')}<select aria-label={t('status')} value={query.status ?? ''} onChange={event => update('status', event.target.value)}><option value="">{t('allStatus')}</option>{statuses.map(status => <option key={status} value={status}>{t(`states.${status}`)}</option>)}</select></label>
        <div className="items-search"><Search size={16}/><Input aria-label={t('search')} placeholder={t('search')} value={search} onChange={event => setSearch(event.target.value)}/></div>
        <Button type="submit" variant="outline">{t('apply')}</Button>
        <label className="items-checkbox"><input type="checkbox" checked={query.regex} onChange={event => update('regex', event.target.checked ? 'true' : '')}/>{t('regex')}</label>
        <label className="items-checkbox"><input type="checkbox" checked={query.flagged ?? false} onChange={event => update('flagged', event.target.checked ? 'true' : '')}/>{t('flagged')}</label>
        <Button type="button" variant="ghost" onClick={() => { setParams({}); setSearch('') }}>{t('reset')}</Button>
      </form>
      <ItemFeedback error={files.error} retry={() => void files.refetch()}/><ItemFeedback error={items.error} retry={() => void items.refetch()}/><ItemFeedback error={mutation.error}/>
      <div className="items-toolbar"><span>{selected.length ? t('selected', { count: selected.length }) : t('editHint')}</span>{selected.length > 0 && <Button variant="ghost" size="sm" onClick={() => useUiContextStore.getState().setSelectedItemIds([])}>{t('clear')}</Button>}{mutation.isSuccess && <span role="status">{t('saved')}</span>}</div>
      {items.isPending ? <PageState/> : rows.length ? <VirtualItemTable key={`${revision}-${projectId}-${params.toString()}`} items={rows} selected={selected} highlighted={highlight} onSelect={select} onSelectAll={selectAll} pending={mutation.isPending} onSave={(item, field, value) => mutation.mutateAsync({ file: item.file, index: item.index, body: { project_id: projectId, [field]: value } })}/> : !items.isError && <div className="items-empty"><Search size={28}/><p>{t('empty')}</p></div>}
      {items.data && <footer className="items-pagination"><span>{t('pagination', { page, pages, total: items.data.total })}</span><Button size="sm" variant="ghost" disabled={page <= 1 || items.isFetching} onClick={() => update('page', '1')}>{t('first')}</Button><Button size="sm" variant="outline" disabled={page <= 1 || items.isFetching} onClick={() => update('page', String(page - 1))}><ChevronLeft size={16}/>{t('previous')}</Button><Button size="sm" variant="outline" disabled={page >= pages || items.isFetching} onClick={() => update('page', String(page + 1))}>{t('next')}<ChevronRight size={16}/></Button><Button size="sm" variant="ghost" disabled={page >= pages || items.isFetching} onClick={() => update('page', String(pages))}>{t('last')}</Button></footer>}
    </>}
  </div>
}
