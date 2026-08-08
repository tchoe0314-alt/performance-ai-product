import { Suspense } from "react";

import { SupportPageClient } from "./SupportPageClient";


export default function SupportPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-slate-50" aria-busy="true" />}>
      <SupportPageClient />
    </Suspense>
  );
}
