/** 分析批次：触发 + 轮询直到终态（pending/running → succeeded/failed）。 */
import { create } from 'zustand';
import { getRun, listRuns, triggerRun } from '../api/run';
import type { RunDetail, RunSummary } from '../types/models';

interface RunState {
  runs: RunSummary[];
  current: RunDetail | null;
  loading: boolean;
  triggering: boolean;
  polling: boolean;
  error: string | null;
  loadRuns: (experimentId?: number) => Promise<void>;
  loadRun: (runId: number) => Promise<void>;
  trigger: (experimentId: number) => Promise<RunSummary>;
  pollUntilDone: (runId: number, timeoutMs?: number) => Promise<RunDetail | null>;
  setCurrent: (run: RunDetail | null) => void;
}

export const useRunStore = create<RunState>((set, get) => ({
  runs: [],
  current: null,
  loading: false,
  triggering: false,
  polling: false,
  error: null,

  loadRuns: async (experimentId) => {
    set({ loading: true, error: null });
    try {
      const runs = await listRuns(experimentId);
      set({ runs, loading: false });
    } catch (error) {
      set({ loading: false, error: error instanceof Error ? error.message : '批次加载失败' });
    }
  },

  loadRun: async (runId) => {
    set({ loading: true, error: null });
    try {
      const current = await getRun(runId);
      set({ current, loading: false });
    } catch (error) {
      set({ loading: false, error: error instanceof Error ? error.message : '批次详情加载失败' });
    }
  },

  trigger: async (experimentId) => {
    set({ triggering: true, error: null });
    try {
      const run = await triggerRun(experimentId);
      set((state) => ({ runs: [run, ...state.runs], triggering: false }));
      return run;
    } catch (error) {
      set({ triggering: false, error: error instanceof Error ? error.message : '触发分析失败' });
      throw error;
    }
  },

  pollUntilDone: async (runId, timeoutMs = 120000) => {
    set({ polling: true });
    const started = Date.now();
    try {
      for (;;) {
        const run = await getRun(runId);
        set({ current: run });
        if (run.status === 'succeeded' || run.status === 'failed') return run;
        if (Date.now() - started > timeoutMs) {
          set({ error: '分析超过 120s 未完成，请查看 worker 日志后重试' });
          return run;
        }
        await new Promise((resolve) => setTimeout(resolve, 900));
      }
    } catch (error) {
      set({ error: error instanceof Error ? error.message : '轮询批次状态失败' });
      return null;
    } finally {
      set({ polling: false });
      void get();
    }
  },

  setCurrent: (current) => set({ current }),
}));
