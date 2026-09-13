"use client";

import React, { useState, useRef, useEffect } from "react";
import { uploadDocument, fetchUploadStatus } from "@/lib/api";
import {
  Upload,
  FileText,
  X,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Clock,
} from "lucide-react";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: () => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "done" | "failed">("idle");
  const [progressMessage, setProgressMessage] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Usability pass: Escape key closes modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && status !== "uploading" && status !== "processing") {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener("keydown", handleKeyDown);
    }
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose, status]);

  // Poll job status
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (jobId && (status === "uploading" || status === "processing")) {
      const poll = async () => {
        try {
          const res = await fetchUploadStatus(jobId);
          if (res.status === "processing") {
            setStatus("processing");
            setProgressMessage(res.progress_message || "Processing PDF with Docling & generating embeddings...");
          } else if (res.status === "done") {
            setStatus("done");
            setProgressMessage("Ingestion and indexing complete.");
            onUploadSuccess();
          } else if (res.status === "failed") {
            setStatus("failed");
            setErrorMessage(res.error || "Document ingestion failed.");
          }
        } catch (err: any) {
          console.error("Polling error:", err);
        }
      };

      timer = setInterval(poll, 2500);
      poll();
    }

    return () => {
      if (timer) clearInterval(timer);
    };
  }, [jobId, status, onUploadSuccess]);

  if (!isOpen) return null;

  const handleFileSelect = (selectedFile: File) => {
    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setErrorMessage("Only PDF documents (.pdf) are supported.");
      return;
    }
    setFile(selectedFile);
    setErrorMessage(null);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async () => {
    if (!file) return;
    setStatus("uploading");
    setErrorMessage(null);
    setProgressMessage("Uploading PDF report...");

    try {
      const res = await uploadDocument(file);
      setJobId(res.job_id);
      setStatus("processing");
      setProgressMessage("Queued for Docling table extraction & embedding...");
    } catch (err: any) {
      setStatus("failed");
      setErrorMessage(err.message || "Upload failed. Check backend connection.");
    }
  };

  const handleReset = () => {
    setFile(null);
    setJobId(null);
    setStatus("idle");
    setErrorMessage(null);
    setProgressMessage("");
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 animate-settle"
      onClick={() => {
        if (status !== "uploading" && status !== "processing") onClose();
      }}
    >
      <div
        className="rich-modal relative w-full max-w-lg rounded-2xl bg-[#181C28] p-6 space-y-5 border border-white/[0.10] text-[#F1F3F9]"
        onClick={(e) => e.stopPropagation()}
        data-testid="upload-modal"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/[0.08] pb-3.5">
          <div className="flex items-center gap-2">
            <Upload className="h-4 w-4 text-[#E59500]" />
            <h3 id="upload-title" className="font-semibold text-[#F1F3F9] text-sm">
              Upload Financial Filing
            </h3>
          </div>
          <button
            onClick={onClose}
            disabled={status === "uploading" || status === "processing"}
            className="rounded-lg p-1 text-[#8C93A5] hover:bg-white/5 hover:text-[#F1F3F9] transition-colors cursor-pointer disabled:opacity-40"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Dropzone & Picker */}
        {status === "idle" && (
          <div className="space-y-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-all cursor-pointer ${
                isDragOver
                  ? "border-[#E59500] bg-[#E59500]/8"
                  : file
                  ? "border-[#E59500]/40 bg-[#13161F]"
                  : "border-white/12 bg-[#13161F] hover:border-white/20 hover:bg-[#181C28]"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files.length > 0) {
                    handleFileSelect(e.target.files[0]);
                  }
                }}
              />

              {file ? (
                <div className="flex flex-col items-center">
                  <FileText className="h-10 w-10 text-[#E59500] mb-2 stroke-[1.5]" />
                  <span className="text-xs font-medium text-[#F1F3F9]">{file.name}</span>
                  <span className="text-[11px] text-[#8C93A5] mt-0.5 tabular-nums font-mono">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                  <span className="mt-3 text-[11px] text-[#E59500] underline">
                    Choose a different PDF
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center">
                  <Upload className="h-9 w-9 text-[#8C93A5] mb-3 stroke-[1.5]" />
                  <span className="text-xs font-medium text-[#F1F3F9]">
                    Drag and drop your PDF report here
                  </span>
                  <span className="text-[11px] text-[#8C93A5] mt-1">
                    or click to browse your local filesystem
                  </span>
                  <span className="mt-3 rounded bg-white/6 px-2 py-0.5 text-[10px] text-[#8C93A5] font-mono border border-white/6">
                    SEC 10-K, 10-Q, or Annual Reports (.pdf)
                  </span>
                </div>
              )}
            </div>

            {errorMessage && (
              <div className="flex items-center gap-2 rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-3 text-xs text-[#EF4444]">
                <AlertCircle className="h-4 w-4 shrink-0 stroke-[1.8]" />
                <span>{errorMessage}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-white/10 px-3.5 py-1.5 text-xs text-[#8C93A5] hover:bg-white/5 hover:text-[#F1F3F9] cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!file}
                onClick={handleSubmit}
                data-testid="start-upload-button"
                className="rounded-lg bg-[#E59500] px-4 py-1.5 text-xs font-medium text-[#0A0B0E] hover:bg-[#F3A712] disabled:opacity-30 transition-colors cursor-pointer shadow-sm"
              >
                Process & Index Filing
              </button>
            </div>
          </div>
        )}

        {/* Processing State (Calm skeleton & status) */}
        {(status === "uploading" || status === "processing") && (
          <div className="space-y-4 py-4 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#E59500]/15 text-[#E59500] border border-[#E59500]/20">
              <Loader2 className="h-6 w-6 animate-spin text-[#E59500]" />
            </div>

            <div>
              <h4 className="font-semibold text-[#F1F3F9] text-sm">
                Ingesting Financial Report
              </h4>
              <p className="mt-1 text-xs text-[#8C93A5] leading-relaxed">
                {progressMessage || "Extracting layout tables with Docling..."}
              </p>
            </div>

            {/* Skeleton shimmer in surface-raised tone */}
            <div className="rounded-xl border border-white/[0.08] bg-[#13161F] p-4 text-left space-y-2.5">
              <div className="flex items-center justify-between text-[11px] text-[#8C93A5]">
                <span>Pipeline execution</span>
                <span className="font-mono text-[#E59500]">Async Job</span>
              </div>
              <div className="space-y-2 animate-skeleton">
                <div className="h-2 w-full rounded bg-white/8" />
                <div className="h-2 w-4/5 rounded bg-white/5" />
              </div>
              <div className="text-[10px] text-[#585E70]">
                Tables, narrative chunks, and embeddings are synced to Qdrant.
              </div>
            </div>
          </div>
        )}

        {/* Success State */}
        {status === "done" && (
          <div className="space-y-4 py-4 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
              <CheckCircle2 className="h-6 w-6 stroke-[1.8]" />
            </div>
            <div>
              <h4 className="font-semibold text-[#F1F3F9] text-sm">
                Filing Indexed Successfully
              </h4>
              <p className="mt-1 text-xs text-[#8C93A5]">
                The document is now active in the filings catalog and available for RAG verification.
              </p>
            </div>
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={() => {
                  handleReset();
                  onClose();
                }}
                className="rounded-lg bg-[#E59500] px-5 py-2 text-xs font-medium text-[#0A0B0E] hover:bg-[#F3A712] cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        )}

        {/* Failed State */}
        {status === "failed" && (
          <div className="space-y-4 py-4 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/30">
              <AlertCircle className="h-6 w-6 stroke-[1.8]" />
            </div>
            <div>
              <h4 className="font-semibold text-[#F1F3F9] text-sm">
                Ingestion Failed
              </h4>
              <p className="mt-1 text-xs text-[#EF4444] max-w-sm mx-auto leading-relaxed">
                {errorMessage || "An unexpected error occurred during processing."}
              </p>
            </div>
            <div className="flex justify-center gap-2 pt-2">
              <button
                type="button"
                onClick={handleReset}
                className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs text-[#F1F3F9] hover:bg-white/10 cursor-pointer"
              >
                Try Again
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-white/10 px-4 py-2 text-xs text-[#8C93A5] hover:text-[#F1F3F9] cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
