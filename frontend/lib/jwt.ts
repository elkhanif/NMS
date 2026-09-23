/**
 * Decodes (never verifies) a JWT payload -- used purely for reading `role`/`sub` to
 * drive UI state. The backend re-verifies the signature on every real request; this
 * is not a security boundary, just a way to avoid an extra round trip for UI gating.
 */
export function decodeJwtPayload<T = Record<string, unknown>>(token: string): T | null {
  try {
    const [, payload] = token.split(".");
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
    const json = Buffer.from(padded, "base64").toString("utf-8");
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
}

export interface AccessTokenClaims {
  sub: string;
  role: string;
  type: string;
  iat: number;
  exp: number;
}
