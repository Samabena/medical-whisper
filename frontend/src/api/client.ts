// Client API typé : gère les jetons admin (access/refresh) avec rafraîchissement auto.
import type {
  Account,
  ApiKey,
  FieldDef,
  FormDef,
  KeyCreated,
  Language,
  SessionInfo,
} from "./types";

const ACCESS_KEY = "vtf_access";
const REFRESH_KEY = "vtf_refresh";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

function getAccess(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}
function getRefresh(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}
export function setTokens(access: string, refresh?: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
export function isAuthenticated(): boolean {
  return getAccess() !== null;
}

async function parse(resp: Response): Promise<any> {
  const text = await resp.text();
  const body = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = body?.detail ?? body?.erreur ?? resp.statusText;
    throw new ApiError(resp.status, String(detail));
  }
  return body;
}

async function refreshAccess(): Promise<boolean> {
  const refresh = getRefresh();
  if (!refresh) return false;
  const resp = await fetch("/admin/api/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!resp.ok) return false;
  const body = await resp.json();
  setTokens(body.access_token);
  return true;
}

// Appel authentifié admin (Bearer), avec un retry après refresh sur 401.
async function adminFetch(path: string, init: RequestInit = {}, retry = true): Promise<any> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string>),
  };
  const access = getAccess();
  if (access) headers["Authorization"] = `Bearer ${access}`;
  const resp = await fetch(path, { ...init, headers });
  if (resp.status === 401 && retry && (await refreshAccess())) {
    return adminFetch(path, init, false);
  }
  return parse(resp);
}

// --- Auth -----------------------------------------------------------------
export async function login(password: string): Promise<void> {
  const resp = await fetch("/admin/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  const body = await parse(resp);
  setTokens(body.access_token, body.refresh_token);
}

// --- Comptes --------------------------------------------------------------
export const accountsApi = {
  list: (): Promise<Account[]> => adminFetch("/admin/api/accounts"),
  get: (id: number): Promise<Account> => adminFetch(`/admin/api/accounts/${id}`),
  create: (data: { nom: string; email_contact: string; langue: Language }): Promise<Account> =>
    adminFetch("/admin/api/accounts", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<Account>): Promise<Account> =>
    adminFetch(`/admin/api/accounts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
};

// --- Clés -----------------------------------------------------------------
export const keysApi = {
  list: (accountId: number): Promise<ApiKey[]> =>
    adminFetch(`/admin/api/accounts/${accountId}/keys`),
  create: (accountId: number, label: string): Promise<KeyCreated> =>
    adminFetch(`/admin/api/accounts/${accountId}/keys`, {
      method: "POST",
      body: JSON.stringify({ label }),
    }),
  revoke: (accountId: number, keyId: number): Promise<ApiKey> =>
    adminFetch(`/admin/api/accounts/${accountId}/keys/${keyId}`, { method: "DELETE" }),
};

// --- Formulaires ----------------------------------------------------------
export const formsApi = {
  list: (accountId: number): Promise<FormDef[]> =>
    adminFetch(`/admin/api/accounts/${accountId}/forms`),
  create: (
    accountId: number,
    data: { form_id: string; titre: string; langue: Language | null; fields: FieldDef[] }
  ): Promise<FormDef> =>
    adminFetch(`/admin/api/accounts/${accountId}/forms`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (
    accountId: number,
    formId: string,
    data: { titre?: string; langue?: Language | null; fields?: FieldDef[] }
  ): Promise<FormDef> =>
    adminFetch(`/admin/api/accounts/${accountId}/forms/${formId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  publish: (accountId: number, formId: string): Promise<FormDef> =>
    adminFetch(`/admin/api/accounts/${accountId}/forms/${formId}/publish`, { method: "POST" }),
};

// --- Intégration (test live, via clé API d'un compte) ---------------------
export const integrationApi = {
  createSession: (apiKey: string, formId: string): Promise<SessionInfo> =>
    fetch("/v1/integration/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
      body: JSON.stringify({ form_id: formId }),
    }).then(parse),
  listForms: (apiKey: string): Promise<{ form_id: string; titre: string }[]> =>
    fetch("/v1/integration/forms", { headers: { "X-API-Key": apiKey } }).then(parse),
};
