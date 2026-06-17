import Link from "next/link";

const sections = [
  {
    id: "onboarding",
    title: "Private Pilot Onboarding",
    body: [
      "Civora helps pilot users organize civil site intent, candidate geometry, engineering signals, assumptions, blockers, and review-package materials.",
      "Start with a project name, address or blank site, site size or boundary, locked site, objects, available survey/GIS/terrain inputs, standards review, system runs, blocker review, and a review package export.",
    ],
  },
  {
    id: "limitations",
    title: "Pilot Limitations",
    body: [
      "Civora is private-pilot software. Civil 3D workflows are not externally verified, DWG export is unsupported, standards require user or company acceptance, and survey/control, datum, benchmark, and source evidence are required for source-backed reviewer evaluation.",
      "Address lookup, GIS, imagery detection, inferred objects, and visual previews are review context only unless backed by accepted source evidence. Users must have rights to upload or connect map/GIS sources before importing them.",
    ],
  },
  {
    id: "operations",
    title: "Controlled Pilot Operations",
    body: [
      "Pilot use should stay within approved test or feasibility scope, use an assigned support path, and report issues with project ID, workflow step, visible status text, inputs, expected result, and actual result.",
      "Users should pause reliance on any output marked blocked, missing input, stale, draft/review-required, visual preview only, or needs review.",
    ],
  },
  {
    id: "responsibility",
    title: "Product Foundation And Responsibility",
    body: [
      "Civora is a review workspace and planning copilot for early civil layout and feasibility. It is not an engineer of record, approval authority, permitting agent, or construction release system.",
      "Civora never stamps, seals, signs, certifies, approves construction, submits construction documents, or acts as engineer of record. Only the licensed engineer or user can review, approve, stamp, seal, sign, submit, and take legal responsibility.",
    ],
  },
];

export default function PilotPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900">
      <div className="mx-auto max-w-4xl">
        <Link
          href="/"
          className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 hover:text-slate-900"
        >
          Back to Civora
        </Link>
        <header className="mt-8 border-b border-slate-200 pb-8">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Pilot guide
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight">
            Civora Pilot Onboarding And Support
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
            User-facing pilot guidance for setup, known limitations, support
            intake, and the engineer responsibility boundary.
          </p>
        </header>

        <nav className="mt-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {sections.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              {section.title}
            </a>
          ))}
        </nav>

        <div className="mt-8 space-y-5">
          {sections.map((section) => (
            <section
              key={section.id}
              id={section.id}
              className="rounded-lg border border-slate-200 bg-white p-5"
            >
              <h2 className="text-xl font-semibold">{section.title}</h2>
              <div className="mt-3 space-y-3 text-sm leading-7 text-slate-600">
                {section.body.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </section>
          ))}
        </div>

        <section className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-5">
          <h2 className="text-lg font-semibold text-amber-950">Support Reports</h2>
          <p className="mt-2 text-sm leading-7 text-amber-900">
            Use the in-app Report issue button to copy a diagnostic summary with
            project ID, active workflow step, visible blockers, and your message.
            Routine support can go to{" "}
            <a className="font-semibold underline" href="mailto:support@civora.ai">
              support@civora.ai
            </a>
            .
          </p>
        </section>
      </div>
    </main>
  );
}
