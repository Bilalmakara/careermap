/**
 * CareerMap V2.0 Ortak TypeScript Veri Modelleri (Web & Mobil)
 */

export type UserRole = 'candidate' | 'admin';

export interface UserAccount {
  user_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active?: boolean;
}

export interface CandidateProfile {
  candidate_id: string;
  user_id?: string;
  full_name: string;
  title: string;
  email: string;
  phone: string;
  city: string;
  graduation_school: string;
  graduation_year: number;
  clinical_case_count: number;
  specialties: string[];
  experience_summary: string;
  work_preferences: {
    target_city: string;
    target_districts: string[];
    employment_type: string;
    preferred_clinic_types: string[];
    career_objective?: string;
  };
}

export interface CandidateDocument {
  document_id: string;
  candidate_id: string;
  document_type: string;
  file_name: string;
  file_path: string;
  secure_token: string;
  expires_at: string;
  view_count: number;
  secure_url: string;
  direct_download_url?: string;
}

export type ChannelType = 'email' | 'whatsapp' | 'phone' | 'website' | 'contact_form';

export interface EmployerContact {
  contact_type: ChannelType;
  contact_value: string;
  contact_category: string;
  source_url: string;
  discovery_method: string;
  evidence_text: string;
  verification_status: 'verified' | 'observed_on_source' | 'directory_observed' | 'needs_review';
}

export interface EmployerItem {
  employer_id: string;
  profession_id: string;
  city: string;
  district: string;
  name: string;
  employer_type: string;
  address: string;
  phone: string;
  phone_verification_status?: string;
  email: string;
  email_verification_status?: string;
  website: string;
  whatsapp_url?: string;
  contact_form_url?: string;
  confidence_score: number;
  confidence_level: string;
  available_channels: ChannelType[];
  is_reachable: boolean;
  match_score?: number;
  application_status?: string | null;
}

export type ApplicationStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'sent'
  | 'attempted'
  | 'waiting_reply'
  | 'interview'
  | 'rejected'
  | 'followup_needed';

export interface ApplicationPackage {
  application_id: string;
  employer: {
    employer_id: string;
    name: string;
    employer_type: string;
    district: string;
    city: string;
  };
  match: {
    match_score: number;
    match_reasons: string[];
    primary_channel: ChannelType;
    planned_channels: ChannelType[];
  };
  workflow: {
    primary_channel: ChannelType;
    steps: Array<{
      step_order: number;
      action_type: string;
      channel: string;
      description: string;
      wait_days_after: number;
    }>;
  };
  messages: {
    email: {
      subject: string;
      body: string;
      recipient: string;
      attachment_name: string;
    };
    whatsapp_model_b: {
      body: string;
      secure_url: string;
    };
    whatsapp_model_c: {
      body: string;
      attachment_instructions: string;
    };
    whatsapp_followup: {
      body: string;
      suggested_wait_days: number;
    };
    phone_script: {
      target_phone: string;
      body: string;
    };
    contact_form: {
      target_url: string;
      subject: string;
      body: string;
    };
    whatsapp_phone?: string;
    whatsapp_handoff_link_b?: string;
  };
}

export interface ChannelAttempt {
  attempt_id: string;
  application_id: string;
  channel: ChannelType;
  contact_value: string;
  status: string;
  notes: string;
  attempted_at: string;
}

export interface ApplicationRecord {
  application_id: string;
  employer_id: string;
  employer_name: string;
  employer_type: string;
  district: string;
  position_title: string;
  status: ApplicationStatus;
  match_score: number;
  match_reasons: string[];
  primary_channel: ChannelType;
  orchestration_step: number;
  email?: string;
  phone?: string;
  whatsapp_url?: string;
  channel_attempts?: ChannelAttempt[];
  created_at: string;
  updated_at: string;
}

export interface CRMDashboardData {
  candidate_id: string;
  metrics: {
    target_employers: number;
    applications_sent: number;
    replies_or_active: number;
    interviews: number;
    drafts: number;
    pending_approval: number;
  };
  applications: ApplicationRecord[];
}

export type ResearchJobStatus =
  | 'queued'
  | 'discovering'
  | 'enriching'
  | 'verifying'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'cancelled';

export interface ResearchJob {
  research_job_id: string;
  user_id: string;
  profession_id: string;
  profession_name: string;
  employer_types: string[];
  country: string;
  city: string;
  districts: string[];
  keywords: string;
  status: ResearchJobStatus;
  total_found: number;
  contacts_found: number;
  verified_count: number;
  progress_percent: number;
  progress_stage: string;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface ProfessionConfig {
  id: string;
  name: string;
  description: string;
  icon: string;
  supported_cities: Record<string, string[]>;
  employer_types: Array<{ id: string; label: string }>;
  is_active: boolean;
  adapter_status: 'ready' | 'planned';
  adapter_message: string;
}

export interface BatchPrepareRequest {
  employer_ids: string[];
  position_title?: string;
}


