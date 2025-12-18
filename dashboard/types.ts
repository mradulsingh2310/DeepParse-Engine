/**
 * TypeScript types matching Python evaluation models
 * Based on evaluation/models.py and evaluation/cache.py
 */

// Match types from evaluation/models.py
export type MatchType = "exact" | "partial" | "missing" | "extra";

export interface ValidationError {
  path: string;
  message: string;
  value?: string | null;
}

export interface FieldConfigComparison {
  mandatory: boolean;
  notes_enabled: boolean;
  notes_required_for_all_options: boolean;
  notes_required_for_selected_options: number;
  attachments_enabled: boolean;
  attachments_required_for_all_options: boolean;
  attachments_required_for_selected_options: number;
  can_create_work_order: boolean;
  work_order_category: boolean;
  work_order_sub_category: boolean;
}

export interface FieldEvaluation {
  source_field_id: number;
  model_field_id: number | null;
  source_name: string;
  model_name: string | null;
  match_type: MatchType;
  name_similarity: number;
  options_similarity: number;
  rating_type_match: boolean;
  options_exact_match: number;
  config_comparison: FieldConfigComparison | null;
  reasoning: string | null;
  config_score: number;
  overall_score: number;
}

export interface SectionEvaluation {
  source_section_name: string;
  model_section_name: string | null;
  section_name_similarity: number;
  source_field_count: number;
  model_field_count: number;
  field_count_match: boolean;
  matched_fields: number;
  missing_fields: number;
  extra_fields: number;
  fields: FieldEvaluation[];
  section_score: number;
}

export interface SchemaValidationResult {
  is_valid: boolean;
  errors: ValidationError[];
  error_count: number;
  compliance_score: number;
}

export interface AggregateScores {
  schema_compliance: number;
  structural_accuracy: number;
  semantic_accuracy: number;
  config_accuracy: number;
  overall_score: number;
}

export interface ModelMetadata {
  provider: string;
  model_id: string;
  supporting_model_id: string | null;
}

export interface EvaluationResult {
  source_file: string;
  model_file: string;
  metadata: ModelMetadata;
  schema_validation: SchemaValidationResult;
  total_source_sections: number;
  total_model_sections: number;
  sections: SectionEvaluation[];
  scores: AggregateScores;
  timestamp: string;
  evaluation_duration_ms: number | null;
}

// Match types from evaluation/cache.py
export interface RunHistoryEntry {
  timestamp: string;
  overall_score: number;
  schema_compliance: number;
  structural_accuracy: number;
  semantic_accuracy: number;
  config_accuracy: number;
  cost?: number;
  input_tokens?: number;
  output_tokens?: number;
}

export interface CachedModelResult {
  model_id: string;
  provider: string;
  run_count: number;
  total_schema_compliance: number;
  total_structural_accuracy: number;
  total_semantic_accuracy: number;
  total_config_accuracy: number;
  total_overall_score: number;
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  best_score: number;
  best_run_timestamp: string | null;
  latest_score: number;
  latest_run_timestamp: string | null;
  run_history: RunHistoryEntry[];
}

export interface EvaluationCache {
  source_file: string;
  last_updated: string;
  models: Record<string, CachedModelResult>;
}

// API response types
export interface EvaluationSummary {
  source_file: string;
  last_updated: string;
  model_count: number;
  best_model: string | null;
  best_score: number | null;
  average_score: number | null;
}

export interface EvaluationsListResponse {
  evaluations: EvaluationSummary[];
}

export interface RunStatus {
  status: "idle" | "running" | "completed" | "error";
  message?: string;
  progress?: {
    current: number;
    total: number;
    currentModel?: string;
  };
}

// WebSocket message types
export type WSMessageType = 
  | "connected"
  | "run_started"
  | "model_started"
  | "model_completed"
  | "run_completed"
  | "run_error"
  | "cache_updated";

export interface WSMessage {
  type: WSMessageType;
  timestamp: string;
  data?: {
    message?: string;
    provider?: string;
    model_id?: string;
    score?: number;
    progress?: { current: number; total: number };
    error?: string;
  };
}

// Pricing
export interface PricingRate {
  input: number;
  output: number;
}

export type PricingTable = Record<string, Record<string, PricingRate>>;

// Chart data types
export interface ModelChartData {
  key: string;
  name: string;
  provider: string;
  overall: number;
  schema: number;
  structure: number;
  semantic: number;
  config: number;
  runCount: number;
  totalCost: number;
  averageCost: number;
  totalInputTokens: number;
  totalOutputTokens: number;
}

export interface TrendDataPoint {
  timestamp: string;
  date: string;
  [modelKey: string]: string | number;
}

// Document explorer types
export interface PdfInfo {
  name: string;
  stem: string;
  source_exists: boolean;
  model_count: number;
  best_score: number | null;
  average_score: number | null;
}

export interface ModelScores {
  overall: number | null;
  schema: number | null;
  structure: number | null;
  semantic: number | null;
  config: number | null;
  run_count?: number;
}

export interface ModelOutputInfo {
  providerDir: string;
  modelDir: string;
  filePath: string;
  metadata: ModelMetadata;
  scores: ModelScores | null;
  run_count?: number;
  cache_key?: string;
}

export interface EvaluationDetail {
  scores: AggregateScores;
  schema_validation: SchemaValidationResult;
  sections: SectionEvaluation[];
  source_file?: string;
  model_file?: string;
  metadata?: ModelMetadata;
}

export interface ModelDetailResponse {
  stem: string;
  providerDir: string;
  modelDir: string;
  model: any;
  source: any;
  metadata: ModelMetadata;
  evaluation: EvaluationDetail | null;
  cacheScores: ModelScores | null;
}

