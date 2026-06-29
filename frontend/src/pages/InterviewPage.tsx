import { useState } from "react";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Chip,
  Input,
  Progress,
  Select,
  SelectItem,
  Slider,
  Tab,
  Tabs,
  Textarea,
} from "@heroui/react";
import { AppShell } from "../layouts/AppShell";
import { api, apiErrorMessage } from "../lib/api";
import { useToast } from "../contexts/ToastContext";

type Question = {
  id?: string;
  prompt: string;
  domain?: string;
  difficulty?: string;
  why_asked?: string;
  what_good_answer_looks_like?: string;
};

type Review = {
  score?: number;
  strengths?: string[];
  improvements?: string[];
  suggested_followups?: string[];
  feedback?: string;
};

type Session = {
  questions: Question[];
  summary?: string;
  plan?: string[];
};

const DOMAINS = [
  { id: "coding", label: "Coding" },
  { id: "system_design", label: "System design" },
  { id: "technical", label: "Technical" },
  { id: "behavioral", label: "Behavioral" },
];

const GOALS = [
  { id: "balanced", label: "Balanced" },
  { id: "weak_spots", label: "Weak spots" },
  { id: "final_mock", label: "Final mock" },
  { id: "technical_deep_dive", label: "Deep dive" },
];

const LEVELS = [
  { id: "", label: "Auto" },
  { id: "junior", label: "Junior" },
  { id: "mid", label: "Mid" },
  { id: "senior", label: "Senior" },
];

