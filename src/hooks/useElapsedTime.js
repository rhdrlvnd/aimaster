import { useEffect, useState } from "react";
export default function useElapsedTime(operation) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!operation) return;
    setElapsed(0);
    const start = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - start) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, [operation]);
  return elapsed;
}
