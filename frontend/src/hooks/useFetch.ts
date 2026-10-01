import { useEffect, useState, useCallback, useRef } from "react";
import client from "../api/client";

interface FetchOptions {
  /** Re-fetch quietly at this interval (ms) so changes made by other users appear without a manual refresh. */
  pollMs?: number;
}

export function useFetch<T = any>(url: string | null, deps: any[] = [], opts: FetchOptions = {}) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);

  const load = useCallback((silent: boolean) => {
    if (!url) return;
    const ticket = ++latest.current;
    if (!silent) setLoading(true);
    client
      .get(url)
      .then((res) => {
        if (ticket !== latest.current) return; // a newer request superseded this one
        setData(res.data);
        setError(null);
      })
      .catch((err) => {
        if (ticket !== latest.current || silent) return;
        const detail = err?.response?.data?.detail;
        setError(typeof detail === "string" ? detail : detail?.message || "Failed to load data");
      })
      .finally(() => {
        if (ticket === latest.current && !silent) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);

  const reload = useCallback(() => load(false), [load]);
  /** Re-fetch without showing the loading state. */
  const refresh = useCallback(() => load(true), [load]);

  useEffect(() => {
    load(false);
  }, [load]);

  useEffect(() => {
    if (!opts.pollMs) return;
    const id = window.setInterval(() => {
      if (!document.hidden) load(true);
    }, opts.pollMs);
    return () => window.clearInterval(id);
  }, [load, opts.pollMs]);

  return { data, loading, error, reload, refresh };
}
