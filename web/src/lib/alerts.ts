import { Resend } from "resend";

// Lightweight internal alerts for revenue-moving events (new paid, cancel).
// Posts to Slack if SLACK_ALERT_WEBHOOK is set, and always emails the admin as
// a reliable fallback. Fire-and-forget — never blocks or throws.

const SLACK = process.env.SLACK_ALERT_WEBHOOK;
const ADMIN_EMAIL = process.env.ADMIN_ALERT_EMAIL || "ryan@vasperacapital.com";

let resend: Resend | null = null;
function client(): Resend {
  if (!resend) resend = new Resend(process.env.RESEND_API_KEY);
  return resend;
}

export async function sendAlert(title: string, lines: string[]): Promise<void> {
  const body = lines.join("\n");
  const tasks: Promise<unknown>[] = [];

  if (SLACK) {
    tasks.push(
      fetch(SLACK, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: `*${title}*\n${body}` }),
      }).catch(() => {}),
    );
  }

  tasks.push(
    client()
      .emails.send({
        from: "AccountingQB Alerts <hello@accountingqb.com>",
        to: ADMIN_EMAIL,
        subject: title,
        text: `${title}\n\n${body}`,
      })
      .catch(() => {}),
  );

  await Promise.allSettled(tasks);
}
