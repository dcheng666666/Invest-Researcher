import { useEffect, useState } from "react";

/**
 * Subscribes to window.matchMedia(query). SSR-safe initial false until mounted.
 */
export function useMediaQuery(query: string): boolean {
  const getMatches = () =>
    typeof window !== "undefined" && window.matchMedia(query).matches;

  const [matches, setMatches] = useState(getMatches);

  useEffect(() => {
    const media = window.matchMedia(query);
    const listener = () => setMatches(media.matches);
    listener();
    media.addEventListener("change", listener);
    return () => media.removeEventListener("change", listener);
  }, [query]);

  return matches;
}
