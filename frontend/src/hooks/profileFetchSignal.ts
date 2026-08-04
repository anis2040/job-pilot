/**
 * A one-shot signal set when a profile is switched to an EMPTY profile (no
 * jobs yet).  The Dashboard consumes it on the next profile change and
 * auto-triggers a fetch — mirroring the original app's `/?fetch=1` redirect.
 */
let pendingAutoFetch = false;

export function markProfileNeedsFetch() {
  pendingAutoFetch = true;
}

/** Returns true once (then resets) if an auto-fetch is pending. */
export function consumeProfileFetchSignal(): boolean {
  if (pendingAutoFetch) {
    pendingAutoFetch = false;
    return true;
  }
  return false;
}
