import { useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Chip,
  Divider,
  Input,
  Progress,
  Select,
  SelectItem,
  Tab,
  Tabs,
  Textarea,
} from "@heroui/react";
import { AppShell } from "../layouts/AppShell";
import { api, apiErrorMessage } from "../lib/api";
import { useToast } from "../contexts/ToastContext";

type JobAnalysis = {
  text: string;
  raw_text: string;
  skills: string[];
  requirements: string[];
  qualifications: string[];
};

type SkillsMatch = { matched: string[]; missing: string[] };
type AtsAnalysis = {
  total_skills?: number;
  ats_score?: number;
  requirements?: Array<{ text: string; covered?: boolean }>;
  priorities?: string[];
  weak_sections?: string[];
};
type CvAnalysis = {
  overall_score?: number;
  match_percentage?: number;
  skills_match?: SkillsMatch;
  recommendations?: string[];
  ats?: AtsAnalysis;
};
type SectionDiff = {
  section: string;
  before: string;
  after: string;
  reason?: string;
};

type Template = { id: string; label?: string; name?: string };

function readAsText(file: File): Promise<string> {
  return new Promise((res, rej) => {
    const reader = new FileReader();
    reader.onload = () => res(String(reader.result || ""));
    reader.onerror = () => rej(reader.error);
    reader.readAsText(file);
  });
}

