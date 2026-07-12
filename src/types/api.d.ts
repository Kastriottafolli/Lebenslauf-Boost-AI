/**
 * Geteilte API-Typen — der Vertrag zwischen Frontend und Backend.
 *
 * Spiegelt die Pydantic-Schemas in backend/schemas.py. Das Frontend ist
 * Vanilla JS; diese Deklarationen dienen als Dokumentation und geben
 * Editoren (VS Code, PyCharm) Autovervollständigung über JSDoc:
 *
 *   /** @type {import("../../src/types/api").GenerateResponse} *​/
 */

export type Language = "de" | "en";
export type Provider = "claude" | "openai";
export type ProviderChoice = Provider | "compare";
export type Technique = "auto" | "few_shot" | "chain_of_thought";
export type ExportFormat = "pdf" | "docx";
export type Design = "modern" | "classic" | "minimal" | "sapphire" | "cobalt" | "slate";
export type RagMode = "embeddings" | "tfidf";

/** Vom Nutzer in der UI eingegebene API-Keys (überschreiben Server-Keys). */
export interface ApiKeys {
  openai?: string;
  anthropic?: string;
}

/** GET /api/status */
export interface StatusOut {
  app: string;
  version: string;
  providers: Record<Provider, boolean>;
  rag_mode: RagMode;
}

/** POST /api/session */
export interface SessionOut {
  session_id: string;
  language: Language;
  has_cv: boolean;
}

/** POST /api/upload-cv */
export interface UploadOut {
  session_id: string;
  filename: string;
  characters: number;
  chunks: number;
  rag_mode: RagMode;
  preview: string;
  /** data:image/jpeg;base64,… (aus dem CV extrahiert) */
  photo: string | null;
}

/** POST /api/generate — Request */
export interface GenerateRequest {
  session_id: string;
  job_description: string;
  wishes?: string;
  provider: ProviderChoice;
  language: Language;
  technique: Technique;
  keys?: ApiKeys;
}

export interface KeywordAnalysis {
  /** 0–100 % Keyword-Abdeckung */
  ats_score: number;
  matched_keywords: string[];
  missing_keywords: string[];
}

export interface GenerationOut {
  generation_id: string;
  provider: Provider;
  model: string;
  technique: Technique | "refine";
  /** Lebenslauf als Markdown */
  content: string;
  analysis: KeywordAnalysis;
  is_demo: boolean;
}

/** POST /api/generate — Response */
export interface GenerateResponse {
  mode: "single" | "compare";
  results: GenerationOut[];
  winner_provider?: Provider | null;
  recommendation?: string | null;
}

/** POST /api/refine — Request (Response: GenerationOut) */
export interface RefineRequest {
  session_id: string;
  instruction: string;
  current_content?: string | null;
  provider: Provider;
  language: Language;
  keys?: ApiKeys;
}

/** POST /api/export — Request (Response: Binärdatei PDF/DOCX) */
export interface ExportRequest {
  session_id?: string | null;
  content: string;
  format: ExportFormat;
  design: Design;
  language: Language;
  filename?: string;
  /** data:image/…;base64,… oder null */
  photo?: string | null;
}
