import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, LoaderCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { platformErrorCode, useSaveBindings, type Platform, type PlatformBindings } from '@/api/platforms'

export function BindingsCard({ platforms, bindings }: { platforms: Platform[]; bindings: PlatformBindings }) {
  const { t } = useTranslation('platforms')
  const [draft, setDraft] = useState(bindings)
  const id = useId()
  const mutation = useSaveBindings()
  const dirty = JSON.stringify(draft) !== JSON.stringify(bindings)
  return <section className="platform-bindings" aria-labelledby={`${id}-title`}>
    <div className="platform-bindings-header"><div><h2 id={`${id}-title`}>{t('bindings')}</h2><p>{t('bindingsDetail')}</p></div>
      <Button variant="outline" disabled={!dirty || mutation.isPending} onClick={() => mutation.mutate(draft)}>
        {mutation.isPending ? <LoaderCircle size={15} className="animate-spin"/> : <Check size={15}/>}{t(mutation.isPending ? 'saving' : 'save')}
      </Button>
    </div>
    <div className="platform-bindings-grid">
      {(['active', 'extract', 'translate', 'polish', 'proofread'] as const).map(role => <div key={role} className={`platform-field${role === 'active' ? ' platform-field-full' : ''}`}>
        <label htmlFor={`${id}-${role}`}>{t(role)}</label>
        <select id={`${id}-${role}`} className="select-control" value={draft[role] ?? ''} disabled={mutation.isPending}
          onChange={event => { setDraft(previous => ({ ...previous, [role]: event.target.value || null })); mutation.reset() }}>
          <option value="">{t(role === 'active' ? 'none' : 'follow')}</option>
          {platforms.map(platform => <option value={platform.id} key={platform.id}>{platform.name}</option>)}
        </select>
      </div>)}
    </div>
    {mutation.isError && <p className="platform-error" role="alert">{t(`errors.${platformErrorCode(mutation.error)}`, { defaultValue: t('errors.request_failed') })}</p>}
    {mutation.isSuccess && <p className="platform-notice" role="status">{t('bindingsSaved')}</p>}
  </section>
}
