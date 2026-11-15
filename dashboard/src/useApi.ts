import { useCallback, useEffect, useState } from "react";
import { getJson } from "./api";

/** How often live pages ask the API for news, in milliseconds. */
export const REFRESH_MS = 2000;

export interface Loaded<T> {
  data: T | undefined;
  error: string | undefined;
  reload: () => void;
}

interface Result<T> {
  path: string;
  data?: T;
  error?: string;
}

/** Load a path from the API, and again every refreshMs when it's above 0. */
export function useApi<T>(path: string, refreshMs = 0): Loaded<T> {
  const [result, setResult] = useState<Result<T>>({ path });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    const load = () => {
      void getJson<T>(path).then(
        (data) => {
          if (live) setResult({ path, data });
        },
        (error: unknown) => {
          if (!live) return;
          const message =
            error instanceof Error ? error.message : String(error);
          setResult((previous) => ({
            path,
            data: previous.path === path ? previous.data : undefined,
            error: message,
          }));
        },
      );
    };
    load();
    const timer = refreshMs > 0 ? setInterval(load, refreshMs) : undefined;
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [path, refreshMs, version]);

  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);
  const current = result.path === path ? result : { path };
  return { data: current.data, error: current.error, reload };
}
