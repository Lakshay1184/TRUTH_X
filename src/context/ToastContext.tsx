"use client";

import { createContext, useContext, useState, ReactNode, useCallback, useEffect } from "react";

type Toast = { id: string; message: string; type?: "error" | "success" | "info" };

interface ToastContextType {
  toasts: Toast[];
  showToast: (message: string, type?: Toast["type"]) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: Toast["type"] = "info") => {
    const id = Math.random().toString(36).slice(2, 9);
    setToasts((t) => [...t, { id, message, type }]);
    // Auto-dismiss
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  useEffect(() => {
    const onUnhandledRejection = (e: PromiseRejectionEvent) => {
      showToast((e.reason && e.reason.message) || "An unexpected error occurred", "error");
      console.error("Unhandled promise rejection:", e.reason);
    };

    const onError = (e: ErrorEvent) => {
      showToast(e.message || "An unexpected error occurred", "error");
      console.error("Runtime error:", e.error || e.message);
    };

    window.addEventListener("unhandledrejection", onUnhandledRejection as any);
    window.addEventListener("error", onError as any);
    return () => {
      window.removeEventListener("unhandledrejection", onUnhandledRejection as any);
      window.removeEventListener("error", onError as any);
    };
  }, [showToast]);

  const dismissToast = useCallback((id: string) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, showToast, dismissToast }}>
      {children}
      <div className="fixed right-6 top-6 z-60 flex flex-col gap-3 pointer-events-none">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto">
            <div className={`glass-card px-4 py-3 rounded-lg border border-white/10 shadow-lg max-w-sm ${t.type === 'error' ? 'bg-rose-500/8' : t.type === 'success' ? 'bg-emerald-500/8' : 'bg-white/5'}`}>
              <div className="text-sm text-white">{t.message}</div>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
