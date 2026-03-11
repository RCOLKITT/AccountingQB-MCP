import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!;

export const supabase = createClient(supabaseUrl, supabaseKey);

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
