import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { LoaderCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { platformErrorCode, useCreatePlatform, useUpdatePlatform, type Platform, type PlatformUpdate } from '@/api/platforms'
import { PlatformDialog } from './PlatformDialog'

type TextField = 'name' | 'api_url' | 'api_key' | 'model' | 'region' | 'access_key' | 'secret_key'
type NumberField = 'rpm_limit' | 'temperature' | 'thinking_budget'
type SwitchField = 'auto_complete' | 'think_switch' | 'tls_switch'
type SelectField = 'api_format' | 'think_depth' | 'thinking_level'

export function PlatformForm({ platform, presets, onClose, onSaved }: {
  platform?: Platform; presets: Platform[]; onClose: () => void; onSaved: () => void
}) {
  const { t } = useTranslation('platforms')
  const formId = useId()
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const [presetId, setPresetId] = useState(presets.find(item => item.id === 'custom')?.id ?? presets[0]?.id ?? '')
  const source = platform ?? presets.find(item => item.id === presetId)
  const [changes, setChanges] = useState<PlatformUpdate>({})
  const [jsonText, setJsonText] = useState<Partial<Record<'extra_body' | 'extra_headers', string>>>({})
  const [numberText, setNumberText] = useState<Partial<Record<NumberField, string>>>({})
  const [tab, setTab] = useState('basic')
  const [validationError, setValidationError] = useState('')
  const create = useCreatePlatform()
  const update = useUpdatePlatform()
  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error
  if (!source) return null
  const draft = { ...source, ...changes }
  const fields = new Set(source.metadata.fields)
  const changed = <K extends keyof PlatformUpdate>(field: K, value: PlatformUpdate[K]) => {
    setChanges(previous => ({ ...previous, [field]: value }))
    setValidationError('')
  }
  const textField = (field: TextField, detail?: string) => <div className="platform-field" key={field}>
    <label htmlFor={`${formId}-${field}`}>{t(field)}</label>
    <Input id={`${formId}-${field}`} value={draft[field]} onChange={event => changed(field, event.target.value)}
      type={['api_key', 'access_key', 'secret_key'].includes(field) ? 'password' : 'text'}
      autoComplete="off" spellCheck={false} required={field === 'name' || field === 'model'}
      list={field === 'model' ? `${formId}-models` : field === 'region' ? `${formId}-regions` : undefined}/>
    {detail && <p>{t(detail)}</p>}
  </div>
  const numberField = (field: NumberField, min: number, max: number, step: number, detail: string) => <div className="platform-field" key={field}>
    <label htmlFor={`${formId}-${field}`}>{t(field)}</label>
    <Input id={`${formId}-${field}`} type="number" min={min} max={max} step={step} value={numberText[field] ?? draft[field]}
      onChange={event => { setNumberText(previous => ({ ...previous, [field]: event.target.value })); setValidationError('') }}/>
    <p>{t(detail)}</p>
  </div>
  const switchField = (field: SwitchField, detail: string) => <div className="platform-field platform-field-full platform-switch-row" key={field}>
    <div><label htmlFor={`${formId}-${field}`}>{t(field)}</label><p>{t(detail)}</p></div>
    <Switch id={`${formId}-${field}`} checked={draft[field]} onCheckedChange={checked => changed(field, checked)}/>
  </div>
  const selectField = (field: SelectField, options: string[]) => <div className="platform-field" key={field}>
    <label htmlFor={`${formId}-${field}`}>{t(field)}</label>
    <select id={`${formId}-${field}`} className="select-control" value={draft[field]}
      onChange={event => changed(field, event.target.value as PlatformUpdate[typeof field])}>
      {[...new Set([draft[field], ...options])].map(option => <option key={option} value={option}>{option}</option>)}
    </select>
  </div>
  const jsonField = (field: 'extra_body' | 'extra_headers', detail: string) => <div className="platform-field platform-field-full" key={field}>
    <label htmlFor={`${formId}-${field}`}>{t(field)}</label>
    <textarea id={`${formId}-${field}`} rows={4} value={jsonText[field] ?? JSON.stringify(source[field], null, 2)}
      spellCheck={false} onChange={event => { setJsonText(previous => ({ ...previous, [field]: event.target.value })); setValidationError('') }}/>
    <p>{t(detail)}</p>
  </div>
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setValidationError('')
    const patch = { ...changes }
    for (const field of ['rpm_limit', 'temperature', 'thinking_budget'] as const) {
      if (numberText[field] === undefined) continue
      const value = Number(numberText[field])
      const valid = numberText[field]?.trim() && Number.isFinite(value) && (
        field === 'temperature' ? value >= 0 && value <= 2 :
          Number.isInteger(value) && (field === 'rpm_limit' ? value >= 0 && value <= 9999999 : value >= -1 && value <= 32768)
      )
      if (!valid) { setValidationError('numberInvalid'); setTab('advanced'); return }
      patch[field] = value
    }
    try {
      for (const field of ['extra_body', 'extra_headers'] as const) {
        if (jsonText[field] === undefined) continue
        const value: unknown = jsonText[field]?.trim() ? JSON.parse(jsonText[field]!) : {}
        if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new Error('invalid JSON')
        if (field === 'extra_headers') {
          if (Object.values(value).some(item => typeof item !== 'string')) throw new Error('invalid headers')
          patch.extra_headers = value as PlatformUpdate['extra_headers']
        } else patch.extra_body = value as PlatformUpdate['extra_body']
      }
    } catch { setValidationError('jsonInvalid'); setTab('advanced'); return }
    if (!draft.name.trim() || !draft.model.trim()) { setValidationError('required'); setTab('basic'); return }
    if (patch.name !== undefined) patch.name = patch.name.trim()
    if (patch.model !== undefined) patch.model = patch.model.trim()
    try {
      if (platform) await update.mutateAsync({ id: platform.id, changes: patch })
      else await create.mutateAsync({ ...patch, preset_id: source.id, name: draft.name.trim(), model: draft.model.trim() })
      if (mounted.current) onSaved()
    } catch { /* The localized mutation error is rendered below. */ }
  }
  return <PlatformDialog title={t(platform ? 'edit' : 'add')} onClose={onClose} wide>
    <form noValidate onSubmit={event => { void submit(event) }}>
      <div className="platform-tabs" role="tablist" aria-label={t('edit')}>
        {(['basic', 'advanced'] as const).map(value => <button type="button" role="tab" aria-selected={tab === value} key={value} onClick={() => setTab(value)}>{t(value)}</button>)}
      </div>
      <div className="platform-dialog-body">
        <fieldset disabled={pending} className="platform-form-fieldset">
          <div className="platform-form-grid" hidden={tab !== 'basic'}>
            {!platform && <div className="platform-field platform-field-full"><label htmlFor={`${formId}-preset`}>{t('preset')}</label>
              <select id={`${formId}-preset`} className="select-control" value={presetId} onChange={event => {
                setPresetId(event.target.value); setChanges({}); setJsonText({}); setNumberText({}); setValidationError(''); create.reset()
              }}>{presets.map(preset => <option key={preset.id} value={preset.id}>{preset.name}</option>)}</select>
            </div>}
            {textField('name')}
            {textField('model', 'modelDetail')}
            {fields.has('api_url') && textField('api_url')}
            {fields.has('api_format') && selectField('api_format', source.format_datas)}
            {fields.has('api_key') && textField('api_key', 'keyDetail')}
            {fields.has('region') && textField('region')}
            {fields.has('access_key') && textField('access_key')}
            {fields.has('secret_key') && textField('secret_key')}
            {fields.has('auto_complete') && switchField('auto_complete', 'autoCompleteDetail')}
            <div className="platform-field platform-field-full"><label htmlFor={`${formId}-model-list`}>{t('model_datas')}</label>
              <textarea id={`${formId}-model-list`} rows={3} value={draft.model_datas.join('\n')} spellCheck={false}
                onChange={event => changed('model_datas', event.target.value.split('\n'))}/><p>{t('modelListDetail')}</p>
            </div>
          </div>
          <div className="platform-form-grid" hidden={tab !== 'advanced'}>
            {fields.has('rpm_limit') && numberField('rpm_limit', 0, 9999999, 1, 'rpmDetail')}
            {fields.has('temperature') && numberField('temperature', 0, 2, 0.01, 'temperatureDetail')}
            {fields.has('think_switch') && switchField('think_switch', 'thinkDetail')}
            {fields.has('think_depth') && selectField('think_depth', source.metadata.think_depth_options)}
            {fields.has('thinking_budget') && numberField('thinking_budget', -1, 32768, 1, 'budgetDetail')}
            {fields.has('thinking_level') && selectField('thinking_level', source.metadata.thinking_level_options)}
            {fields.has('tls_switch') && switchField('tls_switch', 'tlsDetail')}
            {fields.has('extra_body') && jsonField('extra_body', 'bodyDetail')}
            {fields.has('extra_headers') && jsonField('extra_headers', 'headersDetail')}
          </div>
        </fieldset>
        <datalist id={`${formId}-models`}>{source.model_datas.map(model => <option key={model} value={model}/>)}</datalist>
        <datalist id={`${formId}-regions`}>{source.region_datas.map(region => <option key={region} value={region}/>)}</datalist>
        {validationError && <p role="alert" className="platform-error">{t(validationError)}</p>}
        {error && <p role="alert" className="platform-error">{t(`errors.${platformErrorCode(error)}`, { defaultValue: t('errors.request_failed') })}</p>}
      </div>
      <footer className="platform-dialog-footer"><Button type="button" variant="outline" onClick={onClose}>{t('cancel')}</Button>
        <Button type="submit" disabled={pending}>{pending && <LoaderCircle size={15} className="animate-spin"/>}{t(pending ? 'saving' : 'save')}</Button>
      </footer>
    </form>
  </PlatformDialog>
}
