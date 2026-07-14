import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Chip,
  Divider,
  Input,
} from "@heroui/react";
import { AppShell } from "../layouts/AppShell";
import { api, apiErrorMessage } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";

export default function AccountPage() {
  const { user, refresh, setUser } = useAuth();
  const { push } = useToast();
  const navigate = useNavigate();

  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew, setPwNew] = useState("");
  const [pwBusy, setPwBusy] = useState(false);

  const [emNew, setEmNew] = useState("");
  const [emPw, setEmPw] = useState("");
  const [emBusy, setEmBusy] = useState(false);

  const [delPw, setDelPw] = useState("");
  const [delBusy, setDelBusy] = useState(false);

  const [resendBusy, setResendBusy] = useState(false);

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    setPwBusy(true);
    try {
      const r = await api.post<{ message?: string }>("/api/account/password", {
        current_password: pwCurrent,
        new_password: pwNew,
      });
      push(r.data.message || "Password updated.", "success");
      setPwCurrent("");
      setPwNew("");
    } catch (err) {
      push(apiErrorMessage(err, "Could not update password."), "error");
    } finally {
      setPwBusy(false);
    }
  }

  async function changeEmail(e: FormEvent) {
    e.preventDefault();
    setEmBusy(true);
    try {
      const r = await api.post<{ message?: string }>("/api/account/email", {
        email: emNew,
        password: emPw,
      });
      push(r.data.message || "Email updated.", "success");
      setEmNew("");
      setEmPw("");
      refresh();
    } catch (err) {
      push(apiErrorMessage(err, "Could not update email."), "error");
    } finally {
      setEmBusy(false);
    }
  }

  async function logoutOthers() {
    if (!confirm("Sign out of all other devices? You'll stay signed in here.")) return;
    try {
      const r = await api.post<{ message?: string }>("/api/account/logout-others");
      push(r.data.message || "Signed out other devices.", "success");
    } catch (err) {
      push(apiErrorMessage(err, "Could not sign out other devices."), "error");
    }
  }

  async function resendVerification() {
    setResendBusy(true);
    try {
      const r = await api.post<{ message?: string }>("/resend-verification");
      push(r.data.message || "Confirmation email sent.", "success");
    } catch (err) {
      push(apiErrorMessage(err, "Could not resend."), "error");
    } finally {
      setResendBusy(false);
    }
  }

  async function deleteAccount(e: FormEvent) {
    e.preventDefault();
    if (!confirm("Delete your account and all data permanently? This cannot be undone.")) return;
    setDelBusy(true);
    try {
      const r = await api.post<{ redirect?: string }>("/api/account/delete", { password: delPw });
      setUser(null);
      navigate(r.data.redirect || "/login", { replace: true });
    } catch (err) {
      push(apiErrorMessage(err, "Could not delete account."), "error");
    } finally {
      setDelBusy(false);
    }
  }

  return (
    <AppShell>
      <section className="max-w-3xl mx-auto px-6 py-12 space-y-6">
        <div>
          <Chip color="primary" variant="flat">
            Your account
          </Chip>
          <h1 className="font-display text-3xl font-extrabold mt-3">Account & privacy</h1>
          <p className="text-default-500 mt-2">Manage your sign-in details and your data.</p>
        </div>

        {user && !user.email_verified && (
          <Card className="border border-warning-200 bg-warning-50">
            <CardBody className="flex items-center justify-between gap-2 flex-wrap">
              <div>Your email isn't confirmed yet.</div>
              <Button
                size="sm"
                color="warning"
                variant="flat"
                isLoading={resendBusy}
                onPress={resendVerification}
              >
                Resend confirmation link
              </Button>
            </CardBody>
          </Card>
        )}

        <Card className="border border-default-200">
          <CardHeader>
            <h3 className="font-display text-lg font-bold">Profile</h3>
          </CardHeader>
          <CardBody>
            <p className="text-default-600">
              Signed in as <strong>{user?.email}</strong>{" "}
              <Chip
                size="sm"
                color={user?.email_verified ? "success" : "default"}
                variant="flat"
                className="ml-2"
              >
                {user?.email_verified ? "confirmed" : "unconfirmed"}
              </Chip>
            </p>
          </CardBody>
        </Card>

        <Card className="border border-default-200">
          <CardHeader>
            <h3 className="font-display text-lg font-bold">Change password</h3>
          </CardHeader>
          <CardBody>
            <form onSubmit={changePassword} className="space-y-3">
              <Input
                type="password"
                label="Current password"
                value={pwCurrent}
                onValueChange={setPwCurrent}
                autoComplete="current-password"
                isRequired
              />
              <Input
                type="password"
                label="New password"
                value={pwNew}
                onValueChange={setPwNew}
                autoComplete="new-password"
                minLength={8}
                isRequired
              />
              <Button type="submit" color="primary" isLoading={pwBusy}>
                Update password
              </Button>
            </form>
          </CardBody>
        </Card>

        <Card className="border border-default-200">
          <CardHeader>
            <h3 className="font-display text-lg font-bold">Change email</h3>
          </CardHeader>
          <CardBody>
            <form onSubmit={changeEmail} className="space-y-3">
              <Input
                type="email"
                label="New email"
                value={emNew}
                onValueChange={setEmNew}
                autoComplete="email"
                isRequired
              />
              <Input
                type="password"
                label="Confirm with your password"
                value={emPw}
                onValueChange={setEmPw}
                autoComplete="current-password"
                isRequired
              />
              <Button type="submit" color="primary" isLoading={emBusy}>
                Update email
              </Button>
            </form>
          </CardBody>
        </Card>

        <Card className="border border-default-200">
          <CardHeader>
            <h3 className="font-display text-lg font-bold">Sign out other devices</h3>
          </CardHeader>
          <CardBody className="space-y-2">
            <p className="text-default-500 text-sm">
              End every other active session. You'll stay signed in here.
            </p>
            <Button variant="bordered" onPress={logoutOthers}>
              Sign out of all other devices
            </Button>
          </CardBody>
        </Card>

        <Card className="border border-default-200">
          <CardHeader>
            <h3 className="font-display text-lg font-bold">Export your data</h3>
          </CardHeader>
          <CardBody>
            <p className="text-default-500 text-sm mb-2">
              Download everything we store about you as JSON.
            </p>
            <Button as="a" variant="bordered" href="/api/account/export">
              Download my data
            </Button>
          </CardBody>
        </Card>

        <Card className="border border-danger-200">
          <CardHeader>
            <h3 className="font-display text-lg font-bold text-danger">Delete account</h3>
          </CardHeader>
          <CardBody>
            <p className="text-default-500 text-sm mb-3">
              Permanently deletes your account and all associated data. This cannot be undone.
            </p>
            <form onSubmit={deleteAccount} className="space-y-3">
              <Input
                type="password"
                label="Confirm with your password"
                value={delPw}
                onValueChange={setDelPw}
                autoComplete="current-password"
                isRequired
              />
              <Button type="submit" color="danger" isLoading={delBusy}>
                Delete my account permanently
              </Button>
            </form>
          </CardBody>
        </Card>

        <Divider />
      </section>
    </AppShell>
  );
}
