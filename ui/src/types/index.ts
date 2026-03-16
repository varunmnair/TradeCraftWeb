export interface AuthUser {
  id: number;
  tenant_id: number;
  email: string;
  role: string;
  first_name?: string;
  last_name?: string;
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

export interface PlanLatestResponse {
  plan: Record<string, unknown>[];
  skipped: string[];
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
  updated_at: string;
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
}

export interface EntryStrategyListResponse {
  strategies: EntryStrategySummary[];
}

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
}

export interface ApplyRevisionItem {
  level_no: number;
  new_price: number;
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
}

export interface BulkSuggestRevisionResponse {
  suggestions: BulkSuggestRevisionItem[];
}

export interface BulkApplyRevisionItem {
  symbol: string;
  levels: ApplyRevisionItem[];
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
