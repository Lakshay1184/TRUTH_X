"use client";

import React from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

interface IntelErrorBoundaryProps {
  children: React.ReactNode;
  onRetry: () => void;
  retryLabel?: string;
}

interface IntelErrorBoundaryState {
  hasError: boolean;
  message?: string;
}

export default class IntelErrorBoundary extends React.Component<
  IntelErrorBoundaryProps,
  IntelErrorBoundaryState
> {
  constructor(props: IntelErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): IntelErrorBoundaryState {
    return {
      hasError: true,
      message: error.message,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Intel runtime error boundary caught:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, message: undefined });
    this.props.onRetry();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass-card rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 text-white">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-rose-500/10">
              <AlertCircle className="h-5 w-5 text-rose-300" />
            </div>
            <div className="flex-1 space-y-4">
              <div>
                <h3 className="text-lg font-bold text-white uppercase tracking-tight italic">Source Check Rendering Fault</h3>
                <p className="mt-1 text-sm text-slate-400">
                  The analysis terminal encountered a critical visualization error. System telemetry suggest a component mismatch.
                </p>
                {this.state.message ? (
                  <p className="mt-2 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-300 font-mono">
                    ERROR_CODE: {this.state.message}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={this.handleRetry}
                  className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition-colors hover:bg-cyan-500/15"
                >
                  <RefreshCw className="h-4 w-4" />
                  {this.props.retryLabel ?? "Retry"}
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
