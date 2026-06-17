import Link from "next/link";

const sections = [
  {
    title: "Welcome To The Civora Private Pilot",
    body: [
      "Thanks for joining the Civora private pilot. This guide explains how to prepare a project, run the intended pilot workflow, understand source confidence, and get help when something looks wrong.",
      "Civora pilot outputs are review-preparation materials only. Keep normal professional review, source verification, client requirements, and field/submittal decisions outside Civora.",
    ],
  },
  {
    title: "What Civora Helps With",
    bullets: [
      "Organizing address, project setup, site constraints, source files, standards, and review notes in one workspace.",
      "Importing or drawing existing conditions, site objects, utilities, drainage areas, and other review candidates.",
      "Generating review-only civil system outputs, quantities, blockers, assumptions, and evidence packages.",
      "Showing source-confidence status so reviewers can see what needs confirmation before reliance.",
    ],
  },
  {
    title: "What Civora Does Not Do",
    bullets: [
      "Make professional engineering decisions or take legal responsibility for project outcomes.",
      "Replace survey/control, jurisdictional standards, utility records, client requirements, or responsible professional review.",
      "Turn address lookup, imagery, GIS, PDFs, or inferred geometry into trusted evidence without user review and accepted sources.",
      "Promise that exports, drawings, quantities, or calculations can be used outside the review-preparation workflow.",
    ],
  },
  {
    title: "Prepare Before Starting",
    bullets: [
      "Project address or location description.",
      "Survey/control, benchmark, datum, coordinate system, or terrain data if available.",
      "Applicable jurisdictional, owner, company, and utility standards.",
      "Known utility information, tie-ins, outlets, easements, floodplain/wetland constraints, access limits, and other site constraints.",
      "PDFs, survey CSVs, LandXML, GIS/GeoJSON, map images, source notes, sketches, or prior review packages.",
      "A clear note on whether confidential project data is allowed for this pilot account.",
    ],
  },
  {
    title: "Accepted Inputs",
    bullets: [
      "Address/location text for context and map lookup.",
      "PDF plan sheets for review-required extraction.",
      "Survey CSV and terrain/source files supported by the current upload tools.",
      "LandXML, GeoJSON, GIS/map sources, map images, screenshots, and manually drawn site objects when supported by the current workspace.",
      "Standards, utility notes, and source references entered or uploaded through the current pilot workflow.",
    ],
  },
  {
    title: "Step-By-Step Workflow",
    bullets: [
      "Import or enter the address/location, or start from a blank site.",
      "Complete setup with site size, boundary, coordinate context, and source evidence.",
      "Review existing conditions, uploaded files, survey/control status, standards, and source candidates.",
      "Draw or edit site objects such as boundary, buildings, roads, parking, drainage features, and utilities.",
      "Generate systems for the supported review scenario.",
      "Review blockers, missing inputs, stale outputs, source-confidence warnings, quantities, assumptions, and issue lists.",
      "Prepare a review package for qualified review, keeping field/submittal use outside Civora.",
    ],
  },
  {
    title: "Review-Only And Source Confidence",
    bullets: [
      "Review-only means the output is useful for checking, discussion, coordination, or package preparation, but still needs qualified review before reliance.",
      "Needs source means Civora is missing traceable evidence such as survey/control, standards, utility records, source files, dimensions, or accepted candidate data.",
      "Needs engineer review means a responsible professional or qualified reviewer must evaluate the output, assumptions, sources, and next action outside Civora before use.",
      "Blocked means Civora found a missing input, stale output, unsupported export, unresolved conflict, or source-confidence issue that prevents the next review step.",
    ],
  },
  {
    title: "Known Limitations",
    bullets: [
      "Advanced CAD handoff workflows are not externally verified.",
      "DWG export is not supported in the current pilot UI.",
      "Address lookup is context only and does not create trusted site objects by itself.",
      "GIS, imagery, PDF extraction, and inferred objects are candidates until reviewed and tied to accepted source evidence.",
      "Standards require user or company acceptance before they can be used as review evidence.",
      "Uploaded files may be limited by type, size, parsing support, coordinate metadata, and source quality.",
    ],
  },
  {
    title: "Support And Issue Reports",
    bullets: [
      "Use the in-app Report issue panel to copy user-safe metadata with project ID, current workflow step, visible blockers, system status, and your message.",
      "Send routine questions to support@civora.ai unless your pilot owner provided a different support path.",
      "For issues involving source trust, data exposure, exports, responsibility-boundary language, or possible reliance on unclear output, pause use of the affected output and mark the issue urgent.",
      "Include project ID, browser/device/OS, time with timezone, steps to reproduce, expected result, actual result, visible status text, and whether confidential data is involved.",
    ],
  },
  {
    title: "Data And Confidentiality Expectations",
    bullets: [
      "Use non-confidential or explicitly allowed test files unless your written pilot terms allow confidential project data.",
      "Only upload files and third-party data you have the right to use in the pilot.",
      "Do not send confidential project files, screenshots, client names, or restricted data through public support channels.",
      "Deletion, retention, backups, derived artifacts, logs, and support records follow the written pilot terms for the account. Until final terms are in place, avoid promises about deletion timing or backup handling.",
    ],
  },
  {
    title: "Safe Professional Disclaimer",
    body: [
      "Civora is private-pilot software for civil design support, source organization, coordination, and review-package preparation. It does not provide professional engineering services, replace responsible professional judgment, or authorize field/submittal use. Users remain responsible for verifying sources, standards, assumptions, calculations, geometry, quantities, conflicts, exports, and project decisions through the appropriate external review process.",
    ],
  },
];

export default function PilotStarterGuidePage() {
  return (
    <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900">
      <div className="mx-auto max-w-3xl">
        <Link href="/pilot" className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 hover:text-slate-900">
          Back to pilot hub
        </Link>
        <header className="mt-8 border-b border-slate-200 pb-8">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Email-ready guide</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight">Civora Private Pilot Starter Guide</h1>
          <p className="mt-4 text-base leading-7 text-slate-600">
            A shareable guide for controlled pilot users. Keep this page paired with the account-specific pilot terms, support path, and data policy.
          </p>
        </header>

        <div className="mt-8 space-y-6">
          {sections.map((section) => (
            <section key={section.title} className="border-b border-slate-200 pb-6">
              <h2 className="text-xl font-semibold">{section.title}</h2>
              {section.body?.map((paragraph) => (
                <p key={paragraph} className="mt-3 text-sm leading-7 text-slate-600">
                  {paragraph}
                </p>
              ))}
              {section.bullets ? (
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
                  {section.bullets.map((item) => (
                    <li key={item} className="flex gap-2">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </div>
      </div>
    </main>
  );
}
