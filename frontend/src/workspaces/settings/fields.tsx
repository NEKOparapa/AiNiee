import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Check, LoaderCircle, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { usePatchConfig } from '@/api/config'
import type { ConfigPatch } from '@/api/types'
import { SettingCard } from '@/components/common/SettingCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'

type FieldText = { title: string; description: string; disabled?: boolean }

export function useFieldSave() {
  const mutation = usePatchConfig()
  const lastPatch = useRef<ConfigPatch | null>(null)
  const save = async (patch: ConfigPatch) => {
    lastPatch.current = patch
    try {
      await mutation.mutateAsync(patch)
    } catch {
      // The field keeps the failed draft and exposes a localized retry action.
    }
  }
  return {
    mutation,
    save,
    retry: () => { if (lastPatch.current) void save(lastPatch.current) },
  }
}

export function SaveFeedback({ state }: { state: ReturnType<typeof useFieldSave> }) {
  const { t } = useTranslation('settings')
  return <div className="setting-feedback" aria-live="polite">
    {state.mutation.isPending && <span><LoaderCircle size={13} className="animate-spin" />{t('saving')}</span>}
    {state.mutation.isSuccess && <span className="setting-saved"><Check size={13} />{t('saved')}</span>}
    {state.mutation.isError && <div className="setting-save-error" role="alert">
      <span>{t('saveError')}</span>
      <Button size="sm" variant="ghost" onClick={state.retry}><RefreshCw size={13} />{t('retry')}</Button>
    </div>}
  </div>
}

export function SwitchField({ title, description, value, patch, disabled }: FieldText & {
  value: boolean
  patch: (value: boolean) => ConfigPatch
}) {
  const state = useFieldSave()
  const id = useId()
  return <SettingCard title={title} description={description}>
    <div className="setting-field-control">
      <Switch id={id} aria-label={title} checked={value} disabled={disabled || state.mutation.isPending}
        onCheckedChange={(checked) => { void state.save(patch(checked)) }} />
      <SaveFeedback state={state} />
    </div>
  </SettingCard>
}

export function SelectField<Value extends string>({ title, description, value, options, patch, disabled }: FieldText & {
  value: Value
  options: ReadonlyArray<{ value: Value; label: string }>
  patch: (value: Value) => ConfigPatch
}) {
  const state = useFieldSave()
  const { t } = useTranslation('settings')
  return <SettingCard title={title} description={description}>
    <div className="setting-field-control">
      <select className="select-control" aria-label={title} value={value}
        disabled={disabled || state.mutation.isPending}
        onChange={(event) => { void state.save(patch(event.target.value as Value)) }}>
        {!options.some((option) => option.value === value) && <option value={value}>{t('unknownValue', { value })}</option>}
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <SaveFeedback state={state} />
    </div>
  </SettingCard>
}

export function TextField({ title, description, value, patch, disabled, absolutePath = false }: FieldText & {
  value: string
  patch: (value: string) => ConfigPatch
  absolutePath?: boolean
}) {
  const state = useFieldSave()
  const { t } = useTranslation('settings')
  const [draft, setDraft] = useState(value)
  const [invalid, setInvalid] = useState(false)
  const errorId = useId()
  useEffect(() => { setDraft(value) }, [value])
  const commit = () => {
    const next = draft.trim()
    if (next === value) return
    if (absolutePath && !/^(?:[a-zA-Z]:[\\/]|\\\\|\/)/.test(next)) {
      setInvalid(true)
      return
    }
    setInvalid(false)
    void state.save(patch(next))
  }
  return <SettingCard title={title} description={description}>
    <div className={`setting-field-control ${absolutePath ? 'setting-path-control' : ''}`}>
      <Input aria-label={title} value={draft} disabled={disabled || state.mutation.isPending}
        aria-invalid={invalid} aria-describedby={invalid ? errorId : undefined}
        onChange={(event) => { setDraft(event.target.value); setInvalid(false); state.mutation.reset() }}
        onBlur={commit} onKeyDown={(event) => {
          if (event.key === 'Enter') event.currentTarget.blur()
          if (event.key === 'Escape') { setDraft(value); setInvalid(false) }
        }} />
      {invalid && <span className="setting-validation-error" id={errorId} role="alert">{t('pathError')}</span>}
      <SaveFeedback state={state} />
    </div>
  </SettingCard>
}

export function NumberField({ title, description, value, patch, disabled, min = 0, max = 9999999 }: FieldText & {
  value: number
  patch: (value: number) => ConfigPatch
  min?: number
  max?: number
}) {
  const state = useFieldSave()
  const { t } = useTranslation('settings')
  const [draft, setDraft] = useState(String(value))
  const [invalid, setInvalid] = useState(false)
  const errorId = useId()
  useEffect(() => { setDraft(String(value)) }, [value])
  const commit = () => {
    const next = Number(draft)
    if (!draft.trim() || !Number.isInteger(next) || next < min || next > max) {
      setInvalid(true)
      return
    }
    setInvalid(false)
    if (next !== value) void state.save(patch(next))
  }
  return <SettingCard title={title} description={description}>
    <div className="setting-field-control setting-number-control">
      <Input type="number" inputMode="numeric" min={min} max={max} step={1}
        aria-label={title} value={draft} disabled={disabled || state.mutation.isPending}
        aria-invalid={invalid} aria-describedby={invalid ? errorId : undefined}
        onChange={(event) => { setDraft(event.target.value); setInvalid(false); state.mutation.reset() }}
        onBlur={commit} onKeyDown={(event) => {
          if (event.key === 'Enter') event.currentTarget.blur()
          if (event.key === 'Escape') { setDraft(String(value)); setInvalid(false) }
        }} />
      {invalid && <span className="setting-validation-error" id={errorId} role="alert">{t('numberError', { min, max })}</span>}
      <SaveFeedback state={state} />
    </div>
  </SettingCard>
}

export function SettingsGroup({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  const id = useId()
  return <section className="settings-group" aria-labelledby={id}>
    <div className="settings-group-heading"><h2 id={id}>{title}</h2>{description && <p>{description}</p>}</div>
    <div className="settings-cards">{children}</div>
  </section>
}
