import { useState, FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Input, Button } from "@heroui/react";
import { AuthShell } from "../layouts/AuthShell";
import { api, apiErrorMessage } from "../lib/api";

export default function ResetPasswordPage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ success: boolean; message?: string; error?: string }>(
        `/reset-password/${encodeURIComponent(token)}`,
        { password },
      );
      if (r.data.success) {
        navigate("/login", { replace: true });
      } else {
        setError(r.data.error || "Could not reset password.");
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Choose a new password"
      subtitle="Pick a strong password of at least 8 characters."
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
        <Input
          label="New password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          isRequired
          autoFocus
          value={password}
          onValueChange={setPassword}
        />
        <Button type="submit" color="primary" isLoading={busy} className="mt-2 font-semibold">
          Update password
        </Button>
      </form>
    </AuthShell>
  );
}
