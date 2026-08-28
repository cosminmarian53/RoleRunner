import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";

export function useApi(path, { immediate = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState("");

  const refetch = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api(path);
      setData(result);
      return result;
    } catch (requestError) {
      setError(requestError.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    if (immediate) refetch();
  }, [immediate, refetch]);

  return { data, loading, error, refetch, setData };
}
