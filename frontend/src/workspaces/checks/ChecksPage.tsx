import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, FileCheck2, LoaderCircle, ShieldCheck } from 'lucide-react'
import { useRunCheck, type CheckResult, type RuleOptions, type LanguageOptions, type TerminologyOptions, type CheckIssue } from '@/api/checks'
import { ApiError } from '@/api/client'
import { useConfig } from '@/api/config'
import { useCurrentProject } from '@/api/projects'
import { useConnectionStore } from '@/stores/connection'
import { useUiContextStore } from '@/stores/ui-context'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageState } from '@/components/common/PageState'
import './translations'
import './styles.css'

const ruleNames = ['exclusion', 'auto_process', 'placeholder', 'number', 'example', 'newline', 'untranslated'] as const
const RESULT_PAGE_SIZE = 50

export function issueLocation(issue: CheckIssue) {
  return `/items?${new URLSearchParams({ file: issue.file, index: String(issue.index), page: String(Math.floor(issue.position / 100) + 1) })}`
}

export function ChecksPage() {
  const { t } = useTranslation('checks')
  const current = useCurrentProject()
  const projectId = current.data?.project?.project_id
  const config = useConfig()
  const connection = useConnectionStore(s => s.connection)
  const revision = useConnectionStore(s => s.revision)
  const mutation = useRunCheck()
  const [kind, setKind] = useState<CheckResult['kind']>('rule')
  const [rules, setRules] = useState<RuleOptions>({})
  const [language, setLanguage] = useState<LanguageOptions>({})
  const [terminology, setTerminology] = useState<TerminologyOptions>({})
  const [result, setResult] = useState<CheckResult | null>(null)
  const [page, setPage] = useState(1)
  const context = useRef({ projectId, revision })
  context.current = { projectId, revision }
  const reset = mutation.reset
  useEffect(() => { setResult(null); setPage(1); reset() }, [projectId, revision, reset])
  useEffect(() => {
    useUiContextStore.getState().setFilters({ kind })
    useUiContextStore.getState().setSelectedItemIds([])
  }, [kind])
  useEffect(() => {
    if (!config.data) return
    const saved = config.data
    setRules({ exclusion: saved.rule_check_exclusion, auto_process: saved.rule_check_auto_process, placeholder: saved.rule_check_placeholder, number: saved.rule_check_number, example: saved.rule_check_example, newline: saved.rule_check_newline, untranslated: saved.rule_check_untranslated })
    setLanguage({ mode: saved.check_lang_mode_text, chunk_size: saved.check_chunk_size, threshold: saved.check_threshold_ratio, exclude_non_translate: saved.check_exclude_non_translate })
    setTerminology({ case_sensitive: saved.prompt_dictionary_match_case_sensitive, whole_word: saved.prompt_dictionary_match_whole_word })
  }, [config.data])
  async function run() {
    const captured = { projectId, revision }
    setResult(null)
    try {
      const response = await mutation.mutateAsync(kind === 'rule' ? { kind, body: { rules } } : kind === 'language' ? { kind, body: language } : { kind, body: terminology })
      if (context.current.projectId === captured.projectId && context.current.revision === captured.revision && response.project_id === captured.projectId) { setResult(response); setPage(1) }
    } catch { /* Mutation state displays the safe API error. */ }
  }
  const error = mutation.error ?? config.error ?? current.error
  const errorCode = error instanceof ApiError ? error.code : 'fallback'
  const pages = Math.max(1, Math.ceil((result?.issues.length ?? 0) / RESULT_PAGE_SIZE))
  return <div className="workspace checks-workspace"><header className="page-heading"><div><h1>{t('title')}</h1><p>{t('description')}</p></div><span className="subtle-badge"><ShieldCheck size={14}/>{t('local')}</span></header>
    {!connection ? <PageState disconnected/> : current.isPending || config.isPending ? <PageState/> : current.isError || config.isError ? <PageState error retry={() => { void current.refetch(); void config.refetch() }}/> : !projectId ? <div className="checks-empty"><FileCheck2 size={36}/><p>{t('noProject')}</p><Button asChild><Link to="/">{t('openProject')}</Link></Button></div> : <>
      <div className="check-tabs" role="tablist">{(['rule', 'language', 'terminology'] as const).map(value => <button key={value} role="tab" aria-selected={kind === value} disabled={mutation.isPending} onClick={() => { setKind(value); setResult(null); reset() }}>{t(value)}</button>)}</div>
      <form className="check-options" onSubmit={event => { event.preventDefault(); void run() }}><h2>{t('options')}</h2><fieldset disabled={mutation.isPending || config.isError}>
        {kind === 'rule' && <div className="check-rule-grid">{ruleNames.map(name => <label key={name}><input type="checkbox" checked={rules[name] ?? true} onChange={event => setRules({ ...rules, [name]: event.target.checked })}/>{t(`rules.${name}`)}</label>)}</div>}
        {kind === 'language' && <><div className="check-language-grid"><label>{t('mode')}<select value={language.mode ?? 'judge'} onChange={event => setLanguage({ ...language, mode: event.target.value as 'judge' | 'report' })}><option value="judge">{t('judge')}</option><option value="report">{t('report')}</option></select></label><label>{t('chunkSize')}<Input type="number" required min={1} max={9999999} value={language.chunk_size ?? 20} onChange={event => setLanguage({ ...language, chunk_size: Number(event.target.value) })}/></label><label>{t('threshold')}<Input type="number" required min={0.01} max={1} step={0.01} value={language.threshold ?? 0.75} onChange={event => setLanguage({ ...language, threshold: Number(event.target.value) })}/></label></div><label className="check-checkbox"><input type="checkbox" checked={language.exclude_non_translate ?? true} onChange={event => setLanguage({ ...language, exclude_non_translate: event.target.checked })}/>{t('exclude')}</label><p>{t('languageNote')}</p></>}
        {kind === 'terminology' && <><div className="check-rule-grid"><label><input type="checkbox" checked={terminology.case_sensitive ?? false} onChange={event => setTerminology({ ...terminology, case_sensitive: event.target.checked })}/>{t('caseSensitive')}</label><label><input type="checkbox" checked={terminology.whole_word ?? false} onChange={event => setTerminology({ ...terminology, whole_word: event.target.checked })}/>{t('wholeWord')}</label></div><p>{t('termNote')}</p></>}
      </fieldset><Button type="submit" disabled={mutation.isPending || config.isError}>{mutation.isPending ? <LoaderCircle size={16} className="animate-spin"/> : <ShieldCheck size={16}/>}{t(mutation.isPending ? 'running' : 'start')}</Button></form>
      {error && <div className="check-error" role="alert">{t(`errors.${errorCode}`, { defaultValue: t('errors.fallback') })}</div>}
      <section className="check-results"><header><h2>{t('results')}</h2>{result && <span className="subtle-badge">{t(result.passed ? 'passed' : 'issues', { count: result.issues.length })}</span>}</header>
        {!result ? <div className="checks-empty"><FileCheck2 size={34}/><p>{t('empty')}</p></div> : <>
          {result.issues.length === 0 && result.reports.length === 0 && <div className="checks-empty"><CheckCircle2 size={34}/><p>{t('noIssues')}</p></div>}
          {result.issues.length > 0 && <><div className="check-issue-list">{result.issues.slice((page - 1) * RESULT_PAGE_SIZE, page * RESULT_PAGE_SIZE).map((issue, offset) => <article key={`${issue.id}-${offset}`}><div className="check-issue-heading"><span title={issue.file}>{issue.file} · #{issue.index + 1}</span><Link to={issueLocation(issue)} onClick={() => useUiContextStore.getState().setSelectedItemIds([issue.id])}>{t('goToItem')}</Link></div><p className="check-issue-error">{issue.error}</p><div className="check-issue-text"><div><small>{t('source')}</small><p>{issue.source}</p></div><div><small>{t('translation')}</small><p>{issue.translation || '—'}</p></div></div></article>)}</div><footer><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t('previous')}</Button><span>{t('page', { page, pages })}</span><Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>{t('next')}</Button></footer></>}
          {result.reports.length > 0 && <div className="check-reports"><h3>{t('reports')}</h3>{result.reports.map(report => <div key={report.file}><strong>{report.file}</strong><span>{report.project_type} · {report.encoding}</span><p>{report.stats}</p></div>)}</div>}
        </>}
      </section>
    </>}
  </div>
}
