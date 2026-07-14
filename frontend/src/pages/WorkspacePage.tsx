import { useEffect, useState } from "react";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Chip,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
  Select,
  SelectItem,
  Textarea,
  useDisclosure,
} from "@heroui/react";
import { AppShell } from "../layouts/AppShell";
import { api, apiErrorMessage } from "../lib/api";
import { useToast } from "../contexts/ToastContext";

type Job = {
  id: number;
  title?: string;
  company?: string;
  status: string;
  url?: string;
  notes?: string;
  created_at?: string;
  applied_at?: string;
};

type CVVersion = {
  id: number;
  label: string;
  created_at?: string;
  latex?: string;
};

type CVDocument = {
  id: number;
  name: string;
  updated_at?: string;
  versions?: CVVersion[];
};

const STATUSES = ["saved", "applied", "interviewing", "offer", "rejected"];

export default function WorkspacePage() {
  const { push } = useToast();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [docs, setDocs] = useState<CVDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [versionLatex, setVersionLatex] = useState("");
  const [versionLabel, setVersionLabel] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [j, c] = await Promise.all([
        api.get<{ jobs: Job[] }>("/api/jobs"),
        api.get<{ documents: CVDocument[] }>("/api/cv"),
      ]);
      setJobs(j.data.jobs || []);
      setDocs(c.data.documents || []);
    } catch (err) {
      push(apiErrorMessage(err, "Could not load workspace."), "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function updateStatus(job: Job, status: string) {
    try {
      await api.patch(`/api/jobs/${job.id}`, { status });
      setJobs((curr) => curr.map((j) => (j.id === job.id ? { ...j, status } : j)));
    } catch (err) {
      push(apiErrorMessage(err, "Could not update job."), "error");
    }
  }

  async function deleteJob(job: Job) {
    if (!confirm(`Delete the saved job "${job.title || job.company || "Untitled"}"?`)) return;
    try {
      await api.delete(`/api/jobs/${job.id}`);
      setJobs((curr) => curr.filter((j) => j.id !== job.id));
    } catch (err) {
      push(apiErrorMessage(err, "Could not delete."), "error");
    }
  }

  async function deleteDoc(doc: CVDocument) {
    if (!confirm(`Delete "${doc.name}" and all its versions?`)) return;
    try {
      await api.delete(`/api/cv/${doc.id}`);
      setDocs((curr) => curr.filter((d) => d.id !== doc.id));
    } catch (err) {
      push(apiErrorMessage(err, "Could not delete."), "error");
    }
  }

  async function viewVersion(versionId: number, label: string) {
    try {
      const r = await api.get<{ version: { latex: string } }>(`/api/cv/versions/${versionId}`);
      setVersionLatex(r.data.version.latex || "");
      setVersionLabel(label);
      onOpen();
    } catch (err) {
      push(apiErrorMessage(err, "Could not load version."), "error");
    }
  }

  async function restoreVersion(versionId: number) {
    try {
      await api.post(`/api/cv/versions/${versionId}/restore`);
      push("Version restored.", "success");
      load();
    } catch (err) {
      push(apiErrorMessage(err, "Could not restore."), "error");
    }
  }

  return (
    <AppShell>
      <section className="max-w-6xl mx-auto px-6 py-12">
        <div className="text-center mb-8">
          <Chip color="primary" variant="flat">
            Your workspace
          </Chip>
          <h1 className="font-display text-3xl md:text-4xl font-extrabold mt-3">
            Saved jobs & CV versions
          </h1>
          <p className="text-default-500 mt-2">
            Everything you tailor and save lives here — revisit, restore, or clean up.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <div>
            <h2 className="font-display text-lg font-bold mb-3">Saved jobs</h2>
            {loading && <p className="text-default-500">Loading…</p>}
            {!loading && jobs.length === 0 && (
              <p className="text-default-500">No jobs saved yet. Save one from the optimizer.</p>
            )}
            <div className="space-y-3">
              {jobs.map((j) => (
                <Card key={j.id} className="border border-default-200">
                  <CardBody className="space-y-2">
                    <div className="flex justify-between gap-2 flex-wrap">
                      <div>
                        <div className="font-semibold">{j.title || "Untitled role"}</div>
                        {j.company && (
                          <div className="text-sm text-default-500">{j.company}</div>
                        )}
                      </div>
                      <Chip size="sm" variant="flat" color="primary">
                        {j.status}
                      </Chip>
                    </div>
                    {j.url && (
                      <a
                        href={j.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-primary text-sm break-all"
                      >
                        {j.url}
                      </a>
                    )}
                    <div className="flex flex-wrap gap-2 items-center pt-1">
                      <Select
                        size="sm"
                        className="max-w-[160px]"
                        selectedKeys={[j.status]}
                        onSelectionChange={(keys) =>
                          updateStatus(j, String(Array.from(keys)[0] || j.status))
                        }
                        aria-label="status"
                      >
                        {STATUSES.map((s) => (
                          <SelectItem key={s}>{s}</SelectItem>
                        ))}
                      </Select>
                      <Button size="sm" color="danger" variant="bordered" onPress={() => deleteJob(j)}>
                        Delete
                      </Button>
                    </div>
                  </CardBody>
                </Card>
              ))}
            </div>
          </div>

          <div>
            <h2 className="font-display text-lg font-bold mb-3">Saved CVs</h2>
            {loading && <p className="text-default-500">Loading…</p>}
            {!loading && docs.length === 0 && (
              <p className="text-default-500">No CV versions yet.</p>
            )}
            <div className="space-y-3">
              {docs.map((d) => (
                <Card key={d.id} className="border border-default-200">
                  <CardHeader className="flex justify-between gap-2 flex-wrap">
                    <div>
                      <div className="font-semibold">{d.name}</div>
                      {d.updated_at && (
                        <div className="text-xs text-default-500">Updated {d.updated_at}</div>
                      )}
                    </div>
                    <Button size="sm" color="danger" variant="bordered" onPress={() => deleteDoc(d)}>
                      Delete
                    </Button>
                  </CardHeader>
                  <CardBody className="space-y-2">
                    {(d.versions || []).map((v) => (
                      <div
                        key={v.id}
                        className="flex justify-between items-center gap-2 border rounded-md px-3 py-2"
                      >
                        <div>
                          <div className="text-sm font-medium">{v.label}</div>
                          {v.created_at && (
                            <div className="text-xs text-default-500">{v.created_at}</div>
                          )}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="bordered"
                            onPress={() => viewVersion(v.id, v.label)}
                          >
                            View
                          </Button>
                          <Button
                            size="sm"
                            variant="flat"
                            color="primary"
                            onPress={() => restoreVersion(v.id)}
                          >
                            Restore
                          </Button>
                        </div>
                      </div>
                    ))}
                  </CardBody>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </section>

      <Modal isOpen={isOpen} onClose={onClose} size="3xl" scrollBehavior="inside">
        <ModalContent>
          <ModalHeader>{versionLabel}</ModalHeader>
          <ModalBody>
            <Textarea
              minRows={18}
              value={versionLatex}
              readOnly
              classNames={{ input: "font-mono text-xs" }}
            />
          </ModalBody>
          <ModalFooter>
            <Button
              variant="bordered"
              color="primary"
              onPress={() => {
                navigator.clipboard.writeText(versionLatex);
                push("Copied to clipboard.", "success");
              }}
            >
              Copy LaTeX
            </Button>
            <Button onPress={onClose}>Close</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </AppShell>
  );
}
