"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  ReactNode,
  useEffect
} from "react";
import { XMarkIcon } from "@heroicons/react/24/outline";

type Toast = {
  id: string;
  message: string;
  type?: "error" | "info" | "success";
};

type ToastContextValue = {
  showToast: (message: string, type?: Toast["type"]) => void;
};

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type?: Toast["type"]) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { id, message, type }]);
  }, []);

  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => {
      setToasts((prev) => prev.slice(1));
    }, 4000);
    return () => clearTimeout(timer);
  }, [toasts]);

  const dismiss = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center px-4">
        <div className="flex w-full max-w-sm flex-col gap-2">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={[
                "pointer-events-auto flex items-start gap-2 rounded-2xl border px-3 py-2.5 text-sm shadow-lg shadow-black/40 backdrop-blur",
                toast.type === "error"
                  ? "border-rose-500/50 bg-rose-950/70 text-rose-100"
                  : toast.type === "success"
                  ? "border-emerald-500/50 bg-emerald-950/70 text-emerald-100"
                  : "border-slate-700/60 bg-slate-900/80 text-slate-100"
              ].join(" ")}
            >
              <span className="flex-1">{toast.message}</span>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="ml-1 inline-flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border border-slate-600/70 bg-slate-900/80 text-slate-300 hover:border-slate-400 hover:text-slate-100"
              >
                <XMarkIcon className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
}