export default function OptimizerPage() {
  const { push } = useToast();

  // Step 1 — job
  const [jobInput, setJobInput] = useState("");
  const [jobUrl, setJobUrl] = useState("");
  const [jobAnalysis, setJobAnalysis] = useState<JobAnalysis | null>(null);
  const [jobBusy, setJobBusy] = useState(false);

  // Step 2 — CV
  const [cvLatex, setCvLatex] = useState("");
  const [cvBusy, setCvBusy] = useState(false);
  const [cvExtractStatus, setCvExtractStatus] = useState<string>("");

  // Step 3 — optimization
  const [language, setLanguage] = useState<string>("en");
  const [template, setTemplate] = useState<string>("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [optBusy, setOptBusy] = useState(false);
  const [analysis, setAnalysis] = useState<CvAnalysis | null>(null);
  const [optimizedLatex, setOptimizedLatex] = useState("");
  const [sectionDiffs, setSectionDiffs] = useState<SectionDiff[]>([]);
  const [acceptedSections, setAcceptedSections] = useState<Record<number, boolean>>({});
  const [proposedAdditions, setProposedAdditions] = useState<string[]>([]);

  // PDF preview
  const [pdfBusy, setPdfBusy] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const pdfBlobRef = useRef<string | null>(null);

  // Save to workspace
  const [saveName, setSaveName] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);

  const jobFileRef = useRef<HTMLInputElement>(null);
  const cvFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .get<{ templates: Template[] }>("/api/templates")
      .then((r) => {
        const list = r.data.templates || [];
        setTemplates(list);
        if (!template && list.length) setTemplate(list[0].id);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    return () => {
      if (pdfBlobRef.current) URL.revokeObjectURL(pdfBlobRef.current);
    };
  }, []);

  // -----------------------------------------------------------------
  // Job description
  // -----------------------------------------------------------------

  async function parseJob() {
    if (!jobInput.trim()) {
      push("Paste a job description first.", "error");
      return;
    }
    setJobBusy(true);
    try {
      const r = await api.post<{ success: boolean } & JobAnalysis>("/api/parse-job", {
        text: jobInput,
      });
      setJobAnalysis(r.data);
      push("Job description parsed.", "success");
    } catch (err) {
      push(apiErrorMessage(err, "Could not parse the job."), "error");
    } finally {
      setJobBusy(false);
    }
  }

  async function fetchJobFromUrl() {
    if (!jobUrl.trim()) return;
    setJobBusy(true);
    try {
      const r = await api.post<{ text: string }>("/api/fetch-job-url", { url: jobUrl });
      setJobInput(r.data.text || "");
      push("Job posting fetched.", "success");
    } catch (err) {
      push(apiErrorMessage(err, "Could not fetch the URL."), "error");
    } finally {
      setJobBusy(false);
    }
  }

  async function onJobFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await readAsText(file);
      setJobInput(text);
    } catch {
      push("Could not read the file.", "error");
    } finally {
      e.target.value = "";
    }
  }

  async function loadSampleJob() {
    try {
      const r = await api.get<{ job: { text: string } }>("/api/sample-job");
      setJobInput((r.data.job?.text || "").trim());
    } catch {
      /* ignore */
    }
  }

  // -----------------------------------------------------------------
  // CV
  // -----------------------------------------------------------------

  async function onCvFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setCvBusy(true);
    setCvExtractStatus("Extracting CV content…");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("language", language);
      if (template) form.append("template", template);
      const r = await api.post<{ latex: string; source_format: string }>(
        "/api/extract-cv",
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setCvLatex(r.data.latex || "");
      setCvExtractStatus(`Extracted from ${r.data.source_format.toUpperCase()}.`);
    } catch (err) {
      setCvExtractStatus("");
      push(apiErrorMessage(err, "Could not extract the CV."), "error");
    } finally {
      setCvBusy(false);
      e.target.value = "";
    }
  }

  async function loadSampleCV() {
    try {
      const r = await api.get<{ cv: string }>("/api/sample-cv");
      setCvLatex(r.data.cv || "");
    } catch {
      /* ignore */
    }
  }

  // -----------------------------------------------------------------
  // Optimize
  // -----------------------------------------------------------------

  async function optimize() {
    if (!jobAnalysis) {
      push("Parse the job first.", "error");
      return;
    }
    if (!cvLatex.trim()) {
      push("Add your CV first.", "error");
      return;
    }
    setOptBusy(true);
    try {
      const r = await api.post<{
        success: boolean;
        analysis: CvAnalysis;
        optimized_latex: string;
        section_diffs?: SectionDiff[];
        proposed_additions?: string[];
      }>("/api/optimize-cv", {
        cv_latex: cvLatex,
        job_description: jobAnalysis,
        language,
      });
      setAnalysis(r.data.analysis || {});
      setOptimizedLatex(r.data.optimized_latex || "");
      setSectionDiffs(r.data.section_diffs || []);
      setProposedAdditions(r.data.proposed_additions || []);
      const accepted: Record<number, boolean> = {};
      (r.data.section_diffs || []).forEach((_, i) => (accepted[i] = true));
      setAcceptedSections(accepted);
      push("Optimization complete.", "success");
    } catch (err) {
      push(apiErrorMessage(err, "Optimization failed."), "error");
    } finally {
      setOptBusy(false);
    }
  }

  // -----------------------------------------------------------------
  // PDF preview + downloads
  // -----------------------------------------------------------------

  async function renderPDF() {
    const latex = optimizedLatex || cvLatex;
    if (!latex.trim()) return;
    setPdfBusy(true);
    try {
      const r = await api.post("/api/render-latex", { latex }, { responseType: "blob" });
      if (pdfBlobRef.current) URL.revokeObjectURL(pdfBlobRef.current);
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      pdfBlobRef.current = url;
      setPdfUrl(url);
    } catch (err) {
      push(apiErrorMessage(err, "Could not render the PDF."), "error");
    } finally {
      setPdfBusy(false);
    }
  }

  async function downloadPDF() {
    const latex = optimizedLatex || cvLatex;
    if (!latex.trim()) return;
    try {
      const r = await api.post("/api/render-latex", { latex }, { responseType: "blob" });
      triggerDownload(r.data, "cv.pdf");
    } catch (err) {
      push(apiErrorMessage(err, "Download failed."), "error");
    }
  }

  async function exportAs(format: "docx" | "txt") {
    const latex = optimizedLatex || cvLatex;
    if (!latex.trim()) return;
    try {
      const r = await api.post(
        "/api/export",
        { latex, format },
        { responseType: "blob" },
      );
      triggerDownload(r.data, `cv.${format}`);
    } catch (err) {
      push(apiErrorMessage(err, "Export failed."), "error");
    }
  }

  function copyLatex() {
    navigator.clipboard
      .writeText(optimizedLatex || cvLatex)
      .then(() => push("LaTeX copied.", "success"))
      .catch(() => push("Could not copy.", "error"));
  }

  // -----------------------------------------------------------------
  // Save to workspace
  // -----------------------------------------------------------------

  async function saveToWorkspace() {
    if (!jobAnalysis) return;
    setSaveBusy(true);
    try {
      const job = await api.post<{ job: { id: number } }>("/api/jobs", {
        raw_text: jobAnalysis.raw_text || jobInput,
        parsed: jobAnalysis,
        language,
        title: "",
        company: "",
        status: "saved",
      });
      await api.post("/api/cv", {
        name: saveName || "Tailored CV",
        latex: optimizedLatex || cvLatex,
        analysis,
        template,
        language,
        job_id: job.data.job.id,
      });
      push("Saved to your workspace.", "success");
    } catch (err) {
      push(apiErrorMessage(err, "Could not save."), "error");
    } finally {
      setSaveBusy(false);
    }
  }

  // -----------------------------------------------------------------
  // Derived
  // -----------------------------------------------------------------

  const overall = analysis?.overall_score ?? analysis?.match_percentage ?? 0;
  const matched = analysis?.skills_match?.matched ?? [];
  const missing = analysis?.skills_match?.missing ?? [];
  const jobSignalCount =
    (jobAnalysis?.skills?.length || 0) +
    (jobAnalysis?.requirements?.length || 0) +
    (jobAnalysis?.qualifications?.length || 0);
  const cvLineCount = cvLatex.trim() ? cvLatex.trim().split(/\r?\n/).length : 0;
  const acceptedCount = Object.values(acceptedSections).filter(Boolean).length;
  const coverage =
    matched.length + missing.length > 0
      ? Math.round((matched.length / (matched.length + missing.length)) * 100)
      : Number(overall) || 0;

  const currentStep = useMemo(() => {
    if (analysis) return 3;
    if (jobAnalysis) return cvLatex.trim() ? 3 : 2;
    return 1;
  }, [jobAnalysis, cvLatex, analysis]);

  return (
    <AppShell>
      <section className="app-workbench">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 md:py-10">
          <div className="workbench-hero p-5 md:p-7">
            <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
              <div>
                <Chip color="primary" variant="flat">
                  CV optimizer
                </Chip>
                <h1 className="font-display text-3xl md:text-5xl font-extrabold mt-4 leading-tight">
                  Build a role-matched CV in one focused workspace.
                </h1>
                <p className="text-default-600 mt-3 max-w-3xl">
                  Bring in the offer, verify the signals, upload your CV, then review every AI
                  rewrite before export.
                </p>
                <Stepper step={currentStep} />
              </div>

              <div className="grid sm:grid-cols-3 lg:grid-cols-1 gap-3">
                <MetricTile label="Role signals" value={jobSignalCount || "Pending"} tone="blue" />
                <MetricTile label="CV source" value={cvLineCount ? `${cvLineCount} lines` : "Waiting"} tone="teal" />
                <MetricTile label="Match score" value={analysis ? `${overall}%` : "Not run"} tone="amber" />
              </div>
            </div>
          </div>

          <div className="grid xl:grid-cols-[minmax(0,1fr)_360px] gap-5 mt-6 items-start">
            <div className="space-y-5">
              <section className="tool-panel p-5 md:p-6">
                <PanelHeading
                  step="01"
                  kicker="Offer intake"
                  title="Capture the job brief"
                  body="Paste the description directly, fetch a posting URL, or load a local text file."
                />

                <div className="grid md:grid-cols-[minmax(0,1fr)_auto] gap-3 mt-5">
                  <Input
                    placeholder="Paste a job posting URL"
                    value={jobUrl}
                    onValueChange={setJobUrl}
                    classNames={{ inputWrapper: "bg-white" }}
                  />
                  <Button variant="bordered" onPress={fetchJobFromUrl} isLoading={jobBusy}>
                    Fetch URL
                  </Button>
                </div>

                <Textarea
                  className="mt-4"
                  minRows={8}
                  value={jobInput}
                  onValueChange={setJobInput}
                  placeholder="Paste the job description here..."
                  classNames={{ inputWrapper: "bg-white" }}
                />

                <input
                  ref={jobFileRef}
                  type="file"
                  accept=".txt,.md,.tex,text/plain"
                  className="hidden"
                  onChange={onJobFile}
                />
                <div className="flex flex-wrap gap-2 mt-4">
                  <Button color="primary" isLoading={jobBusy} onPress={parseJob}>
                    Analyze offer
                  </Button>
                  <Button variant="bordered" onPress={() => jobFileRef.current?.click()}>
                    Upload text file
                  </Button>
                  <Button variant="flat" onPress={loadSampleJob}>
                    Load sample
                  </Button>
                </div>
              </section>

              {jobAnalysis && (
                <section className="tool-panel p-5 md:p-6">
                  <PanelHeading
                    step="02"
                    kicker="CV source"
                    title="Add the candidate CV"
                    body="Upload a CV file or paste editable LaTeX/plain text. The optimizer keeps the content reviewable."
                  />
                  <input
                    ref={cvFileRef}
                    type="file"
                    accept=".tex,.txt,.pdf,.docx,.png,.jpg,.jpeg,.webp"
                    className="hidden"
                    onChange={onCvFile}
                  />
                  <div className="flex flex-wrap gap-2 mt-5">
                    <Button color="primary" onPress={() => cvFileRef.current?.click()} isLoading={cvBusy}>
                      Upload CV
                    </Button>
                    <Button variant="flat" onPress={loadSampleCV}>
                      Load sample CV
                    </Button>
                    {cvExtractStatus && (
                      <span className="text-sm text-default-500 self-center">{cvExtractStatus}</span>
                    )}
                  </div>
                  <Textarea
                    className="mt-4"
                    minRows={12}
                    value={cvLatex}
                    onValueChange={setCvLatex}
                    placeholder="Paste your LaTeX CV here..."
                    classNames={{ inputWrapper: "bg-white", input: "font-mono text-xs" }}
                  />
                </section>
              )}

              {jobAnalysis && cvLatex.trim() && (
                <section className="tool-panel p-5 md:p-6">
                  <PanelHeading
                    step="03"
                    kicker="Optimization run"
                    title="Choose output settings"
                    body="Select the language and template, then generate reviewable edits."
                  />
                  <div className="grid sm:grid-cols-2 gap-3 mt-5">
                    <Select
                      label="Output language"
                      selectedKeys={[language]}
                      onSelectionChange={(keys) => setLanguage(String(Array.from(keys)[0] || "en"))}
                    >
                      <SelectItem key="en">English</SelectItem>
                      <SelectItem key="fr">Français</SelectItem>
                      <SelectItem key="es">Español</SelectItem>
                    </Select>
                    <Select
                      label="Template"
                      selectedKeys={template ? [template] : []}
                      onSelectionChange={(keys) => setTemplate(String(Array.from(keys)[0] || ""))}
                    >
                      {templates.map((t) => (
                        <SelectItem key={t.id}>{t.label || t.name || t.id}</SelectItem>
                      ))}
                    </Select>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 mt-5">
                    <Button color="success" size="lg" isLoading={optBusy} onPress={optimize}>
                      Optimize CV
                    </Button>
                    <span className="text-sm text-default-500">
                      {analysis ? "Latest run is ready below." : "No changes are applied until you review them."}
                    </span>
                  </div>
                </section>
              )}
            </div>

            <aside className="space-y-4 xl:sticky xl:top-24">
              <PipelinePanel step={currentStep} analysisReady={!!analysis} cvReady={!!cvLatex.trim()} />

              <section className="insight-panel p-5">
                <div className="panel-kicker">Offer signals</div>
                <h2 className="font-display text-xl font-bold mt-1">
                  {jobAnalysis ? "Parsed job intelligence" : "Waiting for analysis"}
                </h2>
                {jobAnalysis ? (
                  <div className="mt-4 space-y-4">
                    <div className="grid grid-cols-3 gap-2">
                      <Stat label="Skills" value={jobAnalysis.skills?.length || 0} compact />
                      <Stat label="Reqs" value={jobAnalysis.requirements?.length || 0} compact />
                      <Stat label="Quals" value={jobAnalysis.qualifications?.length || 0} compact />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold mb-2">Required skills</h3>
                      <div className="flex flex-wrap gap-1.5">
                        {(jobAnalysis.skills || []).slice(0, 18).map((s) => (
                          <Chip key={s} size="sm" variant="flat" color="primary">
                            {s}
                          </Chip>
                        ))}
                      </div>
                    </div>
                    {(jobAnalysis.requirements || []).length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold mb-2">Top requirements</h3>
                        <ul className="text-sm text-default-600 space-y-2">
                          {jobAnalysis.requirements.slice(0, 5).map((r, i) => (
                            <li key={i} className="flex gap-2">
                              <span className="mt-2 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                              <span>{r}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-default-500 mt-3">
                    Once the offer is analyzed, skills and requirements stay visible while you work.
                  </p>
                )}
              </section>
            </aside>
          </div>

          {analysis && (
            <>
              <section className="tool-panel p-5 md:p-6 mt-6">
                <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5">
                  <div>
                    <div className="panel-kicker">Result intelligence</div>
                    <h2 className="font-display text-2xl font-extrabold mt-1">CV analysis results</h2>
                    <p className="text-default-500 mt-1">
                      Coverage, gaps, ATS notes, and recommended edits from the latest run.
                    </p>
                  </div>
                  <MatchGauge value={Number(overall) || 0} />
                </div>

                <div className="grid sm:grid-cols-3 gap-3 mt-5">
                  <Stat
                    label="Overall match"
                    value={`${overall}%`}
                    extra={<Progress value={Number(overall) || 0} color="primary" />}
                  />
                  <Stat
                    label="Skill coverage"
                    value={`${coverage}%`}
                    extra={<Progress value={coverage} color="success" />}
                  />
                  <Stat label="Missing signals" value={missing.length} valueClass="text-danger" />
                </div>

                <div className="grid lg:grid-cols-2 gap-5 mt-6">
                  <div>
                    <h3 className="font-semibold text-sm mb-2 text-success-700">
                      Matched in your CV ({matched.length})
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {matched.map((s) => (
                        <Chip key={s} size="sm" variant="flat" color="success">
                          {s}
                        </Chip>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold text-sm mb-2 text-danger-700">
                      Asked for, but not found ({missing.length})
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {missing.map((s) => (
                        <Chip key={s} size="sm" variant="flat" color="danger">
                          {s}
                        </Chip>
                      ))}
                    </div>
                  </div>
                </div>

                {analysis.recommendations && analysis.recommendations.length > 0 && (
                  <div className="mt-6 rounded-lg bg-default-50 border border-default-200 p-4">
                    <h3 className="font-semibold text-sm mb-2">Recommendations</h3>
                    <ul className="text-sm text-default-600 space-y-2">
                      {analysis.recommendations.map((r, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="mt-2 h-1.5 w-1.5 rounded-full bg-warning shrink-0" />
                          <span>{r}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {analysis.ats && <AtsBreakdown ats={analysis.ats} />}
              </section>

              {sectionDiffs.length > 0 && (
                <section className="tool-panel p-5 md:p-6 mt-5">
                  <div className="flex justify-between gap-3 flex-wrap">
                    <div>
                      <div className="panel-kicker">Rewrite review</div>
                      <h2 className="font-display text-2xl font-extrabold mt-1">Review changes</h2>
                      <p className="text-default-500 text-sm mt-1">
                        {acceptedCount}/{sectionDiffs.length} sections currently accepted.
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="bordered"
                        color="success"
                        onPress={() => {
                          const next: Record<number, boolean> = {};
                          sectionDiffs.forEach((_, i) => (next[i] = true));
                          setAcceptedSections(next);
                        }}
                      >
                        Accept all
                      </Button>
                      <Button
                        size="sm"
                        variant="bordered"
                        onPress={() => setAcceptedSections({})}
                      >
                        Reject all
                      </Button>
                    </div>
                  </div>
                  <div className="space-y-3 mt-5">
                    {sectionDiffs.map((d, i) => (
                      <SectionDiffCard
                        key={i}
                        diff={d}
                        accepted={!!acceptedSections[i]}
                        onToggle={(v) => setAcceptedSections((s) => ({ ...s, [i]: v }))}
                      />
                    ))}
                  </div>
                </section>
              )}

              <section className="tool-panel p-5 md:p-6 mt-5">
                <div className="flex justify-between flex-wrap gap-3">
                  <div>
                    <div className="panel-kicker">Final document</div>
                    <h2 className="font-display text-2xl font-extrabold mt-1">Corrected LaTeX</h2>
                    <p className="text-default-500 text-sm mt-1">
                      Edit the generated source, render a PDF preview, or export it.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" color="success" onPress={downloadPDF}>
                      Download PDF
                    </Button>
                    <Button size="sm" variant="bordered" color="primary" onPress={() => exportAs("docx")}>
                      Word
                    </Button>
                    <Button size="sm" variant="bordered" onPress={() => exportAs("txt")}>
                      TXT
                    </Button>
                    <Button size="sm" variant="bordered" onPress={renderPDF} isLoading={pdfBusy}>
                      Render PDF
                    </Button>
                    <Button size="sm" color="primary" onPress={copyLatex}>
                      Copy LaTeX
                    </Button>
                  </div>
                </div>

                <div className="grid xl:grid-cols-[minmax(0,1fr)_420px] gap-4 mt-5">
                  <Textarea
                    minRows={16}
                    value={optimizedLatex}
                    onValueChange={setOptimizedLatex}
                    classNames={{ inputWrapper: "bg-white", input: "font-mono text-xs" }}
                  />
                  <div className="editor-frame min-h-[360px]">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-default-200 bg-white">
                      <h3 className="font-semibold text-sm">PDF preview</h3>
                      <Chip size="sm" variant="flat" color={pdfUrl ? "success" : "default"}>
                        {pdfUrl ? "Rendered" : "Not rendered"}
                      </Chip>
                    </div>
                    {pdfUrl ? (
                      <iframe
                        title="PDF preview"
                        src={pdfUrl}
                        className="w-full h-[620px] bg-white"
                      />
                    ) : (
                      <div className="h-full min-h-[300px] grid place-items-center p-6 text-center text-sm text-default-500">
                        PDF preview will appear here after rendering.
                      </div>
                    )}
                  </div>
                </div>
              </section>

              {proposedAdditions.length > 0 && (
                <section className="tool-panel p-5 md:p-6 mt-5">
                  <div className="panel-kicker">Optional evidence</div>
                  <h2 className="font-display text-2xl font-extrabold mt-1">Proposed additions</h2>
                  <ul className="grid md:grid-cols-2 gap-3 mt-4 text-sm text-default-600">
                    {proposedAdditions.map((p, i) => (
                      <li key={i} className="rounded-lg bg-default-50 border border-default-200 p-4">
                        {p}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <CoverLetterPanel cvLatex={optimizedLatex || cvLatex} jobText={jobInput} language={language} />

              <section className="tool-panel p-5 md:p-6 mt-5">
                <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
                  <div>
                    <div className="panel-kicker">Workspace save</div>
                    <h2 className="font-display text-2xl font-extrabold mt-1">Save this application</h2>
                    <p className="text-default-500 text-sm mt-1">
                      Store the parsed job and tailored CV so you can revisit versions later.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3 items-end">
                    <Input
                      label="CV name"
                      placeholder="e.g. Backend - Acme"
                      value={saveName}
                      onValueChange={setSaveName}
                      className="w-full sm:w-72"
                    />
                    <Button color="success" isLoading={saveBusy} onPress={saveToWorkspace}>
                      Save job + CV
                    </Button>
                  </div>
                </div>
              </section>
            </>
          )}
        </div>
      </section>
    </AppShell>
  );
}

function PanelHeading({
  step,
  kicker,
  title,
  body,
}: {
  step: string;
  kicker: string;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-4 items-start">
      <div className="step-token" data-active="true">
        {step}
      </div>
      <div>
        <div className="panel-kicker">{kicker}</div>
        <h2 className="font-display text-2xl font-extrabold mt-1">{title}</h2>
        <p className="text-default-500 text-sm mt-1 max-w-2xl">{body}</p>
      </div>
    </div>
  );
}

function MetricTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone: "blue" | "teal" | "amber";
}) {
  const toneClass = {
    blue: "bg-primary",
    teal: "bg-success",
    amber: "bg-warning",
  }[tone];

  return (
    <div className="metric-tile p-4">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${toneClass}`} aria-hidden />
        <span className="text-xs uppercase tracking-wide text-default-500 font-semibold">{label}</span>
      </div>
      <div className="font-display text-2xl font-extrabold mt-2">{value}</div>
    </div>
  );
}

function PipelinePanel({
  step,
  analysisReady,
  cvReady,
}: {
  step: number;
  analysisReady: boolean;
  cvReady: boolean;
}) {
  const items = [
    { label: "Offer parsed", done: step >= 2 },
    { label: "CV loaded", done: cvReady },
    { label: "Optimization run", done: analysisReady },
  ];

  return (
    <section className="insight-panel p-5">
      <div className="panel-kicker">Workflow status</div>
      <h2 className="font-display text-xl font-bold mt-1">Application pipeline</h2>
      <div className="space-y-3 mt-4">
        {items.map((item, index) => (
          <div key={item.label} className="flex items-center gap-3">
            <div className="step-token" data-active={item.done}>
              {index + 1}
            </div>
            <div>
              <div className={item.done ? "font-semibold text-default-900" : "font-medium text-default-500"}>
                {item.label}
              </div>
              <div className="text-xs text-default-400">{item.done ? "Ready" : "Pending"}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function MatchGauge({ value }: { value: number }) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div
      className="score-ring shrink-0"
      style={{
        background: `conic-gradient(#2563eb ${safeValue * 3.6}deg, #e2e8f0 0deg)`,
      }}
      aria-label={`Match score ${safeValue}%`}
    >
      <div className="score-ring-inner">
        <div className="font-display text-2xl font-extrabold">{safeValue}%</div>
        <div className="text-[0.65rem] uppercase tracking-wide text-default-500">match</div>
      </div>
    </div>
  );
}

function Stepper({ step }: { step: number }) {
  const nodes = ["Job description", "Your CV", "Optimize"];
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 mt-6">
      {nodes.map((label, i) => {
        const n = i + 1;
        const active = n <= step;
        return (
          <div key={label} className="flex items-center gap-3">
            <div className="step-token" data-active={active}>
              {n}
            </div>
            <span
              className={`text-sm ${active ? "text-default-900 font-medium" : "text-default-500"}`}
            >
              {label}
            </span>
            {i < nodes.length - 1 && (
              <div className={`hidden sm:block h-px w-10 ${active && n < step ? "bg-primary" : "bg-default-300"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function Stat({
  label,
  value,
  valueClass,
  extra,
  compact,
}: {
  label: string;
  value: React.ReactNode;
  valueClass?: string;
  extra?: React.ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={`border border-default-200 rounded-lg bg-white ${compact ? "p-3" : "p-4"}`}>
      <div className="text-[0.68rem] text-default-500 uppercase tracking-wide font-semibold">{label}</div>
      <div className={`${compact ? "text-xl" : "text-2xl"} font-display font-extrabold mt-1 ${valueClass || ""}`}>
        {value}
      </div>
      {extra && <div className="mt-2">{extra}</div>}
    </div>
  );
}

function AtsBreakdown({ ats }: { ats: AtsAnalysis }) {
  const score = ats.ats_score;
  return (
    <div className="mt-6 rounded-lg border border-default-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="font-semibold">ATS breakdown</h3>
        {score != null && (
          <Chip color="primary" variant="flat">
            {score}% ATS
          </Chip>
        )}
      </div>
      {score != null && <Progress value={Number(score)} color="primary" className="mt-3" />}
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        <div className="rounded-lg bg-default-50 p-4">
          <h5 className="text-sm font-semibold mb-1">Requirements covered</h5>
          <ul className="text-sm text-default-600 space-y-2">
            {(ats.requirements || []).map((r, i) => (
              <li key={i} className="flex items-start gap-2">
                <span
                  className={[
                    "mt-1 h-2 w-2 rounded-full",
                    r.covered ? "bg-success" : "bg-default-300",
                  ].join(" ")}
                />
                {r.text}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg bg-default-50 p-4">
          <h5 className="text-sm font-semibold mb-1">Priority improvements</h5>
          <ul className="text-sm text-default-600 space-y-2">
            {(ats.priorities || []).map((p, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-2 h-1.5 w-1.5 rounded-full bg-warning shrink-0" />
                <span>{p}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function SectionDiffCard({
  diff,
  accepted,
  onToggle,
}: {
  diff: SectionDiff;
  accepted: boolean;
  onToggle: (v: boolean) => void;
}) {
  return (
    <Card className="border border-default-200">
      <CardBody>
        <div className="flex justify-between items-center mb-3 gap-2 flex-wrap">
          <div>
            <div className="text-xs uppercase tracking-wide text-default-500">Section</div>
            <h4 className="font-semibold">{diff.section}</h4>
            {diff.reason && <p className="text-xs text-default-500 mt-1">{diff.reason}</p>}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={accepted ? "solid" : "bordered"}
              color="success"
              onPress={() => onToggle(true)}
            >
              Accept
            </Button>
            <Button
              size="sm"
              variant={!accepted ? "solid" : "bordered"}
              onPress={() => onToggle(false)}
            >
              Reject
            </Button>
          </div>
        </div>
        <Tabs aria-label="diff view">
          <Tab key="after" title="After">
            <pre className="latex-code bg-default-50 p-3 rounded-md max-h-64 overflow-auto">
              {diff.after}
            </pre>
          </Tab>
          <Tab key="before" title="Before">
            <pre className="latex-code bg-default-50 p-3 rounded-md max-h-64 overflow-auto">
              {diff.before}
            </pre>
          </Tab>
        </Tabs>
      </CardBody>
    </Card>
  );
}

function CoverLetterPanel({
  cvLatex,
  jobText,
  language,
}: {
  cvLatex: string;
  jobText: string;
  language: string;
}) {
  const { push } = useToast();
  const [kinds, setKinds] = useState<string[]>(["cover_letter"]);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<Record<string, string>>({});

  function toggle(k: string) {
    setKinds((curr) => (curr.includes(k) ? curr.filter((x) => x !== k) : [...curr, k]));
  }

  async function generate() {
    if (kinds.length === 0) return;
    setBusy(true);
    try {
      const r = await api.post<{ results: Record<string, string> }>("/api/cover-letter", {
        cv_latex: cvLatex,
        job_text: jobText,
        kinds,
        language,
      });
      setResults(r.data.results || {});
    } catch (err) {
      push(apiErrorMessage(err, "Could not generate outreach text."), "error");
    } finally {
      setBusy(false);
    }
  }

  const KINDS = [
    { id: "cover_letter", label: "Cover letter" },
    { id: "recruiter_message", label: "Recruiter message" },
    { id: "linkedin_message", label: "LinkedIn note" },
    { id: "email", label: "Application email" },
  ];

  return (
    <section className="tool-panel p-5 md:p-6 mt-5">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <div className="panel-kicker">Outreach kit</div>
          <h2 className="font-display text-2xl font-extrabold mt-1">Cover letter and messages</h2>
          <p className="text-default-500 text-sm mt-1">
            Generate supporting text from the same CV and job context.
          </p>
        </div>
        <Button color="primary" isLoading={busy} onPress={generate}>
          Generate outreach
        </Button>
      </div>

      <div className="segmented-row mt-5">
        {KINDS.map((k) => (
          <Button
            key={k.id}
            size="sm"
            variant={kinds.includes(k.id) ? "solid" : "bordered"}
            color={kinds.includes(k.id) ? "primary" : "default"}
            onPress={() => toggle(k.id)}
          >
            {k.label}
          </Button>
        ))}
      </div>

      {Object.entries(results).length > 0 && (
        <div className="grid lg:grid-cols-2 gap-4 mt-5">
          {KINDS.map((k) => (
            results[k.id] ? (
              <div key={k.id} className="rounded-lg border border-default-200 bg-default-50 p-4">
                <h3 className="font-semibold text-sm mb-3">{k.label}</h3>
                <Textarea
                  minRows={7}
                  value={results[k.id]}
                  readOnly
                  classNames={{ inputWrapper: "bg-white", input: "font-mono text-xs" }}
                />
              </div>
            ) : null
          ))}
        </div>
      )}
    </section>
  );
}

function triggerDownload(data: BlobPart, name: string) {
  const url = URL.createObjectURL(new Blob([data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
