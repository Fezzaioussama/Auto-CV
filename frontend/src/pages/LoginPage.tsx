import { useState, FormEvent, useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Input, Button } from "@heroui/react";
import { AuthShell } from "../layouts/AuthShell";
import { api, apiErrorMessage } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next") || "/optimizer";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) navigate(next, { replace: true });
  }, [user, navigate, next]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ success: boolean; redirect?: string; error?: string }>(
        "/login",
        { email, password },
      );
      if (r.data.success) {
        await refresh();
        navigate(r.data.redirect || next, { replace: true });
      } else {
        setError(r.data.error || "Could not sign in.");
      }
    } catch (err) {
      setError(apiErrorMessage(err, "Could not sign in."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your tailored CVs, saved jobs and history."
      footer={
        <span>
          No account yet?{" "}
          <Link to="/register" className="text-primary font-medium">
            Create one
          </Link>
        </span>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="text-sm bg-danger-50 text-danger-700 border border-danger-200 rounded-md px-3 py-2">
            {error}
          </div>
        )}
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          isRequired
          value={email}
          onValueChange={setEmail}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          isRequired
          value={password}
          onValueChange={setPassword}
        />
        <div className="text-right text-sm">
          <Link to="/forgot-password" className="text-primary">
            Forgot password?
          </Link>
        </div>
        <Button type="submit" color="primary" isLoading={busy} className="mt-2 font-semibold">
          Sign in
        </Button>
      </form>
    </AuthShell>
  );
}
