/**
 * Create demo license keys for marketplace reviewers.
 *
 * Run with: npx ts-node scripts/create-demo-keys.ts
 * Or: cd web && npx tsx ../scripts/create-demo-keys.ts
 */

import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  console.error("Missing environment variables:");
  console.error("  SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL");
  console.error("  SUPABASE_SERVICE_ROLE_KEY");
  console.error("\nRun with: SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... npx tsx scripts/create-demo-keys.ts");
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

const DEMO_KEYS = [
  {
    key: "LK-DEMO-REVIEWER1",
    email: "reviewer1@anthropic.com",
    tier: "firm",
    status: "active",
  },
  {
    key: "LK-DEMO-REVIEWER2",
    email: "reviewer2@anthropic.com",
    tier: "firm",
    status: "active",
  },
  {
    key: "LK-DEMO-REVIEWER3",
    email: "reviewer3@anthropic.com",
    tier: "firm",
    status: "active",
  },
];

async function createDemoKeys() {
  console.log("Creating demo license keys...\n");

  for (const demo of DEMO_KEYS) {
    // Check if key already exists
    const { data: existing } = await supabase
      .from("licenses")
      .select("key")
      .eq("key", demo.key)
      .maybeSingle();

    if (existing) {
      console.log(`✓ ${demo.key} already exists`);
      continue;
    }

    const { error } = await supabase.from("licenses").insert({
      key: demo.key,
      email: demo.email,
      tier: demo.tier,
      status: demo.status,
      stripe_customer_id: "DEMO",
      stripe_subscription_id: "DEMO",
      trial_ends_at: null, // No trial - full access
    });

    if (error) {
      console.error(`✗ Failed to create ${demo.key}:`, error.message);
    } else {
      console.log(`✓ Created ${demo.key}`);
    }
  }

  console.log("\n--- Demo Keys for Marketplace Submission ---\n");
  for (const demo of DEMO_KEYS) {
    console.log(`License Key: ${demo.key}`);
    console.log(`  Tier: ${demo.tier}`);
    console.log(`  Status: ${demo.status} (full access, no QuickBooks required)`);
    console.log("");
  }

  console.log("These keys activate demo mode, which returns realistic sample data.");
  console.log("Reviewers can test all tools without a real QuickBooks account.");
}

createDemoKeys().catch(console.error);
