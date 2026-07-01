export type Language = "en" | "fr";
export type FieldType = "string" | "text" | "date" | "int" | "number" | "enum" | "bool";
export type FormStatus = "draft" | "published";

export interface Account {
  id: number;
  nom: string;
  email_contact: string;
  langue: Language;
  persona_prompt: string;
  voice_prompt: string;
  actif: boolean;
  allowed_origins: string[];
  date_creation: string;
}

export interface ApiKey {
  id: number;
  label: string;
  key_masquee: string;
  actif: boolean;
  cree_a: string;
}

export interface KeyCreated {
  id: number;
  label: string;
  cle_en_clair: string;
  actif: boolean;
  cree_a: string;
}

export interface FieldDef {
  name: string;
  label: string;
  type: FieldType;
  required: boolean;
  enum_values: string[];
  description: string;
}

export interface FormDef {
  id: number | null;
  form_id: string;
  titre: string;
  version: number;
  statut: FormStatus;
  language: Language | null;
  fields: FieldDef[];
}

export interface SessionInfo {
  session_id: string;
  ws_url: string;
  token: string;
  language: Language;
  expires_at: string;
  form_schema: { fields: FieldDef[]; titre: string; form_id: string };
}
