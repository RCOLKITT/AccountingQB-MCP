import { getSupabase } from "./supabase";

export type EventType =
  | "stripe_webhook"
  | "oauth_connect"
  | "oauth_disconnect"
  | "oauth_refresh";

export interface LogEventParams {
  eventType: EventType;
  eventId?: string;
  licenseKey?: string;
  realmId?: string;
  stripeSubscriptionId?: string;
  action: string;
  payload?: Record<string, unknown>;
  success?: boolean;
  errorMessage?: string;
}

/**
 * Sanitizes payload by removing sensitive fields before logging.
 */
function sanitizePayload(
  payload: Record<string, unknown> | undefined
): Record<string, unknown> | null {
  if (!payload) return null;

  // Deep clone to avoid mutating original
  const sanitized = JSON.parse(JSON.stringify(payload));

  const sensitivePatterns = [
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "api_key",
    "secret",
    "token",
    "credential",
  ];

  function redactSensitive(obj: Record<string, unknown>): void {
    for (const key of Object.keys(obj)) {
      const lowerKey = key.toLowerCase();
      if (sensitivePatterns.some((pattern) => lowerKey.includes(pattern))) {
        obj[key] = "[REDACTED]";
      } else if (typeof obj[key] === "object" && obj[key] !== null && !Array.isArray(obj[key])) {
        redactSensitive(obj[key] as Record<string, unknown>);
      }
    }
  }

  redactSensitive(sanitized);
  return sanitized;
}

/**
 * Logs an event to the event_logs table.
 * Non-blocking: errors are logged to console but don't throw.
 */
export async function logEvent(params: LogEventParams): Promise<void> {
  try {
    const supabase = getSupabase();

    const { error } = await supabase.from("event_logs").insert({
      event_type: params.eventType,
      event_id: params.eventId || null,
      license_key: params.licenseKey || null,
      realm_id: params.realmId || null,
      stripe_subscription_id: params.stripeSubscriptionId || null,
      action: params.action,
      payload: sanitizePayload(params.payload),
      success: params.success ?? true,
      error_message: params.errorMessage || null,
      processed_at: new Date().toISOString(),
    });

    if (error) {
      // Log to console but don't throw — event logging should not block main flow
      console.error("Failed to log event:", error);
    }
  } catch (err) {
    console.error("Event logging error:", err);
  }
}

/**
 * Creates a Stripe webhook event logger for consistent success/failure tracking.
 */
export function createStripeEventLogger(
  eventId: string,
  eventType: string,
  subscriptionId?: string
) {
  return {
    success: (licenseKey?: string, payload?: Record<string, unknown>) => {
      return logEvent({
        eventType: "stripe_webhook",
        eventId,
        action: eventType,
        licenseKey,
        stripeSubscriptionId: subscriptionId,
        payload,
        success: true,
      });
    },
    failure: (errorMessage: string, payload?: Record<string, unknown>) => {
      return logEvent({
        eventType: "stripe_webhook",
        eventId,
        action: eventType,
        stripeSubscriptionId: subscriptionId,
        payload,
        success: false,
        errorMessage,
      });
    },
  };
}

/**
 * Logs an OAuth connection event.
 */
export async function logOAuthConnect(
  licenseKey: string,
  realmId: string,
  companyName: string | null,
  isReconnection: boolean = false
): Promise<void> {
  return logEvent({
    eventType: "oauth_connect",
    licenseKey,
    realmId,
    action: "quickbooks_connected",
    payload: {
      companyName,
      isReconnection,
    },
    success: true,
  });
}

/**
 * Logs an OAuth disconnection event.
 */
export async function logOAuthDisconnect(
  licenseKey: string,
  realmId: string,
  success: boolean = true,
  errorMessage?: string
): Promise<void> {
  return logEvent({
    eventType: "oauth_disconnect",
    licenseKey,
    realmId,
    action: "quickbooks_disconnected",
    success,
    errorMessage,
  });
}

/**
 * Logs an OAuth token refresh event.
 */
export async function logOAuthRefresh(
  licenseKey: string,
  realmId: string,
  success: boolean = true,
  errorMessage?: string
): Promise<void> {
  return logEvent({
    eventType: "oauth_refresh",
    licenseKey,
    realmId,
    action: "token_refreshed",
    success,
    errorMessage,
  });
}
