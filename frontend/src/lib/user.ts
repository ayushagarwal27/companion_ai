const USER_ID_KEY = "companion_ai:user_id";

/** Returns this browser's persistent user id, creating and storing one on first visit. */
export function getOrCreateUserId(): string {
  const existing = localStorage.getItem(USER_ID_KEY);
  if (existing) return existing;

  const id = crypto.randomUUID();
  localStorage.setItem(USER_ID_KEY, id);
  return id;
}
