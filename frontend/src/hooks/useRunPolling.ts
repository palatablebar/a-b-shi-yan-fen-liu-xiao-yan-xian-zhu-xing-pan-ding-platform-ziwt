/** 批次轮询：只在 pending/running 时继续拉取，终态自动停止。 */
import { useEffect, useState } from 'react';
import { getRun } from '../api/run';
import type { RunDetail } from '../types/models';
import { errorMessage } from '../utils/errorMessage';

export const useRunPolling = (
  runId: number | null,
  onFinished?: (run: RunDetail) => void,
): { run: RunDetail | null; error: string | null } => {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      return;
    }
    let active = true;
    let timer: number | undefined;
    setError(null);

    const tick = async () => {
      try {
        const detail = await getRun(runId);
        if (!active) return;
        setRun(detail);
        if (detail.status === 'succeeded' || detail.status === 'failed') {
          onFinished?.(detail);
          return;
        }
        timer = window.setTimeout(tick, 900);
      } catch (err) {
        if (active) setError(errorMessage(err));
      }
    };
    void tick();

    return () => {
      active = false;
      if (timer) window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  return { run, error };
};
