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
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('access_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('access_token', token);
    } else {
      localStorage.removeItem('access_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
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
    });

    if (response.status === 401) {
      this.setToken(null);
      window.location.href = '/login';
      throw new Error('Unauthorized');
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

  // Auth
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
    });
    this.setToken(response.access_token);
    return response;
  }

  async logout(): Promise<void> {
    await this.request('/auth/logout', { method: 'POST' });
    this.setToken(null);
  }

  async me(): Promise<MeResponse> {
    return this.request<MeResponse>('/auth/me');
  }

  // Broker Connections
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

  // Sessions
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

  // Jobs
  async getJob(jobId: number): Promise<JobStatusResponse> {
    return this.request<JobStatusResponse>(`/jobs/${jobId}`);
  }

  async listJobs(sessionId?: string): Promise<JobListResponse> {
    const params = sessionId ? `?session_id=${sessionId}` : '';
    return this.request<JobListResponse>(`/jobs${params}`);
  }

  // Holdings
  async analyzeHoldings(data: HoldingsAnalyzeRequest): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/holdings/analyze', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getHoldingsLatest(sessionId: string): Promise<HoldingsLatestResponse> {
    return this.request<HoldingsLatestResponse>(`/holdings/${sessionId}/latest`);
  }

  // Plan
  async generatePlan(data: PlanGenerateRequest): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/plan/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getPlanLatest(sessionId: string): Promise<PlanLatestResponse> {
    return this.request<PlanLatestResponse>(`/plan/${sessionId}/latest`);
  }

  // Dynamic Averaging
  async generateDynamicAvgPlan(sessionId: string): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/dynamic-avg/generate', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    });
  }

  async getDynamicAvgLatest(sessionId: string): Promise<PlanLatestResponse> {
    return this.request<PlanLatestResponse>(`/dynamic-avg/${sessionId}/latest`);
  }

  // Risk
  async applyRisk(sessionId: string, plan: Record<string, unknown>[]): Promise<JobQueuedResponse> {
    return this.request<JobQueuedResponse>('/risk/apply', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, plan }),
    });
  }

  async getRiskPlanLatest(sessionId: string): Promise<PlanLatestResponse> {
    return this.request<PlanLatestResponse>(`/risk/${sessionId}/latest`);
  }

  // GTT
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

  // Entry Strategies
  async listEntryStrategies(sessionId: string): Promise<EntryStrategyListResponse> {
    return this.request<EntryStrategyListResponse>(`/entry-strategies?session_id=${sessionId}`);
  }

  async getEntryStrategy(symbol: string, sessionId: string): Promise<EntryStrategyFull> {
    return this.request<EntryStrategyFull>(`/entry-strategies/${encodeURIComponent(symbol)}?session_id=${sessionId}`);
  }

  async deleteEntryStrategy(symbol: string, sessionId: string): Promise<{ deleted: string; success: boolean }> {
    return this.request<{ deleted: string; success: boolean }>(`/entry-strategies/${encodeURIComponent(symbol)}?session_id=${sessionId}`, {
      method: 'DELETE',
    });
  }

  async bulkDeleteEntryStrategies(symbols: string[], sessionId: string): Promise<{ deleted_count: number; not_found: string[]; success: boolean }> {
    return this.request<{ deleted_count: number; not_found: string[]; success: boolean }>(`/entry-strategies/bulk-delete?session_id=${sessionId}`, {
      method: 'POST',
      body: JSON.stringify(symbols),
    });
  }

  async uploadEntryStrategyCSV(file: File, sessionId: string): Promise<EntryStrategyUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: HeadersInit = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${API_BASE_URL}/entry-strategies/upload-csv?session_id=${sessionId}`, {
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

  async suggestRevision(symbol: string, sessionId: string, method?: string, pctAdjustment?: number): Promise<SuggestRevisionResponse> {
    const params = new URLSearchParams();
    params.append('session_id', sessionId);
    if (method) params.append('method', method);
    if (pctAdjustment !== undefined) params.append('pct_adjustment', String(pctAdjustment));
    const query = params.toString();
    return this.request<SuggestRevisionResponse>(
      `/entry-strategies/${encodeURIComponent(symbol)}/suggest-revision?${query}`
    );
  }

  async applyRevision(symbol: string, sessionId: string, levels: Array<{ level_no: number; new_price: number }>): Promise<ApplyRevisionResponse> {
    return this.request<ApplyRevisionResponse>(
      `/entry-strategies/${encodeURIComponent(symbol)}/apply-revision?session_id=${sessionId}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ levels }),
      }
    );
  }

  async suggestRevisionBulk(symbols: string[], sessionId: string, method?: string, pctAdjustment?: number): Promise<BulkSuggestRevisionResponse> {
    return this.request<BulkSuggestRevisionResponse>(
      `/entry-strategies/suggest-revision/bulk?session_id=${sessionId}`,
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

  async applyRevisionBulk(updates: Array<{ symbol: string; levels: Array<{ level_no: number; new_price: number }> }>, sessionId: string): Promise<BulkApplyRevisionResponse> {
    return this.request<BulkApplyRevisionResponse>(
      `/entry-strategies/apply-revision/bulk?session_id=${sessionId}`,
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

  async getVersionHistory(symbol: string, sessionId: string, limit?: number): Promise<VersionListResponse> {
    const params = new URLSearchParams();
    params.append('session_id', sessionId);
    if (limit) params.append('limit', String(limit));
    return this.request<VersionListResponse>(`/entry-strategies/${encodeURIComponent(symbol)}/versions?${params.toString()}`);
  }

  async restoreVersion(symbol: string, sessionId: string, versionId: number): Promise<RestoreVersionResponse> {
    return this.request<RestoreVersionResponse>(
      `/entry-strategies/${encodeURIComponent(symbol)}/restore/${versionId}?session_id=${sessionId}`,
      {
        method: 'POST',
      }
    );
  }
}

export const api = new ApiClient();
