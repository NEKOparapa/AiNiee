import { create } from 'zustand'

type UiContextState = {
  projectId: string | null
  page: string
  selectedItemIds: string[]
  filters: Record<string, unknown>
  setProjectId: (projectId: string | null) => void
  setPage: (page: string) => void
  setSelectedItemIds: (selectedItemIds: string[]) => void
  setFilters: (filters: Record<string, unknown>) => void
}

export const useUiContextStore = create<UiContextState>((set) => ({
  projectId: null,
  page: '/',
  selectedItemIds: [],
  filters: {},
  setProjectId: (projectId) => set((state) => state.projectId === projectId ? {} : { projectId, selectedItemIds: [], filters: {} }),
  setPage: (page) => set({ page }),
  setSelectedItemIds: (selectedItemIds) => set({ selectedItemIds: [...new Set(selectedItemIds)] }),
  setFilters: (filters) => set({ filters: { ...filters } }),
}))
