/** Generate a fresh key for one user-initiated broker placement attempt. */
export function newPlacementKey(scope: string): string {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${scope}-${random}`.slice(0, 255);
}
