import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Button,
  Card,
  CardBody,
  Chip,
  Textarea,
} from "@heroui/react";
import { AppShell } from "../layouts/AppShell";
import { api, apiErrorMessage } from "../lib/api";

type Analysis = {
  overall_score?: number;
  match_percentage?: number;
  skills_match?: { matched?: string[]; missing?: string[] };
};

export default function DemoPage() {
  const [jobText, setJobText] = useState("");
  const [cvText, setCvText] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [usedSample, setUsedSample] = useState(false);

  async function loadSample() {
    try {
      const r = await api.get<{ job: { text: string } }>("/api/sample-job");
      setJobText((r.data.job?.text || "").trim());
    } catch {
      /* ignore */
    }
  }

  async function run() {
    if (!jobText.trim()) {
      setStatus("Paste a job description first.");
      return;
    }
    setBusy(true);
    setStatus("Analysing…");
    setAnalysis(null);
    try {
      const r = await api.post<{
        success: boolean;
        analysis: Analysis;
        used_sample_cv: boolean;
      }>("/api/demo", { job_text: jobText, cv_latex: cvText });
      setAnalysis(r.data.analysis || {});
      setUsedSample(r.data.used_sample_cv);
      setStatus("");
    } catch (err) {
      setStatus(apiErrorMessage(err, "Demo unavailable. Try again later."));
    } finally {
      setBusy(false);
    }
  }

  const score = analysis?.overall_score ?? analysis?.match_percentage ?? null;
  const matched = analysis?.skills_match?.matched || [];
  const missing = analysis?.skills_match?.missing || [];

  return (
    <AppShell>
      <section className="max-w-3xl mx-auto px-6 py-12">
        <div className="text-center mb-8">
          <Chip color="primary" variant="flat">
            Free demo · no sign-up
          </Chip>
          <h1 className="font-display text-3xl font-extrabold mt-3">
            See how your CV matches an offer
          </h1>
          <p className="text-default-500 mt-2">
            Paste a job description. We analyse the match against a sample CV — or paste your own.
            Editing, rewriting and PDF/Word export unlock when you create a free account.
          </p>
        </div>

        <Card className="border border-default-200">
          <CardBody className="p-6 space-y-4">
            <Textarea
              label="Job description"
              minRows={6}
              value={jobText}
              onValueChange={setJobText}
              placeholder="Paste the job offer here…"
            />
            <details className="text-sm">
              <summary className="cursor-pointer text-default-600">
                Optional: paste your own CV text instead of the sample
              </summary>
              <Textarea
                className="mt-3"
                minRows={5}
                value={cvText}
                onValueChange={setCvText}
                placeholder="Paste your CV as plain text or LaTeX (optional)"
              />
            </details>
            <div className="flex flex-wrap gap-3 items-center">
              <Button color="primary" isLoading={busy} onPress={run}>
                Analyse match
              </Button>
              <Button variant="bordered" onPress={loadSample}>
                Load a sample offer
              </Button>
              <span className="text-default-500 text-sm">{status}</span>
            </div>
          </CardBody>
        </Card>

        {analysis && (
          <>
            <Card className="border border-default-200 mt-4">
              <CardBody className="p-6">
                <div className="flex justify-between items-center flex-wrap gap-2">
                  <h2 className="font-display text-xl font-bold">Match score</h2>
                  <Chip size="lg" color="primary" variant="flat">
                    {score == null ? "—" : `${score}%`}
                  </Chip>
                </div>
                <p className="text-default-500 text-sm mt-1">
                  {usedSample
                    ? "Analysed against a built-in sample CV. Paste your own above for a personalised result."
                    : "Analysed against the CV you provided."}
                </p>
                <div className="grid md:grid-cols-2 gap-4 mt-4">
                  <div>
                    <h3 className="text-success-600 font-semibold text-sm mb-2">Matched skills</h3>
                    <div className="flex flex-wrap gap-1">
                      {matched.slice(0, 20).map((s) => (
                        <Chip key={s} size="sm" variant="flat" color="success">
                          {s}
                        </Chip>
                      ))}
                      {matched.length === 0 && <span className="text-default-400">—</span>}
                    </div>
                  </div>
                  <div>
                    <h3 className="text-danger-600 font-semibold text-sm mb-2">Missing / to add</h3>
                    <div className="flex flex-wrap gap-1">
                      {missing.slice(0, 20).map((s) => (
                        <Chip key={s} size="sm" variant="flat" color="danger">
                          {s}
                        </Chip>
                      ))}
                      {missing.length === 0 && (
                        <span className="text-default-400">None — great coverage!</span>
                      )}
                    </div>
                  </div>
                </div>
              </CardBody>
            </Card>

            <Card className="bg-primary-50 border border-primary-100 mt-4">
              <CardBody className="p-6 text-center">
                <h3 className="font-display text-lg font-bold">
                  Want the rewritten CV, cover letter and exports?
                </h3>
                <p className="text-default-500 mt-1">
                  Create a free account to tailor and download your CV.
                </p>
                <div className="flex justify-center gap-3 mt-4">
                  <Button as={Link} to="/register" color="primary">
                    Create free account
                  </Button>
                  <Button as={Link} to="/login" variant="bordered">
                    Sign in
                  </Button>
                </div>
              </CardBody>
            </Card>
          </>
        )}
      </section>
    </AppShell>
  );
}
