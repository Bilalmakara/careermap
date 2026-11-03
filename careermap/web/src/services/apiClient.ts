/**
 * CareerMap V2.0 Ortak REST API İstemcisi (Web & React Native / Expo Uyumlu)
 */
import {
  CandidateProfile,
  CandidateDocument,
  EmployerItem,
  ApplicationPackage,
  ApplicationRecord,
  CRMDashboardData,
  UserAccount
} from '../types/careermap';

export class CareerMapApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = '') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  setToken(token: string) {
    this.token = token;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = new Headers(options.headers || {});

    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }

    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      const errText = await res.text();
      let message = `API Hatası: ${res.status}`;
      try {
        const errJson = JSON.parse(errText);
        message = errJson.detail || message;
      } catch {}
      throw new Error(message);
    }

    return res.json() as Promise<T>;
  }

  // Auth
  async login(email: string, password: string): Promise<{ access_token: string; user: UserAccount }> {
    return this.request<{ access_token: string; user: UserAccount }>('/api/v2/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });
  }

  async getMe(): Promise<{ user: UserAccount }> {
    return this.request<{ user: UserAccount }>('/api/v2/auth/me');
  }

  // Candidate Profile & CV
  async getCandidateProfile(): Promise<{ profile: CandidateProfile }> {
    return this.request<{ profile: CandidateProfile }>('/api/v2/candidate/profile');
  }

  async updateCandidateProfile(data: Partial<CandidateProfile>): Promise<{ profile: CandidateProfile }> {
    return this.request<{ profile: CandidateProfile }>('/api/v2/candidate/profile', {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }

  async getCandidateCvs(): Promise<{ documents: CandidateDocument[] }> {
    return this.request<{ documents: CandidateDocument[] }>('/api/v2/candidate/cv');
  }

  // Employers
  async listEmployers(params: {
    city?: string;
    district?: string;
    employer_type?: string;
    has_email?: boolean;
    has_whatsapp?: boolean;
    has_website?: boolean;
    reachable_only?: boolean;
    q?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<{ total: number; page: number; items: EmployerItem[] }> {
    const qp = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) qp.append(k, String(v));
    });
    return this.request<{ total: number; page: number; items: EmployerItem[] }>(`/api/v2/employers?${qp.toString()}`);
  }

  async getEmployerDetail(employerId: string): Promise<{ employer: any }> {
    return this.request<{ employer: any }>(`/api/v2/employers/${employerId}`);
  }

  // Applications & CRM
  async getCRMDashboard(): Promise<{ dashboard: CRMDashboardData }> {
    return this.request<{ dashboard: CRMDashboardData }>('/api/v2/applications/dashboard');
  }

  async listApplications(status?: string): Promise<{ items: ApplicationRecord[] }> {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return this.request<{ items: ApplicationRecord[] }>(`/api/v2/applications${q}`);
  }

  async prepareApplication(employerId: string, positionTitle: string = 'Diş Hekimi'): Promise<ApplicationPackage> {
    return this.request<ApplicationPackage>(`/api/v2/applications/prepare/${employerId}?position_title=${encodeURIComponent(positionTitle)}`, {
      method: 'POST'
    });
  }

  async approveApplication(applicationId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/v2/applications/${applicationId}/approve`, {
      method: 'POST'
    });
  }

  async recordChannelAction(
    applicationId: string,
    channel: string,
    contactValue: string,
    notes: string = ''
  ): Promise<{ status: string; attempt_id: string }> {
    return this.request<{ status: string; attempt_id: string }>(`/api/v2/applications/${applicationId}/action`, {
      method: 'POST',
      body: JSON.stringify({
        channel,
        contact_value: contactValue,
        action_status: 'confirmed_by_user',
        notes
      })
    });
  }

  async updateApplicationStatus(
    applicationId: string,
    newStatus: string,
    notes: string = ''
  ): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/api/v2/applications/${applicationId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ new_status: newStatus, notes })
    });
  }

  // Research Engine (V2.1)
  async listProfessions(): Promise<{ professions: any[] }> {
    return this.request<{ professions: any[] }>('/api/v2/research/professions');
  }

  async startResearchJob(payload: {
    profession_id: string;
    city: string;
    districts?: string[];
    employer_types?: string[];
    keywords?: string;
  }): Promise<{ job_id: string; job: any }> {
    return this.request<{ job_id: string; job: any }>('/api/v2/research/jobs', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  async listResearchJobs(): Promise<{ jobs: any[] }> {
    return this.request<{ jobs: any[] }>('/api/v2/research/jobs');
  }

  async getResearchJob(jobId: string): Promise<{ job: any }> {
    return this.request<{ job: any }>(`/api/v2/research/jobs/${jobId}`);
  }

  async getJobResults(
    jobId: string,
    filters: { filter_reachable?: boolean; filter_email?: boolean; filter_whatsapp?: boolean; filter_unapplied?: boolean } = {}
  ): Promise<{ total: number; items: any[] }> {
    const qp = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => {
      if (v) qp.append(k, 'true');
    });
    return this.request<{ total: number; items: any[] }>(`/api/v2/research/jobs/${jobId}/results?${qp.toString()}`);
  }

  async batchPrepareApplications(payload: { employer_ids: string[]; position_title?: string }): Promise<any> {
    return this.request<any>('/api/v2/applications/batch-prepare', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  // Admin
  async getAdminStats(): Promise<any> {
    return this.request<any>('/api/v2/admin/stats');
  }
}

export const api = new CareerMapApiClient();

