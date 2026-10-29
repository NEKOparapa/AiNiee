import { useEffect, useId, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

export function PlatformDialog({ title, children, onClose, wide = false }: {
  title: string; children: ReactNode; onClose: () => void; wide?: boolean
}) {
  const { t } = useTranslation('platforms')
  const ref = useRef<HTMLDialogElement>(null)
  const id = useId()
  useEffect(() => { ref.current?.showModal() }, [])
  return <dialog ref={ref} className={`platform-dialog${wide ? ' platform-dialog-wide' : ''}`} aria-labelledby={id} onCancel={event => { event.preventDefault(); onClose() }}>
    <header className="platform-dialog-header"><h2 id={id}>{title}</h2>
      <Button type="button" size="icon" variant="ghost" aria-label={t('close')} onClick={onClose}><X size={18}/></Button>
    </header>
    {children}
  </dialog>
}
