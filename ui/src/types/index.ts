export interface AuthUser {
  id: number;
  tenant_id: number;
  email: string;
  role: string;
  first_name?: string;
  last_name?: string;
  is_premium?: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface MeResponse extends AuthUser {
  broker_connections: BrokerConnectionSummary[];
}

export interface BrokerConnectionSummary {
  id: number;
  broker_name: string;
  broker_user_id: string | null;
  created_at: string | null;
  token_updated_at: string | null;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface BrokerConnectionResponse {
  id: number;
  tenant_id: number;
  user_id: number;
  broker_name: string;
  created_at: string;
}

export interface BrokerConnectionCreate {
  broker_name: string;
  tokens: Record<string, unknown>;
  metadata: Record<string, unknown>;
  user_id?: number;
}

export interface ActiveConnectionResponse {
  broker_connection_id: number | null;
  broker_name: string | null;
  broker_user_id: string | null;
}

export interface ActiveConnectionSetRequest {
  broker_connection_id: number;
}

export interface SessionResponse {
  session_id: string;
  user_id: string;
  broker: string;
  expires_at?: string;
  tenant_id?: number;
}

export interface SessionStartRequest {
  session_user_id?: string;
  broker_name?: string;
  broker_config?: Record<string, string>;
  broker_connection_id?: number;
  market_data_connection_id?: number;
  warm_start?: boolean;
}

export interface SessionCreate {
  broker_connection_id: number;
  warm_start?: boolean;
}

export interface JobStatus {
  id: number;
  session_id: string;
  job_type: string;
  status: string;
  progress: number;
  log?: string;
  created_at: string;
  updated_at: string;
}

export interface JobStatusResponse {
  job: JobStatus;
}

export interface JobListResponse {
  jobs: JobStatus[];
}

export interface JobQueuedResponse {
  job_id: number;
}

export interface HoldingsLatestResponse {
  items: Record<string, unknown>[];
}

export interface HoldingsAnalyzeRequest {
  session_id: string;
  filters?: Record<string, unknown>;
  sort_by?: string;
}

export interface OrderHistoryStatus {
  available: boolean;
  trade_count: number;
  symbol_count: number;
  fetched_at: string | null;
  source: string | null;
  date_from: string | null;
  date_to: string | null;
  skipped_symbols?: string[];
  errors?: string[];
}

export type AgeReason = 
  | "order_history_not_fetched"
  | "no_trades_for_symbol"
  | "no_buy_trades"
  | "buy_trades_beyond_400_days"
  | "trade_qty_mismatch"
  | null;

export interface HoldingsRow {
  symbol: string;
  quantity: number;
  average_price: number;
  last_price: number | null;
  invested: number;
  profit: number;
  profit_pct: number;
  quality: string | null;
  age: number | null;
  age_reason: AgeReason;
  age_trade_qty?: number | null;
  age_holding_qty?: number | null;
  profit_per_day: number | null;
  weighted_roi: number | null;
  wroi_trend?: string;
  exit_score?: number | null;
  exit_action?: string | null;
  ema_score?: number | null;
  volume_score?: number | null;
  wroi_score?: number | null;
  thesis_broken?: boolean;
  thesis_break_price?: number | null;
  thesis_break_pct?: number | null;
}

export interface WroiScore {
  exit_score: number | null;
  exit_action: string | null;
  ema_score: number | null;
  volume_score: number | null;
  wroi_score: number | null;
  wroi_trend: string;
}

export interface HoldingsResponse {
  session_id: string;
  broker: string;
  broker_user_id: string;
  holdings: HoldingsRow[];
  order_history: OrderHistoryStatus;
}

export interface Trade {
  symbol: string;
  trade_date: string | null;
  side: string;
  quantity: number;
  price: number;
  trade_id: string | null;
  source: string;
}

export interface TradesListResponse {
  trades: Trade[];
  total_count: number;
  symbol: string | null;
}

export interface PlanLatestResponse {
  strategy_type: 'multi_level' | 'dynamic_averaging';
  plan: Record<string, unknown>[];
  skipped: { symbol?: string; Symbol?: string; skip_reason?: string; reason?: string; [key: string]: unknown }[];
}

export interface PlanGenerateRequest {
  session_id: string;
  apply_risk?: boolean;
}

export interface RiskApplyRequest {
  session_id: string;
  plan: Record<string, unknown>[];
}

export interface GTTOrder {
  id?: number;
  [key: string]: unknown;
}

export interface GTTOrdersResponse {
  orders: GTTOrder[];
}

export interface GTTPreviewRequest {
  session_id: string;
  plan: Record<string, unknown>[];
}

export interface GTTConfirmRequest {
  session_id: string;
  plan: Record<string, unknown>[];
}

export interface GTTApplyRequest {
  session_id: string;
  plan: Record<string, unknown>[];
  confirmation_token: string;
}

export interface GTTConfirmResponse {
  token: string;
  expires_at: string;
}

export interface BrokerConnectResponse {
  authorize_url: string;
  state: string;
  connection_id: number;
}

export interface ConnectionStatus {
  connection_id: number;
  user_id: number;
  connected: boolean;
  broker_user_id: string | null;
  token_updated_at: string | null;
  expires_at: string | null;
  token_status: 'valid' | 'expired' | 'missing';
}

export interface BrokerStatusResponse {
  connections: ConnectionStatus[];
}

export interface UpstoxConnectionStatus extends ConnectionStatus {}

export interface UpstoxStatusResponse extends BrokerStatusResponse {}

export interface ZerodhaConnectResponse {
  authorize_url: string;
  state: string;
  connection_id: number;
}

export interface ZerodhaConnectionStatus extends ConnectionStatus {}

export interface ZerodhaStatusResponse {
  connections: ZerodhaConnectionStatus[];
}

export interface ServiceError {
  error_code: string;
  message: string;
  context: Record<string, unknown>;
  retryable: boolean;
}

export interface EntryLevelType {
  id?: number;
  level_no: number;
  price: number;
  is_active: boolean;
}

export interface EntryStrategySummary {
  symbol: string;
  allocated: number | null;
  quality: string | null;
  exchange: string | null;
  entry1: number | null;
  entry2: number | null;
  entry3: number | null;
  da_enabled: boolean;
  da_legs: number | null;
  da_e1_buyback: number | null;
  da_e2_buyback: number | null;
  da_e3_buyback: number | null;
  da_trigger_offset: number | null;
  levels_count: number;
  created_at: string;
  updated_at: string;
  swing_eligible: boolean | null;
  swing_avg_volume: number | null;
  swing_atr_percent: number | null;
  swing_range_percent: number | null;
  swing_reasons: string[] | null;
  thesis_break_price: number | null;
  review_status: string | null;
  is_holding: boolean;
  holding_entry_level: string | null;
}

export interface EntryStrategyFull {
  id: number;
  symbol: string;
  allocated: number | null;
  quality: string | null;
  exchange: string | null;
  dynamic_averaging_enabled: boolean;
  averaging_rules_json: string | null;
  averaging_rules_summary: string | null;
  levels: EntryLevelType[];
  created_at: string;
  updated_at: string;
  swing_eligible: boolean | null;
  thesis_break_price: number | null;
  review_status: string | null;
  last_evaluated_at: string | null;
  last_entry_revision_at: string | null;
  da_eligible: boolean | null;
  da_status: string | null;
  da_last_evaluated_at: string | null;
  da_confidence_score: number | null;
  da_notes: string | null;
  override_da_enabled: boolean | null;
  override_da_qty_pct: number | null;
  override_sell_offset: number | null;
  override_buyback_price: number | null;
  override_sell_price: number | null;
}

export interface EntryStrategyListResponse {
  strategies: EntryStrategySummary[];
}

export interface InlineUpdateFields {
  allocated?: number;
  entry1?: number;
  entry2?: number;
  entry3?: number;
}

export interface InlineUpdateResponse {
  symbol: string;
  updated_fields: string[];
  updated_at: string;
}

export type CellStatus = 'idle' | 'saving' | 'saved' | 'error';

export interface EntryStrategyUploadResponse {
  symbols_processed: number;
  created_count: number;
  updated_count: number;
  errors: Array<{ row?: number; error: string }>;
  updated_at: string;
}

export interface SuggestedRevision {
  level_no: number;
  original_price: number;
  suggested_price: number;
  rationale: string;
}

export interface SuggestRevisionResponse {
  symbol: string;
  cmp_price: number | null;
  revised_levels: SuggestedRevision[];
  swing_eligible: boolean | null;
  review_status: string | null;
  thesis_break_price: number | null;
  revision_reason: string | null;
  style: string | null;
}

export interface ApplyRevisionItem {
  level_no: number;
  new_price: number;
}

export interface ApplyRevisionRequest {
  levels: ApplyRevisionItem[];
  thesis_break_price?: number | null;
}

export interface ApplyRevisionResponse {
  symbol: string;
  updated_levels: number[];
  updated_at: string;
}

export interface BulkSuggestRevisionItem {
  symbol: string;
  cmp_price: number | null;
  revised_levels: SuggestedRevision[];
  swing_eligible: boolean | null;
  review_status: string | null;
  thesis_break_price: number | null;
  revision_reason: string | null;
  style: string | null;
}

export interface BulkSuggestRevisionResponse {
  suggestions: BulkSuggestRevisionItem[];
}

export interface BulkApplyRevisionItem {
  symbol: string;
  levels: ApplyRevisionItem[];
  thesis_break_price?: number | null;
}

export interface BulkApplyRevisionResult {
  symbol: string;
  success: boolean;
  updated_levels: number[];
  updated_at: string | null;
  error: string | null;
}

export interface BulkApplyRevisionResponse {
  results: BulkApplyRevisionResult[];
  total_updated: number;
  total_failed: number;
}

export interface UploadHistoryItem {
  id: number;
  filename: string;
  symbols: string[];
  created_at: string;
}

export interface UploadHistoryResponse {
  uploads: UploadHistoryItem[];
}

export interface VersionItem {
  id: number;
  version_no: number;
  action: string;
  levels: EntryLevelType[];
  changes_summary: string | null;
  created_at: string;
}

export interface VersionListResponse {
  versions: VersionItem[];
}

export interface RestoreVersionResponse {
  symbol: string;
  restored_to_version: number;
  updated_at: string;
}

export interface EvaluateStrategyResponse {
  symbol: string;
  review_status: string;
  swing_eligible: boolean | null;
  swing_avg_volume: number | null;
  swing_atr_percent: number | null;
  swing_range_percent: number | null;
  swing_reasons: string[] | null;
  thesis_break_price: number | null;
  last_evaluated_at: string | null;
  reason: string | null;
}

export interface DAEvalResult {
  symbol: string;
  da_eligible: boolean;
  da_status: string | null;
  da_confidence_score: number | null;
  da_confidence_label: string | null;
  da_last_evaluated_at: string | null;
  da_notes: string | null;
  recommended_sell_trigger: number | null;
  recommended_sell_limit: number | null;
  recommended_buyback_price: number | null;
  recommended_da_qty: number;
  recommended_da_qty_pct: number;
  expected_sell_value: number | null;
  expected_buyback_value: number | null;
  expected_charges: number | null;
  expected_net_profit: number | null;
  position_risk_score: number | null;
  range_high: number | null;
  range_low: number | null;
  range_width: number | null;
  range_pct: number | null;
}

export interface DABulkEvalResponse {
  session_id: string;
  results: DAEvalResult[];
}

export interface DAOverrideRequest {
  override_da_enabled?: boolean | null;
  override_da_qty_pct?: number | null;
  override_sell_offset?: number | null;
  override_buyback_price?: number | null;
  override_sell_price?: number | null;
}

export interface DAConfig {
  minimum_da_net_profit: number;
  default_sell_offset: number;
  minimum_volume_threshold: number;
  da_range_analysis_days: number;
  high_confidence_qty_pct: number;
  medium_confidence_qty_pct: number;
  low_confidence_qty_pct: number;
  no_recommendation_min_score: number;
  confidence_high_threshold: number;
  confidence_medium_threshold: number;
  confidence_low_threshold: number;
}

// ── Entry Candidate Pipeline ──────────────────────────────────────────────────

export type StrategyType = 'MULTI_LEVEL' | 'DYNAMIC_AVERAGING' | 'SIP';
export type CandidateStatus = 'READY' | 'WARNING' | 'REVIEW' | 'SKIPPED';

export interface NormalizedCandidate {
  symbol: string;
  exchange: string | null;
  strategy_type: StrategyType;
  side: string;
  status: CandidateStatus;
  status_severity: number;
  signal: string | null;
  cmp: number | null;
  order_price: number | null;
  trigger_price: number | null;
  qty: number;
  amount: number;
  allocation: number | null;
  current_holding_qty: number;
  current_holding_value: number;
  allocation_used_percent: number;
  level_or_leg: string;
  strategy_reference: string | null;
  reason_code: string | null;
  reason_message: string | null;
  suggested_action: string | null;
  is_selectable: boolean;
  created_at: string | null;
  additional_details: Record<string, unknown>;
}

export interface SkippedCandidate {
  symbol: string;
  exchange: string | null;
  strategy_type: StrategyType;
  cmp: number | null;
  level_or_leg: string | null;
  reason_code: string;
  reason_message: string;
  suggested_action: string;
  technical_details: string | null;
}

export interface CandidateSummary {
  total: number;
  ready: number;
  warning: number;
  review: number;
  skipped: number;
  capital_required: number;
}

export interface CandidateGenerateResponse {
  strategy_type: string;
  candidates: NormalizedCandidate[];
  skipped: SkippedCandidate[];
  summary: CandidateSummary;
  generated_at: string | null;
}

export interface CandidateGenerateRequest {
  apply_risk_management?: boolean;
}

export interface PlaceOrderResult {
  symbol: string;
  strategy_type: string;
  qty: number;
  order_price: number | null;
  trigger_price: number | null;
  amount: number;
  status: string;
  remarks: string;
}

export interface CandidatePlaceResponse {
  placed: number;
  skipped: number;
  errors: string[];
  results: PlaceOrderResult[];
}
