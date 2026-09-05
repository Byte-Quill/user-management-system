import type { ApplicationStatus } from "@/types/application";

export interface EmailActivity {
  sent_last_30_days: number;
  failed_last_30_days: number;
  recent: Array<{
    id: string;
    purpose: string;
    recipient: string;
    subject: string;
    status: string;
    user_email: string | null;
    created_at: string;
  }>;
}

export interface Analytics {
  kpis: {
    total_applications: number;
    submitted_last_30_days: number;
    users: number;
    pending_review: number;
  };
  approval_rate: number | null;
  pipeline: Record<ApplicationStatus, number>;
  email_activity: EmailActivity;
}
