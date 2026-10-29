import { create } from 'zustand'

const STORAGE_KEY = 'ainiee.layout'
type LayoutPreferences = { agentPanelOpen: boolean; sidebarCollapsed: boolean }

function readPreferences(): LayoutPreferences {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
    if (saved && typeof saved === 'object') {
      return {
        agentPanelOpen: 'agentPanelOpen' in saved && saved.agentPanelOpen === true,
        sidebarCollapsed: 'sidebarCollapsed' in saved && saved.sidebarCollapsed === true,
      }
    }
  } catch {
    // Storage is optional; both controls still work within this browser session.
  }
  return { agentPanelOpen: false, sidebarCollapsed: false }
}

function persist(preferences: LayoutPreferences) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences)) } catch { /* optional */ }
}

type LayoutState = LayoutPreferences & {
  toggleAgentPanel: () => void
  setAgentPanelOpen: (open: boolean) => void
  toggleSidebar: () => void
}

export const useLayoutStore = create<LayoutState>((set, get) => ({
  ...readPreferences(),
  toggleAgentPanel: () => get().setAgentPanelOpen(!get().agentPanelOpen),
  setAgentPanelOpen: (agentPanelOpen) => {
    set({ agentPanelOpen })
    persist({ agentPanelOpen, sidebarCollapsed: get().sidebarCollapsed })
  },
  toggleSidebar: () => {
    const sidebarCollapsed = !get().sidebarCollapsed
    set({ sidebarCollapsed })
    persist({ agentPanelOpen: get().agentPanelOpen, sidebarCollapsed })
  },
}))
