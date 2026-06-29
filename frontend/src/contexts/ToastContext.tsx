import { createContext, useCallback, useContext, useState, ReactNode } from "react";

type ToastKind = "info" | "success" | "error";
type Toast = { id: number; message: string; kind: ToastKind };

type ToastCtx = {
  push: (message: string, kind?: ToastKind) => void;
};

const Ctx = createContext<ToastCtx | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((message: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setToasts((curr) => [...curr, { id, message, kind }]);
    setTimeout(() => setToasts((curr) => curr.filter((t) => t.id !== id)), 4500);
  }, []);

  return (
    <Ctx.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={[
              "min-w-[240px] max-w-sm rounded-lg px-4 py-3 text-sm shadow-lg backdrop-blur",
              t.kind === "error"
                ? "bg-danger-50 text-danger-700 border border-danger-200"
                : t.kind === "success"
                  ? "bg-success-50 text-success-700 border border-success-200"
                  : "bg-default-50 text-default-700 border border-default-200",
            ].join(" ")}
          >
            {t.message}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
