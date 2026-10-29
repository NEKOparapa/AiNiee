import { useTranslation } from 'react-i18next'

import { NumberField, SelectField, SettingsGroup } from './fields'
import { SettingsFrame } from './SettingsFrame'

export function TaskSettingsPage() {
  const { t } = useTranslation('settings')
  return <SettingsFrame page="task">{(config) => <>
    <SettingsGroup title={t('task.splitting')} description={t('task.splittingNote')}>
      <SelectField title={t('task.mode')} description={t('task.modeDescription')}
        value={config.lines_limit_switch ? 'lines' : 'tokens'}
        options={[{ value: 'lines', label: t('task.linesMode') }, { value: 'tokens', label: t('task.tokensMode') }]}
        patch={(value) => ({ lines_limit_switch: value === 'lines', tokens_limit_switch: value === 'tokens' })} />
      {config.lines_limit_switch
        ? <NumberField title={t('task.lines')} description={t('task.linesDescription')} value={config.lines_limit} patch={(value) => ({ lines_limit: value })} />
        : <NumberField title={t('task.tokens')} description={t('task.tokensDescription')} value={config.tokens_limit} patch={(value) => ({ tokens_limit: value })} />}
    </SettingsGroup>
    <SettingsGroup title={t('task.execution')} description={t('task.executionNote')}>
      <NumberField title={t('task.concurrency')} description={t('task.concurrencyDescription')}
        value={config.user_thread_counts} patch={(value) => ({ user_thread_counts: value })} />
      <NumberField title={t('task.timeout')} description={t('task.timeoutDescription')}
        value={config.request_timeout} patch={(value) => ({ request_timeout: value })} />
      <NumberField title={t('task.rounds')} description={t('task.roundsDescription')}
        value={config.round_limit} patch={(value) => ({ round_limit: value })} />
    </SettingsGroup>
  </>}</SettingsFrame>
}
