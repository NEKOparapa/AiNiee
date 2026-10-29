import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, Copy, Pencil, Plus, Trash2 } from 'lucide-react'
import { type LibraryKind, type LibraryPrompt, useDeleteLibraryPrompt, usePromptLibrary, useSavePrompt } from '@/api/prompts'
import { useConnectionStore } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { PageState } from '@/components/common/PageState'
import { Button } from '@/components/ui/button'
import { PromptFeedback } from './PromptFeedback'
import { PromptEditDialog } from './PromptEditDialog'
import { EditorDialog } from '@/workspaces/tables/EditorDialog'
import './translations'
import '../tables/styles.css'
import './styles.css'

const kinds: LibraryKind[] = ['system', 'polish', 'analysis_basic', 'analysis_judgment']

export function PromptLibraryPage({ kind: fixedKind }: { kind?: LibraryKind }) {
  const { t } = useTranslation('prompts')
  const [tab, setTab] = useState<LibraryKind>('system')
  const kind = fixedKind ?? tab
  const query = usePromptLibrary(kind)
  const save = useSavePrompt(kind)
  const remove = useDeleteLibraryPrompt(kind)
  const connection = useConnectionStore(s => s.connection)
  const revision = useConnectionStore(s => s.revision)
  const [q, setQ] = useState('')
  const [previewId, setPreviewId] = useState<string | number | null>(null)
  const [editing, setEditing] = useState<{ prompt?: LibraryPrompt; copy?: boolean } | null>(null)
  const [deleting, setDeleting] = useState<LibraryPrompt | null>(null)
  useEffect(() => { setPreviewId(null); setQ(''); setEditing(null); setDeleting(null) }, [kind, revision])
  useEffect(() => { useUiContextStore.getState().setFilters({ promptKind: kind, q }) }, [kind, q])
  const pending = save.isPending || remove.isPending
  const library = query.data
  const entries = [...(library?.presets ?? []), ...(library?.custom ?? [])]
  const preview = entries.find(entry => String(entry.id) === String(previewId ?? library?.selected_id)) ?? entries[0]
  const name = (entry: (typeof entries)[number]) => entry.type === 'system' ? t(`presetNames.${entry.id}`, { defaultValue: entry.name }) : entry.name
  const matches = (entry: (typeof entries)[number]) => `${name(entry)} ${entry.content}`.toLocaleLowerCase().includes(q.toLocaleLowerCase())
  return <div className="workspace prompt-workspace"><header className="page-heading"><div><h1>{t(fixedKind ?? 'library')}</h1><p>{t('subtitle')}</p></div>{!fixedKind && <label className="table-actions">{t('taskKind')}<select aria-label={t('taskKind')} disabled={pending} value={kind} onChange={e => setTab(e.target.value as LibraryKind)}>{kinds.map(value => <option key={value} value={value}>{t(value)}</option>)}</select></label>}<Button disabled={!connection || pending || query.isPending || query.isError} onClick={() => setEditing({})}><Plus/>{t('new')}</Button></header>
    {!connection ? <PageState disconnected/> : <><PromptFeedback loading={query.isPending} error={query.error} retry={() => void query.refetch()}/><PromptFeedback error={save.error ?? remove.error}/>{library && <div className="prompt-library-grid"><section className="prompt-card-list"><input className="prompt-search" value={q} onChange={e => setQ(e.target.value)} placeholder={t('search')} aria-label={t('search')}/>{(['presets', 'custom'] as const).map(group => <div key={group}><h2>{t(group)}</h2><div className="prompt-card-list">{library[group].filter(matches).map(entry => <button className="prompt-card" key={entry.id} aria-label={name(entry)} aria-pressed={String(preview?.id) === String(entry.id)} onClick={() => setPreviewId(entry.id)}><strong>{name(entry)}</strong>{String(library.selected_id) === String(entry.id) && <small>{t('selected')}</small>}</button>)}{!library[group].filter(matches).length && <p className="prompt-preview-note">{t(q ? 'noMatches' : 'empty')}</p>}</div></div>)}</section>{preview && <section className="prompt-preview"><header><h2>{name(preview)}</h2><Button variant="outline" disabled={pending} onClick={() => setEditing({ prompt: preview, copy: true })}><Copy/>{t('copy')}</Button>{preview.type === 'user' && <><Button variant="outline" disabled={pending} onClick={() => setEditing({ prompt: preview })}><Pencil/>{t('edit')}</Button><Button variant="ghost" disabled={pending} onClick={() => setDeleting(preview)}><Trash2/>{t('remove')}</Button></>}<Button disabled={pending || String(library.selected_id) === String(preview.id)} onClick={() => save.mutate({ selected_id: preview.id }, { onSuccess: () => void query.refetch() })}><Check/>{t(String(library.selected_id) === String(preview.id) ? 'selected' : 'select')}</Button></header>{kind.startsWith('analysis_') && <p className="prompt-preview-note">{t('stageHint')}</p>}<pre>{preview.content}</pre>{preview.type === 'system' && <p className="prompt-preview-note">{t('presetHint')}</p>}</section>}</div>}</>}
    {editing && <PromptEditDialog kind={kind} {...editing} onClose={() => { setEditing(null); setPreviewId(null) }}/>}
    {deleting && <EditorDialog pending={remove.isPending} title={t('remove')} onClose={() => setDeleting(null)}><p>{t('removeConfirm', { name: name(deleting) })}</p><PromptFeedback error={remove.error}/><footer><Button variant="outline" disabled={remove.isPending} onClick={() => setDeleting(null)}>{t('cancel')}</Button><Button variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate(String(deleting.id), { onSuccess: () => { setDeleting(null); setPreviewId(null) } })}>{t('remove')}</Button></footer></EditorDialog>}
  </div>
}
