import { useTranslation } from 'react-i18next'

import { SelectField, SettingsGroup, SwitchField, TextField } from './fields'
import { SettingsFrame } from './SettingsFrame'

const openccPresets = ['s2t', 's2tw', 's2hk', 's2twp', 't2s', 't2tw', 't2hk', 't2jp', 'tw2s', 'tw2t', 'tw2sp', 'hk2s', 'hk2t', 'jp2t'] as const

export function OutputSettingsPage() {
  const { t } = useTranslation('settings')
  return <SettingsFrame page="output">{(config) => <>
    <SettingsGroup title={t('output.files')} description={t('output.filesNote')}>
      <TextField title={t('output.suffix')} description={t('output.suffixDescription')}
        value={config.output_filename_suffix} patch={(value) => ({ output_filename_suffix: value })} />
      <SwitchField title={t('output.autoPath')} description={t('output.autoPathDescription')}
        value={config.auto_set_output_path} patch={(value) => ({ auto_set_output_path: value })} />
      <TextField title={t('output.translationPath')} absolutePath disabled={config.auto_set_output_path}
        description={t(config.auto_set_output_path ? 'output.inactivePathDescription' : 'output.translationPathDescription')}
        value={config.label_output_path} patch={(value) => ({ label_output_path: value })} />
      <TextField title={t('output.polishPath')} absolutePath disabled={config.auto_set_output_path}
        description={t(config.auto_set_output_path ? 'output.inactivePathDescription' : 'output.polishPathDescription')}
        value={config.label_polish_output_path} patch={(value) => ({ label_polish_output_path: value })} />
    </SettingsGroup>
    <SettingsGroup title={t('output.format')}>
      <SelectField title={t('output.order')} description={t('output.orderDescription')}
        value={config.bilingual_text_order === 'original_first' ? 'source_first' : config.bilingual_text_order} options={[
          { value: 'source_first', label: t('output.sourceFirst') },
          { value: 'translation_first', label: t('output.translationFirst') },
        ]} patch={(value) => ({ bilingual_text_order: value })} />
      <SwitchField title={t('output.report')} description={t('output.reportDescription')}
        value={config.translation_result_check_switch} patch={(value) => ({ translation_result_check_switch: value })} />
      <SwitchField title={t('output.encoding')} description={t('output.encodingDescription')}
        value={config.keep_original_encoding} patch={(value) => ({ keep_original_encoding: value })} />
    </SettingsGroup>
    <SettingsGroup title={t('output.conversion')}>
      <SwitchField title={t('output.convert')} description={t('output.convertDescription')}
        value={config.response_conversion_toggle} patch={(value) => ({ response_conversion_toggle: value })} />
      <SelectField title={t('output.preset')} description={t('output.presetDescription')} disabled={!config.response_conversion_toggle}
        value={config.opencc_preset} options={openccPresets.map((value) => ({ value, label: value }))}
        patch={(value) => ({ opencc_preset: value })} />
    </SettingsGroup>
  </>}</SettingsFrame>
}
