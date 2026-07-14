import { Link } from "react-router-dom";
import { Button, Card, CardBody, Chip } from "@heroui/react";
import { AppShell } from "../layouts/AppShell";
import { useAuth } from "../contexts/AuthContext";

const OUTCOMES = [
  {
    title: "Optimize the CV for the role",
    body: "Auto-CV compares the offer against your CV, highlights skill coverage, and proposes grounded rewrites you can accept, edit, or reject.",
    image: "/static/assets/how-cv-optimization.png",
    alt: "CV optimization dashboard comparing a job offer with a candidate CV and reviewable rewrite suggestions.",
    points: ["ATS-style match coverage", "Reviewable section rewrites", "PDF, Word, text, and LaTeX export"],
  },
  {
    title: "Prepare for the interview",
    body: "The same job and CV context becomes targeted interview questions, practice prompts, and answer structure without losing the role focus.",
    image: "/static/assets/how-interview-prep.png",
    alt: "Interview preparation dashboard with question cards, a microphone control, answer structure, and competency coverage.",
    points: ["Role-specific questions", "STAR answer practice", "Saved context from each application"],
  },
];

const PROCESS_STEPS = [
  {
    chip: "Step 01",
    title: "Analyze the offer",
    body: "Paste the job offer or fetch it from a careers page. Auto-CV extracts the skills, requirements, qualifications, and responsibilities that drive the match.",
    image: "/static/assets/how-offer-analysis.png",
    alt: "Job offer document flowing into extracted skills, requirements, and qualifications panels.",
    points: ["Plain text or URL input", "Structured role signals", "Original offer kept for review"],
  },
  {
    chip: "Step 02",
    title: "Bring your CV",
    body: "Upload LaTeX, PDF, Word, or a scanned image. The app extracts structured content and keeps your existing facts as the source of truth.",
    image: "/static/assets/how-cv-upload.png",
    alt: "Candidate CV upload turning into structured profile cards for matching.",
    points: ["Multiple CV formats", "LaTeX preserved when available", "Profile structured for matching"],
  },
  {
    chip: "Step 03",
    title: "Optimize and review",
    body: "See matched skills, missing signals, and suggested rewrites. Each change stays reviewable before it touches the final CV.",
    image: "/static/assets/how-cv-optimization.png",
    alt: "CV match dashboard with a match score, green coverage markers, amber gaps, and rewrite review controls.",
    points: ["Coverage and gap view", "Before and after rewrite review", "No unverified claims added"],
  },
  {
    chip: "Step 04",
    title: "Export and save",
    body: "Render a PDF preview, download the final version, copy the source, and save the tailored CV with the job inside your workspace.",
    image: "/static/assets/how-export-workspace.png",
    alt: "Editable source moving to PDF export and saved workspace history.",
    points: ["Inline PDF preview", "Reusable saved versions", "Workspace history for each role"],
  },
  {
    chip: "Step 05",
    title: "Practice the interview",
    body: "Use the optimized CV and offer analysis to generate interview prompts that reflect the exact role you are applying for.",
    image: "/static/assets/how-interview-prep.png",
    alt: "Interview prep dashboard using CV and job context to create questions and practice prompts.",
    points: ["Questions tied to the role", "Answer structure prompts", "Preparation follows the same context"],
  },
];

