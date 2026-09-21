import { AppShell } from "../layouts/AppShell";

export default function TermsPage() {
  return (
    <AppShell>
      <article className="prose max-w-3xl mx-auto px-6 py-16">
        <h1 className="font-display text-3xl font-extrabold mb-4">Terms of service</h1>
        <p className="text-default-500">
          Use Auto-CV in good faith. We don't invent facts on your CV — every rewrite is grounded in
          content you provided. You're responsible for verifying any text before submitting it to
          employers.
        </p>
        <h2 className="font-display text-xl font-bold mt-8 mb-2">Fair use</h2>
        <p className="text-default-500">
          API endpoints are rate-limited. Don't use automation to abuse the demo or LLM endpoints.
        </p>
        <h2 className="font-display text-xl font-bold mt-8 mb-2">No warranty</h2>
        <p className="text-default-500">
          Auto-CV is provided "as is". Match scores and recommendations are best-effort and not
          guarantees of interview success.
        </p>
      </article>
    </AppShell>
  );
}
