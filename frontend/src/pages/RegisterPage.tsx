import { useState, FormEvent, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Input, Button } from "@heroui/react";
import { AuthShell } from "../layouts/AuthShell";
import { api, apiErrorMessage } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";

export default function RegisterPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) navigate("/optimizer", { replace: true });
  }, [user, navigate]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const r = await api.post<{
        success: boolean;
        error?: string;
        message?: string;
        verify_required?: boolean;
        redirect?: string;
      }>("/register", { name, email, password });
      if (r.data.success) {
        if (r.data.verify_required) {
          setInfo(r.data.message || "Check your email to confirm before signing in.");
          return;
        }
        await refresh();
        navigate(r.data.redirect || "/optimizer", { replace: true });
      } else {
        setError(r.data.error || "Could not create the account.");
      }
    } catch (err) {
      setError(apiErrorMessage(err, "Could not create the account."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Save tailored CVs, track jobs, and pick up where you left off."
      footer={
        <span>
          Already have an account?{" "}
          <Link to="/login" className="text-primary font-medium">
            Sign in
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
        {info && (
          <div className="text-sm bg-primary-50 text-primary-700 border border-primary-200 rounded-md px-3 py-2">
            {info}
          </div>
        )}
        <Input label="Name (optional)" autoComplete="name" value={name} onValueChange={setName} />
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
          autoComplete="new-password"
          isRequired
          minLength={8}
          description="At least 8 characters."
          value={password}
          onValueChange={setPassword}
        />
        <Button type="submit" color="primary" isLoading={busy} className="mt-2 font-semibold">
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}
