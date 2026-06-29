import { useState, FormEvent } from "react";
import { Link } from "react-router-dom";
import { Input, Button } from "@heroui/react";
import { AuthShell } from "../layouts/AuthShell";
import { api, apiErrorMessage } from "../lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const r = await api.post<{ success: boolean; message?: string; error?: string }>(
        "/forgot-password",
        { email },
      );
      if (r.data.success) {
        setMessage(r.data.message || "If that email has an account, a reset link is on its way.");
      } else {
        setError(r.data.error || "Could not send the reset link.");
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Forgot your password?"
      subtitle="Enter your email and we'll send a link to set a new one."
      footer={
        <Link to="/login" className="text-primary font-medium">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="text-sm bg-danger-50 text-danger-700 border border-danger-200 rounded-md px-3 py-2">
            {error}
          </div>
        )}
        {message && (
          <div className="text-sm bg-primary-50 text-primary-700 border border-primary-200 rounded-md px-3 py-2">
            {message}
          </div>
        )}
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          isRequired
          autoFocus
          value={email}
          onValueChange={setEmail}
        />
        <Button type="submit" color="primary" isLoading={busy} className="mt-2 font-semibold">
          Send reset link
        </Button>
      </form>
    </AuthShell>
  );
}
