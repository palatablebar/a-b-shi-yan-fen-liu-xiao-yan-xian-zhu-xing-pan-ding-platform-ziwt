/** 实验列表与详情缓存。 */
import { create } from 'zustand';
import { getExperiment, listExperiments } from '../api/experiment';
import type { ExperimentDetail, ExperimentSummary } from '../types/models';

interface ExperimentState {
  items: ExperimentSummary[];
  detail: ExperimentDetail | null;
  loadingList: boolean;
  loadingDetail: boolean;
  error: string | null;
  loadList: () => Promise<void>;
  loadDetail: (id: number, force?: boolean) => Promise<void>;
  clearDetail: () => void;
}

export const useExperimentStore = create<ExperimentState>((set, get) => ({
  items: [],
  detail: null,
  loadingList: false,
  loadingDetail: false,
  error: null,

  loadList: async () => {
    set({ loadingList: true, error: null });
    try {
      const items = await listExperiments();
      set({ items, loadingList: false });
    } catch (error) {
      set({
        loadingList: false,
        error: error instanceof Error ? error.message : '实验列表加载失败',
      });
    }
  },

  loadDetail: async (id, force = false) => {
    if (!force && get().detail?.id === id) return;
    set({ loadingDetail: true, error: null });
    try {
      const detail = await getExperiment(id);
      set({ detail, loadingDetail: false });
    } catch (error) {
      set({
        loadingDetail: false,
        error: error instanceof Error ? error.message : '实验详情加载失败',
      });
    }
  },

  clearDetail: () => set({ detail: null }),
}));