export default function InterviewPage() {
  const { push } = useToast();

  const [cvInput, setCvInput] = useState("");
  const [jobInput, setJobInput] = useState("");
  const [level, setLevel] = useState<string>("");
  const [goal, setGoal] = useState<string>("balanced");
  const [domains, setDomains] = useState<string[]>(["coding", "system_design", "technical", "behavioral"]);
  const [count, setCount] = useState<number>(10);
  const [extra, setExtra] = useState("");
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState<Session | null>(null);

  function toggleDomain(id: string) {
    setDomains((curr) => (curr.includes(id) ? curr.filter((x) => x !== id) : [...curr, id]));
  }

  async function generate() {
    if (!cvInput.trim() && !jobInput.trim()) {
      push("Paste your CV and/or a job description.", "error");
      return;
    }
    setBusy(true);
    try {
      const r = await api.post<{ questions: Question[]; summary?: string; plan?: string[] }>(
        "/api/interview/questions",
        {
          cv_latex: cvInput,
          job_description: jobInput,
          level: level || undefined,
          domains,
          count,
          extra_instructions: extra || undefined,
          session_goal: goal,
        },
      );
      setSession({
        questions: r.data.questions || [],
        summary: r.data.summary,
        plan: r.data.plan,
      });
    } catch (err) {
      push(apiErrorMessage(err, "Could not generate the session."), "error");
    } finally {
      setBusy(false);
    }
  }

  const selectedGoal = GOALS.find((g) => g.id === goal)?.label || "Balanced";
  const selectedLevel = LEVELS.find((l) => l.id === level)?.label || "Auto";
  const contextCount = [cvInput.trim(), jobInput.trim()].filter(Boolean).length;
  const generatedCount = session?.questions?.length || 0;

  return (
    <AppShell>
      <section className="app-workbench">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 md:py-10">
          <div className="workbench-hero p-5 md:p-7">
            <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] gap-6 items-start">
              <div>
                <Chip color="primary" variant="flat">
                  Interview preparation
                </Chip>
                <h1 className="font-display text-3xl md:text-5xl font-extrabold mt-4 leading-tight">
                  Turn your CV and offer into a focused coaching room.
                </h1>
                <p className="text-default-600 mt-3 max-w-3xl">
                  Generate role-specific questions, practice structured answers, and get review
                  feedback without leaving the preparation flow.
                </p>
              </div>

              <div className="grid sm:grid-cols-3 lg:grid-cols-1 gap-3">
                <CoachMetric label="Context" value={`${contextCount}/2`} tone="blue" />
                <CoachMetric label="Questions" value={generatedCount || count} tone="teal" />
                <CoachMetric label="Focus" value={selectedGoal} tone="amber" />
              </div>
            </div>
          </div>

          <div className="grid xl:grid-cols-[minmax(0,1fr)_360px] gap-5 mt-6 items-start">
            <div className="space-y-5">
              <section className="tool-panel p-5 md:p-6">
                <div className="panel-kicker">Context lab</div>
                <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-3 mt-1">
                  <div>
                    <h2 className="font-display text-2xl font-extrabold">Paste the source material</h2>
                    <p className="text-default-500 text-sm mt-1">
                      Use either field, or both for sharper role-specific coaching.
                    </p>
                  </div>
                  <Chip color={contextCount ? "success" : "default"} variant="flat">
                    {contextCount ? `${contextCount} context source${contextCount > 1 ? "s" : ""}` : "No context yet"}
                  </Chip>
                </div>

                <div className="grid lg:grid-cols-2 gap-4 mt-5">
                  <Textarea
                    label="Your CV"
                    minRows={10}
                    value={cvInput}
                    onValueChange={setCvInput}
                    placeholder="Paste LaTeX or plain text..."
                    classNames={{ inputWrapper: "bg-white", input: "font-mono text-xs" }}
                  />
                  <Textarea
                    label="Job offer"
                    minRows={10}
                    value={jobInput}
                    onValueChange={setJobInput}
                    placeholder="Paste the job offer..."
                    classNames={{ inputWrapper: "bg-white" }}
                  />
                </div>
              </section>

              <section className="tool-panel p-5 md:p-6">
                <div className="panel-kicker">Session controls</div>
                <h2 className="font-display text-2xl font-extrabold mt-1">Tune the coaching run</h2>
                <p className="text-default-500 text-sm mt-1">
                  Build a session that matches the interview stage, seniority, and question mix.
                </p>

                <div className="grid gap-6 mt-5">
                  <ControlGroup label="Seniority level">
                    {LEVELS.map((l) => (
                      <SelectionButton
                        key={l.id || "auto"}
                        selected={level === l.id}
                        onPress={() => setLevel(l.id)}
                      >
                        {l.label}
                      </SelectionButton>
                    ))}
                  </ControlGroup>

                  <ControlGroup label="Session focus">
                    {GOALS.map((g) => (
                      <SelectionButton
                        key={g.id}
                        selected={goal === g.id}
                        onPress={() => setGoal(g.id)}
                      >
                        {g.label}
                      </SelectionButton>
                    ))}
                  </ControlGroup>

                  <ControlGroup label="Question domains">
                    {DOMAINS.map((d) => (
                      <SelectionButton
                        key={d.id}
                        selected={domains.includes(d.id)}
                        onPress={() => toggleDomain(d.id)}
                      >
                        {d.label}
                      </SelectionButton>
                    ))}
                  </ControlGroup>

                  <div className="rounded-lg border border-default-200 bg-white p-4">
                    <Slider
                      label={`Question volume: ${count}`}
                      minValue={5}
                      maxValue={20}
                      step={1}
                      value={count}
                      onChange={(v) => setCount(Array.isArray(v) ? v[0] : v)}
                    />
                  </div>

                  <Textarea
                    label="Steer the coach"
                    placeholder="e.g. Focus on async Python, scaling tradeoffs, and one SQL challenge..."
                    minRows={3}
                    value={extra}
                    onValueChange={setExtra}
                    classNames={{ inputWrapper: "bg-white" }}
                  />

                  <div className="flex flex-wrap items-center gap-3">
                    <Button color="success" size="lg" isLoading={busy} onPress={generate}>
                      Generate coaching session
                    </Button>
                    <span className="text-sm text-default-500">
                      {domains.length} domains selected, {selectedLevel.toLowerCase()} level.
                    </span>
                  </div>
                </div>
              </section>
            </div>

            <aside className="space-y-4 xl:sticky xl:top-24">
              <section className="insight-panel p-5">
                <div className="panel-kicker">Run profile</div>
                <h2 className="font-display text-xl font-bold mt-1">Coach configuration</h2>
                <div className="space-y-3 mt-4">
                  <RunProfile label="Level" value={selectedLevel} />
                  <RunProfile label="Goal" value={selectedGoal} />
                  <RunProfile label="Questions" value={count} />
                  <RunProfile label="Domains" value={domains.length} />
                </div>
              </section>

              <section className="insight-panel p-5">
                <div className="panel-kicker">Coverage</div>
                <h2 className="font-display text-xl font-bold mt-1">Question mix</h2>
                <div className="flex flex-wrap gap-1.5 mt-4">
                  {DOMAINS.map((d) => (
                    <Chip
                      key={d.id}
                      size="sm"
                      variant={domains.includes(d.id) ? "flat" : "bordered"}
                      color={domains.includes(d.id) ? "primary" : "default"}
                    >
                      {d.label}
                    </Chip>
                  ))}
                </div>
                <p className="text-sm text-default-500 mt-4">
                  Select at least the domains expected in the role. Extra instructions can narrow
                  the output to a framework, stack, or interview round.
                </p>
              </section>
            </aside>
          </div>

          {session && (
            <div className="mt-6 space-y-5">
              {session.summary && (
                <section className="tool-panel p-5 md:p-6">
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                    <div>
                      <div className="panel-kicker">Session plan</div>
                      <h2 className="font-display text-2xl font-extrabold mt-1">Your practice path</h2>
                      <p className="text-default-600 mt-2">{session.summary}</p>
                    </div>
                    <Chip color="success" variant="flat" size="lg">
                      {session.questions.length} questions
                    </Chip>
                  </div>
                  {session.plan && session.plan.length > 0 && (
                    <div className="grid md:grid-cols-2 gap-3 mt-5">
                      {session.plan.map((p, i) => (
                        <div key={i} className="rounded-lg bg-default-50 border border-default-200 p-4 text-sm text-default-600">
                          {p}
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              )}

              <div className="space-y-4">
                {session.questions.map((q, i) => (
                  <QuestionCard key={i} question={q} index={i} jobText={jobInput} />
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </AppShell>
  );
}

function CoachMetric({
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
      <div className="font-display text-2xl font-extrabold mt-2 truncate">{value}</div>
    </div>
  );
}

function ControlGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-sm font-semibold text-default-700 mb-2 block">{label}</label>
      <div className="segmented-row">{children}</div>
    </div>
  );
}

function SelectionButton({
  selected,
  onPress,
  children,
}: {
  selected: boolean;
  onPress: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      size="sm"
      variant={selected ? "solid" : "bordered"}
      color={selected ? "primary" : "default"}
      onPress={onPress}
    >
      {children}
    </Button>
  );
}

function RunProfile({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-default-200 bg-white p-3">
      <div className="text-[0.68rem] text-default-500 uppercase tracking-wide font-semibold">{label}</div>
      <div className="font-display text-xl font-extrabold mt-1">{value}</div>
    </div>
  );
}

function QuestionCard({
  question,
  index,
  jobText,
}: {
  question: Question;
  index: number;
  jobText: string;
}) {
  const { push } = useToast();
  const [answer, setAnswer] = useState("");
  const [language, setLanguage] = useState("python");
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<Review | null>(null);

  async function reviewAnswer() {
    if (!answer.trim()) {
      push("Write your answer first.", "error");
      return;
    }
    setBusy(true);
    try {
      const r = await api.post<{ review: Review }>("/api/interview/review", {
        question,
        answer,
        language,
        job_description: jobText,
      });
      setReview(r.data.review || null);
    } catch (err) {
      push(apiErrorMessage(err, "Review failed."), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="question-card p-5 md:p-6">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex gap-4">
          <div className="step-token" data-active="true">
            {index + 1}
          </div>
          <div>
            <div className="panel-kicker">Practice prompt</div>
            <h3 className="font-display text-xl font-bold mt-1">{question.prompt}</h3>
            <div className="flex flex-wrap gap-2 mt-3">
              {question.domain && (
                <Chip size="sm" variant="flat" color="primary">
                  {question.domain}
                </Chip>
              )}
              {question.difficulty && (
                <Chip size="sm" variant="flat">
                  {question.difficulty}
                </Chip>
              )}
            </div>
          </div>
        </div>
        {review?.score != null && (
          <div className="min-w-40">
            <div className="flex justify-between text-xs text-default-500 mb-1">
              <span>Review score</span>
              <span>{review.score}/10</span>
            </div>
            <Progress value={review.score * 10} color="primary" />
          </div>
        )}
      </div>

      {question.why_asked && (
        <details className="interview-note text-sm text-default-600 mt-5">
          <summary className="cursor-pointer font-semibold text-default-800">
            Why this question matters
          </summary>
          <p className="mt-3">{question.why_asked}</p>
          {question.what_good_answer_looks_like && (
            <p className="mt-2 text-default-500">{question.what_good_answer_looks_like}</p>
          )}
        </details>
      )}

      <div className="rounded-lg border border-default-200 bg-default-50 p-3 md:p-4 mt-5">
        <Tabs aria-label="answer-mode" variant="underlined">
          <Tab key="answer" title="Answer lab">
            <Textarea
              minRows={6}
              value={answer}
              onValueChange={setAnswer}
              placeholder="Type or paste your answer or code here..."
              classNames={{ inputWrapper: "bg-white", input: "font-mono text-xs" }}
            />
            <div className="flex gap-2 mt-3 flex-wrap items-end">
              <Input
                label="Language"
                size="sm"
                className="max-w-[170px]"
                value={language}
                onValueChange={setLanguage}
                classNames={{ inputWrapper: "bg-white" }}
              />
              <Button color="primary" size="sm" isLoading={busy} onPress={reviewAnswer}>
                Review answer
              </Button>
            </div>
          </Tab>
        </Tabs>
      </div>

      {review && (
        <div className="grid lg:grid-cols-3 gap-3 mt-5">
          {review.strengths && review.strengths.length > 0 && (
            <ReviewBlock title="Strengths" tone="success" items={review.strengths} />
          )}
          {review.improvements && review.improvements.length > 0 && (
            <ReviewBlock title="Improvements" tone="warning" items={review.improvements} />
          )}
          {review.suggested_followups && review.suggested_followups.length > 0 && (
            <ReviewBlock title="Follow-ups" tone="primary" items={review.suggested_followups} />
          )}
          {review.feedback && (
            <div className="lg:col-span-3 rounded-lg border border-default-200 bg-white p-4 text-sm text-default-600">
              {review.feedback}
            </div>
          )}
        </div>
      )}
    </article>
  );
}

function ReviewBlock({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "success" | "warning" | "primary";
  items: string[];
}) {
  const colorClass = {
    success: "bg-success",
    warning: "bg-warning",
    primary: "bg-primary",
  }[tone];

  return (
    <div className="rounded-lg border border-default-200 bg-white p-4">
      <h4 className="text-sm font-semibold mb-3">{title}</h4>
      <ul className="space-y-2 text-sm text-default-600">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2">
            <span className={`mt-2 h-1.5 w-1.5 rounded-full shrink-0 ${colorClass}`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
