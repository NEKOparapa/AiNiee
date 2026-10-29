import { useEffect, useId, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import './translations'

export function EditorDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const { t } = useTranslation('tables')
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => { ref.current?.showModal() }, [])
  return <dialog ref={ref} className="editor-native-dialog" aria-labelledby={id} onCancel={event => { event.preventDefault(); onClose() }}><div className="table-dialog"><header><h2 id={id}>{title}</h2><Button size="sm" variant="ghost" onClick={onClose}>{t('cancel')}</Button></header>{children}</div></dialog>
}
