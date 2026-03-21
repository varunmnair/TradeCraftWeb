import {
  AuthResponse,
  MeResponse,
  RegisterRequest,
  LoginRequest,
  BrokerConnectionResponse,
  BrokerConnectionCreate,
  SessionResponse,
  SessionStartRequest,
  SessionCreate,
  JobStatusResponse,
  JobListResponse,
  JobQueuedResponse,
  HoldingsLatestResponse,
  HoldingsAnalyzeRequest,
  PlanLatestResponse,
  PlanGenerateRequest,
  GTTOrdersResponse,
  GTTPreviewRequest,
  GTTConfirmRequest,
  GTTApplyRequest,
  GTTConfirmResponse,
  BrokerConnectResponse,
  BrokerStatusResponse,
  ZerodhaConnectResponse,
  ZerodhaStatusResponse,
  ServiceError,
  EntryStrategyListResponse,
  EntryStrategyFull,
  EntryStrategyUploadResponse,
  SuggestRevisionResponse,
  ApplyRevisionResponse,
  UploadHistoryResponse,
  VersionListResponse,
  RestoreVersionResponse,
  BulkSuggestRevisionResponse,
  BulkApplyRevisionResponse,
  ActiveConnectionResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class ApiClient {
  private token: string | null = null;
  private isRefreshing = false;
  private refreshSubscribers: ((token: string) => void)[] = [];

  constructor() {
    this.token = sessionStorage.getItem('access_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      sessionStorage.setItem('access_token', token);
    } else {
      sessionStorage.removeItem('access_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private subscribeToRefresh(callback: (token: string) => void) {
    this.refreshSubscribers.push(callback);
  }

  private onTokenRefreshed(token: string) {
    this.refreshSubscribers.forEach(callback => callback(token));
    this.refreshSubscribers = [];
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit & { retryRefresh?: boolean } = {},
    retryRefresh = true
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
      credentials: 'include',
    });

    if (response.status === 401 && retryRefresh) {
      if (this.isRefreshing) {
        return new Promise((resolve, reject) => {
          this.subscribeToRefresh((token: string) => {
            this.request<T>(endpoint, { ...options, retryRefresh: false })
              .then(resolve)
              .catch(reject);
          });
        });
      }

      this.isRefreshing = true;
      
      try {
        const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
        });

        if (refreshResponse.ok) {
          const data: AuthResponse = await refreshResponse.json();
          this.setToken(data.access_token);
          this.isRefreshing = false;
          this.onTokenRefreshed(data.access_token);
          
          return this.request<T>(endpoint, { ...options, retryRefresh: false });
        } else {
          this.setToken(null);
          window.location.href = '/login';
          throw new Error('Session expired');
        }
      } catch (error) {
        this.isRefreshing = false;
        this.setToken(null);
        window.location.href = '/login';
        throw error;
      }
    }

    if (!response.ok) {
      const error: ServiceError = await response.json().catch(() => ({
        error_code: 'unknown',
        message: 'An unknown error occurred',
        context: {},
        retryable: false,
      }));
      throw new Error(error.message || 'Request failed');
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  async register(data: RegisterRequest): Promise<MeResponse> {
    return this.request<MeResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async login(data: LoginRequest): Promise<AuthResponse> {
    const response = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    }, false);
    this.setToken(response.access_token);
    return response;
  }

  async logout(): Promise<void> {
    try {
      await this.request('/auth/logout', { method: 'POST' }, false);
    } finally {
      this.setToken(null);
    }
  }

  async me(): Promise<MeResponse> {
    return this.request<MeResponse>('/auth/me');
  }

  async listBrokerConnections(userId?: number): Promise<BrokerConnectionResponse[]> {
    const params = userId ? `?user_id=${userId}` : '';
    return this.request<BrokerConnectionResponse[]>(`/broker-connections${params}`);
  }

  async createBrokerConnection(data: BrokerConnectionCreate): Promise<BrokerConnectionResponse> {
    return this.request<BrokerConnectionResponse>('/broker-connections', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async connectUpstox(connectionId?: number): Promise<BrokerConnectResponse> {
    const params = connectionId ? `?connection_id=${connectionId}` : '';
    return this.request<BrokerConnectResponse>(`/brokers/upstox/connect${params}`);
  }

  async getUpstoxStatus(connectionId?: number): Promise<BrokerStatusResponse> {
    const params = connectionId ? `?connection_id=${connectionId}` : '';
    return this.request<BrokerStatusResponse>(`/brokers/upstox/status${params}`);
  }

  async connectZerodha(connectionId?: number): Promise<ZerodhaConnectResponse> {
    const params = connectionId ? `?connection_id=${connectionId}` : '';
    return this.request<ZerodhaConnectResponse>(`/brokers/zerodha/connect${params}`);
  }

  async getZerodhaStatus(connectionId?: number): Promise<ZerodhaStatusResponse> {
    const params = connectionId ? `?connection_id=${connectionId}` : '';
    return this.request<ZerodhaStatusResponse>(`/brokers/zerodha/status${params}`);
  }

  async disconnectUpstox(): Promise<{ disconnected: boolean; broker: string }> {
    return this.request<{ disconnected: boolean; broker: string }>('/brokers/upstox/disconnect', {
      method: 'POST',
    });
  }

  async disconnectZerodha(): Promise<{ disconnected: boolean; broker: string }> {
    return this.request<{ disconnected: boolean; broker: string }>('/brokers/zerodha/disconnect', {
      method: 'POST',
    });
  }

  async createSession(data: SessionCreate): Promise<SessionResponse> {
    return this.request<SessionResponse>('/api/v1/sessions', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async startSession(data: SessionStartRequest): Promise<SessionResponse> {
    return this.request<SessionResponse>('/session/start', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getSession(sessionId: string): Promise<SessionResponse> {
    return this.request<SessionResponse>(`/session/${sessionId}`);
  }

  async refreshSession(sessionId: string): Promise<SessionResponse> {
    return this.request<SessionResponse>(`/session/${sessionId}/refresh`, {
      method: 'POST',
    });
  }

  async setActiveConnection(brokerConnectionId: number): Promise<ActiveConnectionResponse> {
    return this.request<ActiveConnectionResponse>('/session/active-connection', {
      method: 'POST',
      body: JSON.stringify({ broker_connection_id: brokerConnectionId }),
    });
  }

  async getActiveConnection(): Promise<ActiveConnectionResponse> {
    return this.request<ActiveConnectionResponse>('/session/active-connection');
  }

  async getJob(jobId: number): Promise<JobStatusResponse> {
    return this.request<JobStatusResponse>(`/jobs/${jobId}`);
  }

  async listJobs(sessionId?: string): Promise<JobListResponse> {
    const params = sessionId ? `?session_id=${sessionId}` : '';
    return this.request<JobListResponse>(`/jobs${params}`);
  }

  async analyzeHoldings(data: HoldingsAnalyzeRequest): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/holdings/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getHoldingsLatest(sessionId: string): Promise<HoldingsLatestResponse> {
    return this.request<HoldingsLatestResponse>(`/holdings/${sessionId}/latest`);
  }

  async getHoldingsAnalyzeStatus(sessionId: string): Promise<{
    broker: string;
    market_data_ready: boolean;
    trades_ready: boolean;
    ready_to_analyze: boolean;
    blocking_reason: string | null;
    missing: { cmp: string[]; candles: string[]; trades: string[] };
  }> {
    return this.request<{
      broker: string;
      market_data_ready: boolean;
      trades_ready: boolean;
      ready_to_analyze: boolean;
      blocking_reason: string | null;
      missing: { cmp: string[]; candles: string[]; trades: string[] };
    }>(`/holdings/analyze/status?session_id=${sessionId}`);
  }

  async syncUpstoxTrades(days: number = 400): Promise<{ job_id: number }> {
    return this.request<{ job_id: number }>(`/brokers/upstox/trades/sync?days=${days}`, {
      method: 'POST',
    });
  }

  async uploadZerodhaTradebook(file: File): Promise<{
    rows_ingested: number;
    symbols_covered: number;
    errors: string[];
  }> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: HeadersInit = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE_URL}/brokers/zerodha/tradebook/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Upload failed' }));
      throw new Error(error.message || 'Upload failed');
    }

    return response.json();
  }

  async generatePlan(data: PlanGenerateRequest): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/plan/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getPlanLatest(sessionId: string): Promise<PlanLatestResponse> {
    return this.request<PlanLatestResponse>(`/plan/${sessionId}/latest`);
  }

  async generateMultiLevelPlan(data: PlanGenerateRequest): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/entries/multi-level/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getMultiLevelPlanLatest(sessionId: string): Promise<PlanLatestResponse> {
    return this.request<PlanLatestResponse>(`/entries/multi-level/${sessionId}/latest`);
  }

  async generateDynamicAvgPlan(sessionId: string): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/dynamic-avg/generate', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    });
  }

  async getDynamicAvgLatest(sessionId: string): Promise<PlanLatestResponse> {
    return this.request<PlanLatestResponse>(`/dynamic-avg/${sessionId}/latest`);
  }

  async generateDynamicAveragingPlan(data: PlanGenerateRequest): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/entries/dynamic-averaging/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getDynamicAveragingLatest(sessionId: string): Promise<PlanLatestResponse> {
    return this.request<PlanLatestResponse>(`/entries/dynamic-averaging/${sessionId}/latest`);
  }

  async purgeEntriesPlans(sessionId: string, strategyType?: 'multi_level' | 'dynamic_averaging'): Promise<{ purged_count: number; session_id: string }> {
    const params = strategyType ? `?strategy_type=${strategyType}` : '';
    return this.request<{ purged_count: number; session_id: string }>(`/entries/purge?session_id=${sessionId}${params}`, {
      method: 'DELETE',
    });
  }

  async applyRisk(sessionId: string, plan: Record<string, unknown>[]): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/risk/apply', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, plan }),
    });
  }

  async getRiskPlanLatest(sessionId: string): Promise<PlanLatestResponse> {
    return this.request<PlanLatestResponse>(`/risk/${sessionId}/latest`);
  }

  async getGTTOrders(sessionId: string): Promise<GTTOrdersResponse> {
    return this.request<GTTOrdersResponse>(`/gtt/${sessionId}`);
  }

  async previewGTT(data: GTTPreviewRequest): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/gtt/preview', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async confirmGTT(data: GTTConfirmRequest): Promise<GTTConfirmResponse> {
    return this.request<GTTConfirmResponse>('/gtt/confirm', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async applyGTT(data: GTTApplyRequest): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/gtt/apply', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteGTTOrders(sessionId: string, orderIds: string[]): Promise<{ deleted: string[]; count: number }> {
    return this.request<{ deleted: string[]; count: number }>('/gtt/delete', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, order_ids: orderIds }),
    });
  }

  async adjustGTTOrders(sessionId: string, orderIds: string[], targetVariance: number): Promise<{ adjusted: Array<{ GTT_ID: string; Symbol: string; old_trigger: number; new_trigger: number; old_variance: number; new_variance: number; status: string; reason?: string }>; failed: Array<{ GTT_ID: string; Symbol: string; status: string; reason: string }>; count: number }> {
    return this.request<{ adjusted: any[]; failed: any[]; count: number }>('/gtt/adjust', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, order_ids: orderIds, target_variance: targetVariance }),
    });
  }

  async chatWithAI(sessionId: string, message: string, context?: { page?: string; selectedSymbols?: string[] }): Promise<{ response: string; actions?: Array<{ type: string; params: Record<string, unknown> }> }> {
    return this.request<{ response: string; actions?: Array<{ type: string; params: Record<string, unknown> }> }>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, message, context }),
    });
  }

  async listEntryStrategies(): Promise<EntryStrategyListResponse> {
    return this.request<EntryStrategyListResponse>(`/entry-strategies`);
  }

  async getEntryStrategy(symbol: string): Promise<EntryStrategyFull> {
    return this.request<EntryStrategyFull>(`/entry-strategies/${encodeURIComponent(symbol)}`);
  }

  async deleteEntryStrategy(symbol: string): Promise<{ deleted: string; success: boolean }> {
    return this.request<{ deleted: string; success: boolean }>(`/entry-strategies/${encodeURIComponent(symbol)}`, {
      method: 'DELETE',
    });
  }

  async bulkDeleteEntryStrategies(symbols: string[]): Promise<{ deleted_count: number; not_found: string[]; success: boolean }> {
    return this.request<{ deleted_count: number; not_found: string[]; success: boolean }>(`/entry-strategies/bulk-delete`, {
      method: 'POST',
      body: JSON.stringify(symbols),
    });
  }

  async uploadEntryStrategyCSV(file: File): Promise<EntryStrategyUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: HeadersInit = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE_URL}/entry-strategies/upload-csv`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error: ServiceError = await response.json().catch(() => ({
        error_code: 'unknown',
        message: 'Upload failed',
        context: {},
        retryable: false,
      }));
      throw new Error(error.message || 'Upload failed');
    }

    return response.json();
  }

  async getEntryStrategyTemplate(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/entry-strategies/template.csv');
  }

  async suggestRevision(symbol: string, method?: string, pctAdjustment?: number): Promise<SuggestRevisionResponse> {
    const params = new URLSearchParams();
    if (method) params.append('method', method);
    if (pctAdjustment !== undefined) params.append('pct_adjustment', String(pctAdjustment));
    const query = params.toString();
    return this.request<SuggestRevisionResponse>(
      `/entry-strategies/${encodeURIComponent(symbol)}/suggest-revision${query ? '?' + query : ''}`
    );
  }

  async applyRevision(symbol: string, levels: Array<{ level_no: number; new_price: number }>): Promise<ApplyRevisionResponse> {
    return this.request<ApplyRevisionResponse>(
      `/entry-strategies/${encodeURIComponent(symbol)}/apply-revision`,
      {
        method: 'PATCH',
        body: JSON.stringify({ levels }),
      }
    );
  }

  async suggestRevisionBulk(symbols: string[], method?: string, pctAdjustment?: number): Promise<BulkSuggestRevisionResponse> {
    return this.request<BulkSuggestRevisionResponse>(
      `/entry-strategies/suggest-revision/bulk`,
      {
        method: 'POST',
        body: JSON.stringify({
          symbols,
          method: method || 'align_to_cmp',
          pct_adjustment: pctAdjustment || 5.0,
        }),
      }
    );
  }

  async applyRevisionBulk(updates: Array<{ symbol: string; levels: Array<{ level_no: number; new_price: number }> }>): Promise<BulkApplyRevisionResponse> {
    return this.request<BulkApplyRevisionResponse>(
      `/entry-strategies/apply-revision/bulk`,
      {
        method: 'PATCH',
        body: JSON.stringify({ updates }),
      }
    );
  }

  async getUploadHistory(limit?: number): Promise<UploadHistoryResponse> {
    const params = limit ? `?limit=${limit}` : '';
    return this.request<UploadHistoryResponse>(`/entry-strategies/uploads${params}`);
  }

  async getVersionHistory(symbol: string, limit?: number): Promise<VersionListResponse> {
    const params = limit ? `?limit=${limit}` : '';
    return this.request<VersionListResponse>(`/entry-strategies/${encodeURIComponent(symbol)}/versions${params}`);
  }

  async restoreVersion(symbol: string, versionId: number): Promise<RestoreVersionResponse> {
    return this.request<RestoreVersionResponse>(
      `/entry-strategies/${encodeURIComponent(symbol)}/restore/${versionId}`,
      {
        method: 'POST',
      }
    );
  }

  async getCmp(symbols: string[], tradeDate?: string): Promise<{
    trade_date: string;
    as_of_ts: string | null;
    data: Record<string, number>;
    missing: string[];
  }> {
    return this.request<{
      trade_date: string;
      as_of_ts: string | null;
      data: Record<string, number>;
      missing: string[];
    }>('/market/cmp', {
      method: 'POST',
      body: JSON.stringify({ symbols, trade_date: tradeDate }),
    });
  }

  async getCandles(symbols: string[], days: number = 400): Promise<{
    data: Record<string, Array<{
      trade_date: string;
      open: number;
      high: number;
      low: number;
      close: number;
      volume: number | null;
    }>>;
    missing_symbols: string[];
  }> {
    return this.request<{
      data: Record<string, Array<{
        trade_date: string;
        open: number;
        high: number;
        low: number;
        close: number;
        volume: number | null;
      }>>;
      missing_symbols: string[];
    }>('/market/candles', {
      method: 'POST',
      body: JSON.stringify({ symbols, days }),
    });
  }

  // Admin endpoints
  async getSymbolCatalogStatus(): Promise<{
    total_symbols: number;
    last_updated_at: string | null;
  }> {
    return this.request('/admin/symbol-catalog/status');
  }

  async importSymbolCatalog(file: File): Promise<{ job_id: number }> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: HeadersInit = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE_URL}/admin/symbol-catalog/import`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Upload failed' }));
      throw new Error(error.detail || error.message || 'Upload failed');
    }

    return response.json();
  }

  async refreshCMP(): Promise<{ job_id: number }> {
    return this.request<{ job_id: number }>('/admin/market-data/cmp/refresh', {
      method: 'POST',
    });
  }

  async getCMPStatus(): Promise<{
    total_symbols: number;
    cmp_present_count: number;
    last_cmp_job: {
      job_id: number;
      processed: number;
      succeeded: number;
      failed: number;
      updated_at: string | null;
    } | null;
  }> {
    return this.request('/admin/market-data/cmp/status');
  }

  async refreshOHLCV(days: number = 200): Promise<{ job_id: number }> {
    return this.request<{ job_id: number }>(`/admin/market-data/ohlcv/refresh?days=${days}`, {
      method: 'POST',
    });
  }

  async getOHLCVStatus(): Promise<{
    total_candles: number;
    symbols_with_candles: number;
    last_ohlcv_job: {
      job_id: number;
      processed_symbols: number;
      succeeded_symbols: number;
      failed_symbols: number;
      days: number;
      updated_at: string | null;
    } | null;
  }> {
    return this.request('/admin/market-data/ohlcv/status');
  }

  async getLastOHLCVJob(): Promise<{
    job_id: number | null;
    status: string;
    progress?: number;
    result?: {
      operation?: string;
      total_symbols?: number;
      processed_symbols?: number;
      succeeded_symbols?: number;
      failed_symbols?: number;
      failure_count?: number;
      failures?: Array<{ symbol: string; excerpt: string }>;
    };
    created_at?: string;
    updated_at?: string;
  }> {
    return this.request('/admin/market-data/ohlcv/last-job');
  }

  async getJobFailures(jobId: number): Promise<{
    job_id: number;
    job_type: string;
    operation: string | null;
    total: number;
    succeeded: number;
    failed: number;
    failures: Array<{ symbol: string; excerpt: string }>;
  }> {
    return this.request(`/admin/jobs/${jobId}/failures`);
  }
}

export const api = new ApiClient();
