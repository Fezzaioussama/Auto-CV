import { AppShell } from "../layouts/AppShell";

export default function PrivacyPage() {
  return (
    <AppShell>
      <article className="prose max-w-3xl mx-auto px-6 py-16">
        <h1 className="font-display text-3xl font-extrabold mb-4">Privacy</h1>
        <p className="text-default-500">
          Auto-CV stores the account, jobs, and CV versions you save so you can come back to them.
          We never share your data, and you can export or delete everything at any time from the
          Account page.
        </p>
        <h2 className="font-display text-xl font-bold mt-8 mb-2">What we store</h2>
        <ul className="list-disc pl-6 text-default-600">
          <li>Account email, optional name, and password hash.</li>
          <li>Jobs you save (text, parsed analysis, status).</li>
          <li>CV documents and their versions.</li>
          <li>Cover letters / outreach drafts you save.</li>
        </ul>
        <h2 className="font-display text-xl font-bold mt-8 mb-2">Your rights</h2>
        <p className="text-default-500">
          Download all stored data or permanently delete your account from{" "}
          <a className="text-primary" href="/account">/account</a>. Email questions to
          support@auto-cv.app.
        </p>
      </article>
    </AppShell>
  );
}
