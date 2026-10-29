import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { type LibraryKind, type LibraryPrompt, useSaveLibraryPrompt } from '@/api/prompts'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { EditorDialog } from '@/workspaces/tables/EditorDialog'
import { PromptFeedback } from './PromptFeedback'

export function PromptEditDialog({ kind, prompt, copy = false, onClose }: { kind: LibraryKind; prompt?: LibraryPrompt; copy?: boolean; onClose: () => void }) {
  const { t } = useTranslation('prompts')
  const [name, setName] = useState(prompt?.name ?? '')
  const [content, setContent] = useState(prompt?.content ?? '')
  const save = useSaveLibraryPrompt(kind)
  return <EditorDialog title={t(prompt && !copy ? 'edit' : 'new')} onClose={onClose}><form className="prompt-edit-form" onSubmit={e => { e.preventDefault(); save.mutate({ ...(prompt ?? {}), id: prompt && !copy ? String(prompt.id) : undefined, name, content, select: true }, { onSuccess: onClose }) }}><label>{t('name')}<Input autoFocus required maxLength={200} value={name} disabled={save.isPending} onChange={e => setName(e.target.value)}/></label><label>{t('content')}<textarea required value={content} disabled={save.isPending} onChange={e => setContent(e.target.value)}/></label><PromptFeedback error={save.error}/><footer><Button type="button" variant="outline" onClick={onClose}>{t('cancel')}</Button><Button type="submit" disabled={save.isPending || !name.trim() || !content.trim()}>{t(save.isPending ? 'saving' : 'save')}</Button></footer></form></EditorDialog>
}
