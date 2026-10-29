import { useEffect, useState } from 'react'
import { Check, LoaderCircle, Monitor, Moon, Sun } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useConfig, usePatchConfig } from '@/api/config'
import type { components } from '@/api/generated/schema'
import { Button } from '@/components/ui/button'
import { SettingCard } from '@/components/common/SettingCard'
import { PageHeading } from '@/components/common/PageHeading'
import { PageState } from '@/components/common/PageState'
import { useConnectionStore } from '@/stores/connection'

export function AppearancePage({ openConnection }: { openConnection: () => void }) {
  const { t } = useTranslation()
  const query = useConfig()
  const mutation = usePatchConfig()
  const connection = useConnectionStore(state => state.connection)
  const [color, setColor] = useState('#808b9d')
  const [lastPatch, setLastPatch] = useState<components['schemas']['ConfigPatch']>({})
  useEffect(() => { if (query.data) setColor(query.data.accent_color) }, [query.data?.accent_color])
  const save = (patch: components['schemas']['ConfigPatch']) => { setLastPatch(patch); mutation.mutate(patch) }
  return <div className="workspace"><PageHeading title={t('appearance.title')} subtitle={t('appearance.subtitle')}/>{!connection ? <PageState disconnected/> : query.isPending ? <PageState/> : query.isError || !query.data ? <PageState error retry={() => void query.refetch()}/> : <><div className="section-heading section-inline"><h2>{t('appearance.heading')}</h2><span className="save-state" role="status">{mutation.isPending ? <><LoaderCircle size={13} className="animate-spin"/>{t('common.saving')}</> : mutation.isSuccess ? <><Check size={13}/>{t('common.saved')}</> : null}</span></div>{mutation.isError && <div className="inline-error" role="alert"><span>{t('common.error')}</span><Button variant="outline" size="sm" onClick={() => mutation.mutate(lastPatch)}>{t('common.retry')}</Button></div>}<div className="settings-cards"><SettingCard title={t('appearance.theme')} description={t('appearance.themeDetail')}><div className="theme-options">{([['light', Sun], ['dark', Moon], ['auto', Monitor]] as const).map(([value, Icon]) => <button key={value} className={query.data.theme === value ? 'selected' : ''} disabled={mutation.isPending} aria-pressed={query.data.theme === value} onClick={() => save({ theme: value })}><Icon size={17}/>{t(`appearance.${value}`)}</button>)}</div></SettingCard><SettingCard title={t('appearance.accent')} description={t('appearance.accentDetail')}><div className="accent-control"><input type="color" value={color} onChange={event => setColor(event.target.value)} aria-label={t('appearance.accent')} disabled={mutation.isPending}/><span>{color.toUpperCase()}</span><Button variant="outline" size="sm" disabled={mutation.isPending || color === query.data.accent_color} onClick={() => save({ accent_color: color })}>{t('common.save')}</Button></div></SettingCard><SettingCard title={t('appearance.language')} description={t('appearance.languageDetail')}><select className="select-control" aria-label={t('appearance.language')} value={query.data.interface_language_setting === 'English' ? 'English' : '简中'} disabled={mutation.isPending} onChange={event => save({ interface_language_setting: event.target.value })}><option value="简中">{t('appearance.chinese')}</option><option value="English">{t('appearance.english')}</option></select></SettingCard></div></>}<div className="section-heading"><h2>{t('appearance.connectionHeading')}</h2></div><SettingCard title={connection?.api ?? t('connection.disconnected')} description={t('appearance.connectionDetail')}><Button variant="outline" onClick={openConnection}>{t('connection.change')}</Button></SettingCard></div>
}
