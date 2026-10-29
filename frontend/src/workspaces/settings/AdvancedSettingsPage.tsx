import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { ApiConfig } from '@/api/types'
import { SettingCard } from '@/components/common/SettingCard'
import { Switch } from '@/components/ui/switch'

import { NumberField, SaveFeedback, SettingsGroup, SwitchField, useFieldSave } from './fields'
import { SettingsFrame } from './SettingsFrame'

const tabs = ['extraction', 'translation', 'polishing'] as const

function ResponseChecks({ config }: { config: ApiConfig }) {
  const { t } = useTranslation('settings')
  const state = useFieldSave()
  const checks = [
    ['return_to_original_text_check', 'originalCheck'],
    ['residual_original_text_check', 'residualCheck'],
    ['newline_character_count_check', 'newlineCheck'],
    ['reply_format_check', 'formatCheck'],
  ] as const
  return <SettingsGroup title={t('advanced.checks')} description={t('advanced.checksDescription')}>
    {checks.map(([key, text]) => <SettingCard key={key} title={t(`advanced.${text}`)} description={t(`advanced.${text}Description`)}>
      <Switch aria-label={t(`advanced.${text}`)} checked={config.response_check_switch[key]} disabled={state.mutation.isPending}
        onCheckedChange={(checked) => { void state.save({ response_check_switch: { ...config.response_check_switch, [key]: checked } }) }} />
    </SettingCard>)}
    <SaveFeedback state={state} />
  </SettingsGroup>
}

export function AdvancedSettingsPage() {
  const { t } = useTranslation('settings')
  const [tab, setTab] = useState<(typeof tabs)[number]>('translation')
  const id = useId()
  return <SettingsFrame page="advanced">{(config) => <>
    <div className="settings-tabs" role="tablist" aria-label={t('advanced.title')}>
      {tabs.map((key) => <button key={key} role="tab" type="button" id={`${id}-${key}`}
        aria-selected={tab === key} aria-controls={`${id}-panel`} tabIndex={tab === key ? 0 : -1}
        onClick={() => setTab(key)} onKeyDown={(event) => {
          const direction = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
          if (direction) {
            event.preventDefault()
            const next = tabs[(tabs.indexOf(key) + direction + tabs.length) % tabs.length]
            setTab(next)
            document.getElementById(`${id}-${next}`)?.focus()
          }
        }}>{t(`advanced.${key}`)}</button>)}
    </div>
    <div role="tabpanel" id={`${id}-panel`} aria-labelledby={`${id}-${tab}`}>
      {tab === 'extraction' && <SettingsGroup title={t('advanced.extraction')}>
        <NumberField title={t('advanced.extractTokens')} description={t('advanced.extractTokensDescription')} min={1}
          value={config.extract_task_token_limit} patch={(value) => ({ extract_task_token_limit: value })} />
        <SwitchField title={t('advanced.nonTranslate')} description={t('advanced.nonTranslateDescription')}
          value={config.auto_extract_non_translate_switch} patch={(value) => ({ auto_extract_non_translate_switch: value })} />
        <SwitchField title={t('advanced.mergeNames')} description={t('advanced.mergeNamesDescription')}
          value={config.extract_short_name_merge_switch} patch={(value) => ({ extract_short_name_merge_switch: value })} />
      </SettingsGroup>}
      {tab === 'translation' && <>
        <SettingsGroup title={t('advanced.context')}>
          <NumberField title={t('advanced.contextLines')} description={t('advanced.contextLinesDescription')}
            value={config.pre_line_counts} patch={(value) => ({ pre_line_counts: value })} />
        </SettingsGroup>
        <SettingsGroup title={t('advanced.processing')}>
          <SwitchField title={t('advanced.preprocess')} description={t('advanced.preprocessDescription')}
            value={config.auto_process_text_code_segment} patch={(value) => ({ auto_process_text_code_segment: value })} />
          <SwitchField title={t('advanced.symbols')} description={t('advanced.symbolsDescription')}
            value={config.text_symbol_repair_switch} patch={(value) => ({ text_symbol_repair_switch: value })} />
          <SwitchField title={t('advanced.languageFilter')} description={t('advanced.languageFilterDescription')}
            value={config.language_filter_switch} patch={(value) => ({ language_filter_switch: value })} />
          <SwitchField title={t('advanced.codeFilter')} description={t('advanced.codeFilterDescription')}
            value={config.code_filter_switch} patch={(value) => ({ code_filter_switch: value })} />
          <SwitchField title={t('advanced.examples')} description={t('advanced.examplesDescription')}
            value={config.few_shot_and_example_switch} patch={(value) => ({ few_shot_and_example_switch: value })} />
        </SettingsGroup>
        <ResponseChecks config={config} />
      </>}
      {tab === 'polishing' && <SettingsGroup title={t('advanced.polishing')}>
        <NumberField title={t('advanced.polishContext')} description={t('advanced.polishContextDescription')}
          value={config.polishing_pre_line_counts} patch={(value) => ({ polishing_pre_line_counts: value })} />
      </SettingsGroup>}
    </div>
  </>}</SettingsFrame>
}
