import { createClient, SupabaseClient } from "@supabase/supabase-js";

let _supabase: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!_supabase) {
    _supabase = createClient(
      process.env.SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!,
    );
  }
  return _supabase;
}

export interface License {
  id: string;
  key: string;
  email: string;
  tier: "solopreneur" | "business" | "firm";
  stripe_customer_id: string;
  stripe_subscription_id: string;
  status: "active" | "trialing" | "canceled" | "expired";
  trial_ends_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OAuthToken {
  id: string;
  license_key: string;
  realm_id: string;
  company_name: string | null;
  access_token: string;
  refresh_token: string;
  token_expires_at: string;
  created_at: string;
  updated_at: string;
}

export interface UserProfile {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserLicense {
  id: string;
  user_id: string;
  license_key: string;
  role: "owner" | "member";
  created_at: string;
}

export interface ToolUsage {
  id: string;
  license_key: string;
  realm_id: string | null;
  tool_name: string;
  time_saved_minutes: number;
  invoked_at: string;
}

export interface UsageStatsCache {
  id: string;
  total_tool_calls: number;
  total_hours_saved: number;
  calls_this_week: number;
  active_licenses: number;
  updated_at: string;
}
