import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Search, Trash2 } from 'lucide-react'
import type { components } from '@/api/generated/schema'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useUiContextStore } from '@/stores/ui-context'
import './translations'
import './styles.css'

export type EditorRow = components['schemas']['TableRow']
export const tableColumns = {
  glossary: ['src', 'dst', 'info', 'regex'], exclusion: ['markers', 'info', 'regex'],
  replace_a: ['src', 'dst', 'regex'], replace_b: ['src', 'dst', 'regex'],
  characters: ['original_name', 'translated_name', 'gender', 'age', 'personality', 'speech_style', 'additional_info'], examples: ['src', 'dst'],
} as const

export function TableRowsEditor({ rows, columns, onChange, contextId, disabled = false }: { rows: EditorRow[]; columns: readonly string[]; onChange: (rows: EditorRow[]) => void; contextId: string; disabled?: boolean }) {
  const { t } = useTranslation('tables')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  useEffect(() => { setSelected(new Set()); setQ(''); setPage(0) }, [contextId])
  useEffect(() => {
    useUiContextStore.getState().setSelectedItemIds([...selected].map(index => `${contextId}:${index}`))
    useUiContextStore.getState().setFilters({ table: contextId, q })
  }, [contextId, q, selected])
  const indices = useMemo(() => rows.flatMap((row, index) => columns.some(key => String(row[key] ?? '').toLocaleLowerCase().includes(q.toLocaleLowerCase())) ? [index] : []), [rows, columns, q])
  const total = Math.max(1, Math.ceil(indices.length / 50))
  const currentPage = Math.min(page, total - 1)
  const visible = indices.slice(currentPage * 50, currentPage * 50 + 50)
  const update = (index: number, key: string, value: string | boolean) => onChange(rows.map((row, position) => position === index ? { ...row, [key]: value } : row))
  return <div className="table-rows-editor">
    <div className="table-editor-toolbar"><div className="table-search"><Search size={15}/><Input aria-label={t('search')} placeholder={t('search')} value={q} onChange={e => { setQ(e.target.value); setPage(0) }}/></div><span>{t('rowCount', { count: rows.length })}</span><Button variant="outline" disabled={disabled} onClick={() => { onChange([...rows, {}]); setQ(''); setPage(Math.floor(rows.length / 50)) }}><Plus/>{t('addRow')}</Button><Button variant="outline" disabled={disabled || !selected.size} onClick={() => { onChange(rows.filter((_, index) => !selected.has(index))); setSelected(new Set()) }}><Trash2/>{t('removeRows')}</Button></div>
    <div className="table-scroll"><table className="editable-public-table"><thead><tr><th><input type="checkbox" aria-label={t('all')} checked={visible.length > 0 && visible.every(index => selected.has(index))} onChange={e => setSelected(previous => { const next = new Set(previous); visible.forEach(index => e.target.checked ? next.add(index) : next.delete(index)); return next })}/></th>{columns.map(key => <th key={key}>{t(`columns.${key}`)}</th>)}</tr></thead><tbody>{visible.map(index => <tr key={index} className={`${selected.has(index) ? 'selected' : ''} ${rows[index].is_valid === false ? 'invalid' : ''}`} title={rows[index].is_valid === false ? t('invalidPattern') : undefined}><td><input type="checkbox" aria-label={`${index + 1}`} checked={selected.has(index)} onChange={e => setSelected(previous => { const next = new Set(previous); if (e.target.checked) next.add(index); else next.delete(index); return next })}/></td>{columns.map(key => <td key={key}>{key === 'regex' ? <input type="checkbox" disabled={disabled} aria-label={`${t(`columns.${key}`)} ${index + 1}`} checked={rows[index][key] === true} onChange={e => update(index, key, e.target.checked)}/> : <textarea rows={2} disabled={disabled} aria-label={`${t(`columns.${key}`)} ${index + 1}`} value={String(rows[index][key] ?? '')} onChange={e => update(index, key, e.target.value)}/>}</td>)}</tr>)}</tbody></table>{!visible.length && <div className="table-empty">{t(rows.length ? 'noMatches' : 'empty')}</div>}</div>
    <footer className="table-editor-footer"><span>{t('selected', { count: selected.size })}</span><div><Button variant="ghost" disabled={!currentPage} onClick={() => setPage(currentPage - 1)}>{t('previous')}</Button><span>{t('page', { page: currentPage + 1, total })}</span><Button variant="ghost" disabled={currentPage >= total - 1} onClick={() => setPage(currentPage + 1)}>{t('next')}</Button></div></footer>
  </div>
}
