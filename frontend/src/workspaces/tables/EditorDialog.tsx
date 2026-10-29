import { useEffect, useId, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import './translations'

export function EditorDialog({ title, children, onClose, pending = false }: { title: string; children: ReactNode; onClose: () => void; pending?: boolean }) {
  const { t } = useTranslation('tables')
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => { ref.current?.showModal() }, [])
  return <dialog ref={ref} className="editor-native-dialog" aria-labelledby={id} aria-busy={pending} onCancel={event => { event.preventDefault(); if (!pending) onClose() }}><div className="table-dialog"><header><h2 id={id}>{title}</h2><Button size="sm" variant="ghost" disabled={pending} onClick={onClose}>{t('cancel')}</Button></header>{children}</div></dialog>
}
