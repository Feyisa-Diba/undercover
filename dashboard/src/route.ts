import { useSyncExternalStore } from "react";

export type Route =
  | { page: "queue" }
  | { page: "claim"; claimId: string }
  | { page: "instructions" };

export function parseRoute(hash: string): Route {
  const claim = /^#\/claims\/([\w-]+)$/.exec(hash);
  if (claim?.[1]) return { page: "claim", claimId: claim[1] };
  if (hash === "#/instructions") return { page: "instructions" };
  return { page: "queue" };
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
  };
}

/** The page the address bar's hash points to, such as #/claims/CLM-1001. */
export function useRoute(): Route {
  return parseRoute(
    useSyncExternalStore(subscribe, () => window.location.hash),
  );
}
