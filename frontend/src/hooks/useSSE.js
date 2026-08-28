import { useEffect, useState } from "react";

export function useSSE(url) {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource(url);
    source.onopen = () => setConnected(true);
    source.onmessage = (event) => {
      try {
        setData(JSON.parse(event.data));
      } catch {
        setData({ message: event.data });
      }
    };
    source.onerror = () => setConnected(false);
    return () => source.close();
  }, [url]);

  return { data, connected };
}
