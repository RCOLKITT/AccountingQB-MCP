export interface Testimonial {
  /** Real, permissioned name (first name + last initial is fine). */
  name: string;
  /** e.g. "Bookkeeper · 12 clients" or "Solo founder, Boston". */
  role: string;
  /** Their own words — keep it specific, not marketing-speak. */
  quote: string;
  /** A concrete outcome, e.g. "Cut month-end close from 2 days to 3 hours". Optional. */
  outcome?: string;
  /** Path to a headshot in /public (e.g. "/testimonials/jane.jpg"). Optional → initial avatar. */
  photoUrl?: string;
}

/* EMPTY until real, permissioned customer quotes exist.
 *
 * The testimonial wall renders NOTHING while this array is empty — no stand-in
 * faces, no invented names, no fabricated outcomes (audit D3.2/D3.1, and our own honesty
 * guardrail). To turn the section on: collect 5–8 named beta-tester quotes (first
 * name + role + a specific outcome, with written permission), drop a headshot in
 * /public/testimonials/, add entries below, and the homepage section appears
 * automatically. */
export const testimonials: Testimonial[] = [];
