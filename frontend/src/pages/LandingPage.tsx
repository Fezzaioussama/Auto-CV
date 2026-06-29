import { Link } from "react-router-dom";
import { Button, Card, CardBody, Chip } from "@heroui/react";
import { AppShell } from "../layouts/AppShell";
import { useAuth } from "../contexts/AuthContext";

const STEPS = [
  {
    num: "01",
    title: "Analyze the offer",
    body: "Auto-CV extracts the key skills, requirements and qualifications the role asks for.",
  },
  {
    num: "02",
    title: "Match your CV",
    body: "See your match score, which skills land, and which signals are still missing.",
  },
  {
    num: "03",
    title: "Review and export",
    body: "Edit the optimized LaTeX, render a PDF preview, then download or copy the final source.",
  },
];

export default function LandingPage() {
  const { user } = useAuth();
  const primaryCta = user ? { to: "/optimizer", label: "Open optimizer" } : { to: "/register", label: "Create free account" };

  return (
    <AppShell>
      <section className="hero-gradient text-white">
        <div className="max-w-6xl mx-auto px-6 py-20 grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <Chip color="default" variant="flat" className="bg-white/15 text-white">
              LaTeX-native CV optimization
            </Chip>
            <h1 className="font-display text-4xl md:text-5xl font-extrabold leading-tight mt-4">
              Adapt your CV to the role without losing your facts.
            </h1>
            <p className="text-lg text-white/85 mt-4 max-w-xl">
              Paste the offer, upload your LaTeX CV, and review matched skills, rewritten sections,
              optional additions, and a PDF preview — all in one workspace.
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
                to="/demo"
                size="lg"
                radius="full"
                variant="bordered"
                className="text-white border-white/40"
              >
                Try a live demo
              </Button>
            </div>
          </div>

          <Card className="bg-white/10 backdrop-blur border border-white/15 text-white shadow-2xl">
            <CardBody className="p-6">
              <div className="flex justify-between text-sm text-white/70 mb-4">
                <span>Workspace</span>
                <span>★ AI assist</span>
              </div>
              <ul className="space-y-4">
                <li className="flex gap-3 items-start">
                  <span className="h-2.5 w-2.5 mt-2 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,.25)]" />
                  <div>
                    <strong>Offer analysis</strong>
                    <div className="text-white/70 text-sm">Skills, requirements, qualifications</div>
                  </div>
                </li>
                <li className="flex gap-3 items-start">
                  <span className="h-2.5 w-2.5 mt-2 rounded-full bg-white/50" />
                  <div>
                    <strong>CV matching</strong>
                    <div className="text-white/70 text-sm">Coverage and missing signals</div>
                  </div>
                </li>
                <li className="flex gap-3 items-start">
                  <span className="h-2.5 w-2.5 mt-2 rounded-full bg-white/50" />
                  <div>
                    <strong>Review and export</strong>
                    <div className="text-white/70 text-sm">Editable LaTeX with PDF preview</div>
                  </div>
                </li>
              </ul>
              <div className="grid grid-cols-2 gap-4 mt-6 pt-6 border-t border-white/10">
                <div>
                  <div className="text-3xl font-extrabold">3</div>
                  <div className="text-white/70 text-sm">guided steps</div>
                </div>
                <div>
                  <div className="text-3xl font-extrabold">0</div>
                  <div className="text-white/70 text-sm">facts invented</div>
                </div>
              </div>
            </CardBody>
          </Card>
        </div>
      </section>

      <section className="py-20">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-12">
            <Chip color="primary" variant="flat">
              How it works
            </Chip>
            <h2 className="font-display text-3xl md:text-4xl font-extrabold mt-3">
              From offer to tailored PDF
            </h2>
            <p className="text-default-500 mt-2">
              A guided three-step flow. You stay in control of every change.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {STEPS.map((s) => (
              <Card key={s.num} className="border border-default-200">
                <CardBody className="p-6">
                  <div className="text-xs font-mono text-primary tracking-widest">STEP {s.num}</div>
                  <h3 className="font-display text-xl font-bold mt-2">{s.title}</h3>
                  <p className="text-default-500 mt-2">{s.body}</p>
                </CardBody>
              </Card>
            ))}
          </div>
          <div className="text-center mt-10">
            <Button
              as={Link}
              to="/how-it-works"
              variant="bordered"
              color="primary"
              radius="full"
            >
              See the full visual guide
            </Button>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
