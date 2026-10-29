import { BookOpen, BookText, Braces, CheckCheck, CircleHelp, FileOutput, FileText, FolderTree, Home, Languages, ListFilter, MessagesSquare, Palette, PencilLine, ScanText, Settings2, SlidersHorizontal, Sparkles, Table2, Terminal, TextCursorInput, TextQuote, Users, WandSparkles, Workflow } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type WorkspaceKind = 'home' | 'platforms' | 'overview' | 'task' | 'output' | 'advanced' | 'appearance' | 'logs' | 'about' | 'placeholder'
export type WorkspaceGroup = 'start' | 'project' | 'settings' | 'prompts' | 'tables' | 'bottom'
export interface WorkspaceEntry { id: string; path: string; label: string; group: WorkspaceGroup; icon: LucideIcon; kind: WorkspaceKind }

export const workspaceGroups: WorkspaceGroup[] = ['start', 'project', 'settings', 'prompts', 'tables']
export const workspaces: WorkspaceEntry[] = [
  { id: 'home', path: '/', label: 'home', group: 'start', icon: Home, kind: 'home' },
  { id: 'platforms', path: '/platforms', label: 'platforms', group: 'start', icon: Workflow, kind: 'platforms' },
  { id: 'overview', path: '/project', label: 'overview', group: 'project', icon: FolderTree, kind: 'overview' },
  { id: 'items', path: '/items', label: 'items', group: 'project', icon: Table2, kind: 'placeholder' },
  { id: 'checks', path: '/checks', label: 'checks', group: 'project', icon: CheckCheck, kind: 'placeholder' },
  { id: 'export', path: '/export', label: 'export', group: 'project', icon: FileOutput, kind: 'placeholder' },
  { id: 'analysis', path: '/analysis', label: 'analysis', group: 'project', icon: ScanText, kind: 'placeholder' },
  { id: 'task', path: '/settings/task', label: 'task', group: 'settings', icon: SlidersHorizontal, kind: 'task' },
  { id: 'output', path: '/settings/output', label: 'output', group: 'settings', icon: FileOutput, kind: 'output' },
  { id: 'advanced', path: '/settings/advanced', label: 'advanced', group: 'settings', icon: Settings2, kind: 'advanced' },
  { id: 'systemPrompt', path: '/prompts/system', label: 'systemPrompt', group: 'prompts', icon: TextQuote, kind: 'placeholder' },
  { id: 'charactersPrompt', path: '/prompts/characters', label: 'charactersPrompt', group: 'prompts', icon: Users, kind: 'placeholder' },
  { id: 'worldPrompt', path: '/prompts/world', label: 'worldPrompt', group: 'prompts', icon: BookOpen, kind: 'placeholder' },
  { id: 'stylePrompt', path: '/prompts/style', label: 'stylePrompt', group: 'prompts', icon: PencilLine, kind: 'placeholder' },
  { id: 'examplesPrompt', path: '/prompts/examples', label: 'examplesPrompt', group: 'prompts', icon: MessagesSquare, kind: 'placeholder' },
  { id: 'polishPrompt', path: '/prompts/polish', label: 'polishPrompt', group: 'prompts', icon: WandSparkles, kind: 'placeholder' },
  { id: 'promptLibrary', path: '/prompts/library', label: 'promptLibrary', group: 'prompts', icon: BookText, kind: 'placeholder' },
  { id: 'glossary', path: '/tables/glossary', label: 'glossary', group: 'tables', icon: Languages, kind: 'placeholder' },
  { id: 'exclusion', path: '/tables/exclusion', label: 'exclusion', group: 'tables', icon: ListFilter, kind: 'placeholder' },
  { id: 'replaceA', path: '/tables/replace-a', label: 'replaceA', group: 'tables', icon: TextCursorInput, kind: 'placeholder' },
  { id: 'replaceB', path: '/tables/replace-b', label: 'replaceB', group: 'tables', icon: Braces, kind: 'placeholder' },
  { id: 'logs', path: '/logs', label: 'logs', group: 'bottom', icon: Terminal, kind: 'logs' },
  { id: 'appearance', path: '/settings/app', label: 'appSettings', group: 'bottom', icon: Palette, kind: 'appearance' },
  { id: 'about', path: '/about', label: 'about', group: 'bottom', icon: CircleHelp, kind: 'about' },
]

export const workspaceForPath = (path: string) => workspaces.find(entry => entry.path === path)
export { FileText, Sparkles }
