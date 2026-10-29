import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Save } from 'lucide-react'
import { type PromptDocument, usePrompt, useSavePrompt } from '@/api/prompts'
import { useConnectionStore } from '@/stores/connection'
import { Button } from '@/components/ui/button'
import { PageState } from '@/components/common/PageState'
import { TableRowsEditor, tableColumns } from '@/workspaces/tables/TableRowsEditor'
import { PromptFeedback } from './PromptFeedback'
import './translations'
import './styles.css'

export function TextPromptPage({ kind }: { kind: 'world' | 'style' | 'examples' | 'characters' }) {
  const { t } = useTranslation('prompts')
  const connection = useConnectionStore(s => s.connection)
  const revision = useConnectionStore(s => s.revision)
  const query = usePrompt(kind)
  const save = useSavePrompt(kind)
  const [draft, setDraft] = useState<PromptDocument | null>(null)
  useEffect(() => { setDraft(null) }, [kind, revision])
  const value = draft ?? query.data
  const modify = (change: Partial<PromptDocument>) => value && setDraft({ ...value, ...change })
  return <div className="workspace prompt-workspace"><header className="page-heading"><div><h1>{t(kind)}</h1><p>{t('textSubtitle')}</p></div><div className="table-actions">{draft ? <span className="table-save-status">{t('dirty')}</span> : save.isSuccess && <span role="status">{t('saved')}</span>}<Button variant="outline" disabled={!draft || save.isPending} onClick={() => setDraft(null)}>{t('reset')}</Button><Button disabled={!value || !connection || save.isPending} onClick={() => value && save.mutate(value, { onSuccess: () => { if (useConnectionStore.getState().revision === revision) setDraft(null) } })}><Save/>{t(save.isPending ? 'saving' : 'save')}</Button></div></header>
    {!connection ? <PageState disconnected/> : <><PromptFeedback loading={query.isPending} error={query.error} retry={() => void query.refetch()}/><PromptFeedback error={save.error}/>{value && <><label className="prompt-enabled-card"><span><strong>{t('enabled')}</strong><small>{t('textSubtitle')}</small></span><input type="checkbox" checked={value.enabled ?? false} disabled={save.isPending} onChange={e => modify({ enabled: e.target.checked })}/></label>{kind === 'examples' || kind === 'characters' ? <TableRowsEditor contextId={`prompts:${kind}:${revision}`} columns={tableColumns[kind]} rows={value.rows ?? []} onChange={rows => modify({ rows })} disabled={save.isPending}/> : <textarea className="prompt-text-editor" aria-label={t('content')} spellCheck={false} disabled={save.isPending} value={value.content ?? ''} onChange={e => modify({ content: e.target.value })}/>}</>}</>}
  </div>
}
