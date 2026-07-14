import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card, CardBody } from "@heroui/react";

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <section className="flex items-center justify-center p-8">
        <Card className="w-full max-w-md shadow-xl">
          <CardBody className="p-8">
            <Link to="/" className="flex items-center gap-2 font-display font-extrabold text-xl mb-6">
              <img
                src="/static/assets/autocv-logo.png"
                alt=""
                aria-hidden
                className="h-8 w-8 rounded-md"
              />
              <span>
                Auto<span className="text-primary">CV</span>
              </span>
            </Link>
            <h1 className="text-2xl font-display font-bold mb-1">{title}</h1>
            {subtitle && <p className="text-default-500 mb-6">{subtitle}</p>}
            {children}
            {footer && <div className="mt-6 text-sm text-default-500">{footer}</div>}
          </CardBody>
        </Card>
      </section>

      <aside
        aria-hidden
        className="hidden lg:flex flex-col justify-between p-12 hero-gradient"
      >
        <div>
          <span className="inline-block px-3 py-1 rounded-full bg-white/10 text-white/80 text-xs uppercase tracking-wider">
            Live CV workspace
          </span>
          <h2 className="font-display text-3xl font-extrabold mt-4 leading-tight">
            Tailor your CV to <span className="grad-word">any job offer</span> — in seconds.
          </h2>
          <p className="text-white/80 mt-3 max-w-md">
            Paste an offer, upload your LaTeX CV, and review matched skills, rewritten sections, and
            a PDF preview in one workspace.
          </p>
        </div>
        <ul className="text-white/85 space-y-2 text-sm">
          <li>✓ Matched skills & ATS-style breakdown</li>
          <li>✓ Per-section rewrites with accept / reject</li>
          <li>✓ One-click PDF, Word, or LaTeX export</li>
        </ul>
      </aside>
    </div>
  );
}
