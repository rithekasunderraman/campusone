import { useEffect, useState, useCallback } from "react";
import client from "../api/client";

export function useFetch<T = any>(url: string | null, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    if (!url) return;
    setLoading(true);
    client
      .get(url)
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.detail || "Failed to load data"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, loading, error, reload };
}