export default function HowItWorksPage() {
  const { user } = useAuth();
  const primaryCta = user
    ? { to: "/optimizer", label: "Open optimizer" }
    : { to: "/register", label: "Create free account" };
  const secondaryCta = user
    ? { to: "/interview", label: "Prepare interview" }
    : { to: "/demo", label: "Try live demo" };

  return (
    <AppShell>
      <section
        className="relative isolate overflow-hidden text-white"
        style={{
          backgroundImage:
            "linear-gradient(90deg, rgba(11,31,77,.94) 0%, rgba(11,31,77,.82) 48%, rgba(15,118,110,.2) 100%), url('/static/assets/how-workflow-hero.png')",
          backgroundPosition: "center",
          backgroundSize: "cover",
        }}
      >
        <div className="absolute inset-0 bg-black/10" aria-hidden />
        <div className="relative max-w-6xl mx-auto px-6 py-20 lg:py-24">
          <Chip color="default" variant="flat" className="bg-white/15 text-white">
            Guided CV and interview workflow
          </Chip>
          <h1 className="font-display text-4xl md:text-5xl font-extrabold leading-tight mt-4 max-w-3xl">
            From job offer to optimized CV, then interview-ready answers.
          </h1>
          <p className="text-lg text-white/85 mt-4 max-w-2xl">
            Auto-CV turns the same role context into a reviewed application package: role analysis,
            grounded CV rewrites, exports, saved versions, and focused interview preparation.
          </p>
          <div className="flex flex-wrap gap-3 mt-8">
            <Button
              as={Link}
              to={primaryCta.to}
              color="primary"
              size="lg"
              radius="full"
              className="font-semibold"
            >
              {primaryCta.label}
            </Button>
            <Button
              as={Link}
              to={secondaryCta.to}
              size="lg"
              radius="full"
              variant="bordered"
              className="text-white border-white/40"
            >
              {secondaryCta.label}
            </Button>
          </div>
        </div>
      </section>

      <section className="py-16 bg-white">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-10">
            <Chip color="primary" variant="flat">
              What you get
            </Chip>
            <h2 className="font-display text-3xl md:text-4xl font-extrabold mt-3">
              One workflow for the application and the interview
            </h2>
            <p className="text-default-500 mt-2 max-w-2xl mx-auto">
              The visual flow is built around two outcomes: a stronger CV for the job and interview
              practice based on the same evidence.
            </p>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            {OUTCOMES.map((outcome) => (
              <Card
                key={outcome.title}
                radius="sm"
                className="border border-default-200 shadow-sm overflow-hidden"
              >
                <img src={outcome.image} alt={outcome.alt} className="w-full aspect-video object-cover" />
                <CardBody className="p-6">
                  <h3 className="font-display text-2xl font-bold">{outcome.title}</h3>
                  <p className="text-default-500 mt-2">{outcome.body}</p>
                  <div className="grid gap-2 mt-5">
                    {outcome.points.map((point) => (
                      <div key={point} className="flex items-center gap-2 text-sm text-default-600">
                        <span className="h-2 w-2 rounded-full bg-primary" aria-hidden />
                        <span>{point}</span>
                      </div>
                    ))}
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-10">
            <Chip color="primary" variant="flat">
              Process
            </Chip>
            <h2 className="font-display text-3xl md:text-4xl font-extrabold mt-3">
              Five checkpoints from offer to interview
            </h2>
            <p className="text-default-500 mt-2 max-w-2xl mx-auto">
              Every step stays reviewable. The AI suggests improvements, but your CV facts remain
              under your control.
            </p>
          </div>

          <div className="space-y-8">
            {PROCESS_STEPS.map((step, index) => (
              <article
                key={step.chip}
                className="grid lg:grid-cols-[1.1fr_.9fr] gap-6 lg:gap-10 items-center bg-white border border-default-200 rounded-lg shadow-sm p-4 md:p-6"
              >
                <div className={index % 2 === 1 ? "lg:order-2" : ""}>
                  <img
                    src={step.image}
                    alt={step.alt}
                    loading="lazy"
                    className="w-full aspect-video object-cover rounded-md border border-default-200 shadow-sm"
                  />
                </div>
                <div className="p-2 md:p-3">
                  <Chip color="primary" variant="flat" className="mb-4">
                    {step.chip}
                  </Chip>
                  <h3 className="font-display text-2xl md:text-3xl font-bold">{step.title}</h3>
                  <p className="text-default-500 mt-3">{step.body}</p>
                  <div className="grid gap-3 mt-5">
                    {step.points.map((point) => (
                      <div key={point} className="flex gap-3 text-default-600">
                        <span className="mt-2 h-2 w-2 rounded-full bg-success shrink-0" aria-hidden />
                        <span>{point}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="py-8">
        <div className="max-w-6xl mx-auto px-6">
          <div className="rounded-lg border border-primary-100 bg-primary-50 p-6 md:p-8 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
            <div>
              <Chip color="primary" variant="flat">
                Ready
              </Chip>
              <h2 className="font-display text-2xl md:text-3xl font-extrabold mt-3">
                Start with the offer, then keep every change under review.
              </h2>
              <p className="text-default-500 mt-2 max-w-2xl">
                Build the tailored CV first, then reuse the same role context for interview prep.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                as={Link}
                to={primaryCta.to}
                color="primary"
                radius="full"
                className="font-semibold"
              >
                {primaryCta.label}
              </Button>
              <Button as={Link} to={secondaryCta.to} variant="bordered" color="primary" radius="full">
                {secondaryCta.label}
              </Button>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
