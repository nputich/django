/**
 * Move an item to a 1-based position, clamped to [1, length].
 * Other items shift to fill the gap (e.g. position 50 in a 9-item list → 9).
 */
export function moveToPosition(items, fromIndex, position) {
  const n = items.length;
  if (n === 0 || fromIndex < 0 || fromIndex >= n) {
    return items;
  }
  const parsed = Number.parseInt(String(position), 10);
  const clamped = Math.max(1, Math.min(n, Number.isFinite(parsed) ? parsed : 1));
  return moveToIndex(items, fromIndex, clamped - 1);
}

/** Move an item to a 0-based index, clamped to [0, length - 1]. */
export function moveToIndex(items, fromIndex, toIndex) {
  const n = items.length;
  if (n === 0 || fromIndex < 0 || fromIndex >= n) {
    return items;
  }
  const clamped = Math.max(0, Math.min(n - 1, toIndex));
  if (fromIndex === clamped) {
    return items;
  }
  const next = [...items];
  const [item] = next.splice(fromIndex, 1);
  next.splice(clamped, 0, item);
  return next;
}

/** Reassign 1-based order field on each item (mutates copies). */
export function withSequentialOrder(items, orderKey = "order") {
  return items.map((item, index) => ({ ...item, [orderKey]: index + 1 }));
}
