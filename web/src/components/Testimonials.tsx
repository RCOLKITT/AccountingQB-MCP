import Image from "next/image";
import { testimonials } from "@/lib/testimonials";

/* Customer testimonial wall (audit D3.2 story proof / D3.1 quantity proof).
   Renders ONLY when real, permissioned quotes exist — empty data → nothing shows,
   so the site never ships placeholder or invented social proof. Populate
   src/lib/testimonials.ts to activate. */
export default function Testimonials() {
  if (testimonials.length === 0) return null;

  return (
    <section className="relative py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="text-center">
          <div className="mb-4 inline-flex items-center rounded-full border border-cyan-500/20 bg-cyan-500/[0.08] px-3 py-1 text-xs font-medium text-cyan-300">
            What customers say
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Real books, real owners
          </h2>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {testimonials.map((t) => (
            <figure key={`${t.name}-${t.role}`} className="flex flex-col rounded-2xl border border-white/[0.08] bg-[#131a2e] p-6">
              {t.outcome && (
                <figcaption className="mb-3 inline-flex w-fit rounded-md bg-cyan-500/[0.1] px-2.5 py-1 text-[12px] font-semibold text-cyan-300">
                  {t.outcome}
                </figcaption>
              )}
              <blockquote className="flex-1 text-[15px] leading-relaxed text-gray-300">
                &ldquo;{t.quote}&rdquo;
              </blockquote>
              <div className="mt-5 flex items-center gap-3">
                {t.photoUrl ? (
                  <div className="relative h-10 w-10 overflow-hidden rounded-full ring-1 ring-white/10">
                    <Image src={t.photoUrl} alt={t.name} fill sizes="40px" className="object-cover" />
                  </div>
                ) : (
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/[0.06] text-sm font-semibold text-gray-300">
                    {t.name.charAt(0)}
                  </div>
                )}
                <div>
                  <div className="text-sm font-semibold text-white">{t.name}</div>
                  <div className="text-[13px] text-gray-500">{t.role}</div>
                </div>
              </div>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
