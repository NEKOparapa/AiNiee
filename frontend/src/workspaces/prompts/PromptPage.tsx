import type { PromptKind } from '@/api/prompts'
import { PromptLibraryPage } from './PromptLibraryPage'
import { TextPromptPage } from './TextPromptPage'
import { TablesPage } from '@/workspaces/tables/TablesPage'

export function PromptPage({ kind }: { kind: PromptKind | 'library' }) {
  if (kind === 'library') return <PromptLibraryPage/>
  if (kind === 'characters') return <TablesPage name="characters"/>
  if (kind === 'system' || kind === 'polish' || kind === 'analysis_basic' || kind === 'analysis_judgment') return <PromptLibraryPage key={kind} kind={kind}/>
  return <TextPromptPage key={kind} kind={kind}/>
}
