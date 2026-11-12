"use client";

import { useRef, useState, type FormEvent } from "react";
import {
  ArrowDownRight, ArrowUp, BookOpen, Check, FileText, LoaderCircle,
  Paperclip, Quote, Upload, X,
} from "lucide-react";

type Citation = {
  chunk_id: number;
  title: string;
  page_number: number;
  text: string;
};

type Answer = { answer: string; citations: Citation[] };
type IndexedFile = { id: number; name: string };
type UploadResponse = { document_id: number; created: boolean };

const questions = [
  "How many paid parental leave days do employees receive?",
  "What is the annual home office equipment allowance?",
];

async function post<T>(action: string, body: FormData | string): Promise<T> {
  const response = await fetch(`/api/${action}`, {
    method: "POST",
    headers: typeof body === "string" ? { "Content-Type": "application/json" } : undefined,
    body,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok || data === null) {
    throw new Error(typeof data?.detail === "string" ? data.detail : "Request failed. Please try again.");
  }
  return data as T;
}

export default function Workspace() {
  const [file, setFile] = useState<File | null>(null);
  const [indexed, setIndexed] = useState<IndexedFile[]>([]);
  const [uploadNotice, setUploadNotice] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState("");
  const [result, setResult] = useState<Answer | null>(null);
  const [askError, setAskError] = useState("");
  const [asking, setAsking] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const questionInput = useRef<HTMLInputElement>(null);

  function selectFile(candidate: File | null) {
    setUploadNotice("");
    setUploadError("");
    if (candidate && (!candidate.name.toLowerCase().endsWith(".pdf") || candidate.size > 10 * 1024 * 1024)) {
      setFile(null);
      setUploadError("Choose a PDF no larger than 10 MiB.");
      return;
    }
    setFile(candidate);
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || uploading) return;
    setUploading(true);
    setUploadNotice("");
    setUploadError("");
    const body = new FormData();
    body.append("file", file);
    try {
      const data = await post<UploadResponse>("documents", body);
      setIndexed((items) => items.some((item) => item.id === data.document_id)
        ? items
        : [...items, { id: data.document_id, name: file.name }]);
      setUploadNotice(data.created ? "PDF indexed." : "This PDF is already indexed.");
      setFile(null);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text || asking) return;
    setAsked(text);
    setResult(null);
    setAskError("");
    setAsking(true);
    try {
      setResult(await post<Answer>("ask", JSON.stringify({ question: text })));
    } catch (error) {
      setAskError(error instanceof Error ? error.message : "Could not get an answer.");
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><BookOpen size={19} /></span>KnowFlow<span className="brand-ai">AI</span></div>
      </header>

      <main className="workspace">
        <div className="heading">
          <h1>Knowledge workspace</h1>
          <p>Ask questions about your PDFs and trace each answer to the source.</p>
        </div>

        <div className="columns">
          <aside className="card documents" aria-labelledby="documents-title">
            <div className="section-label"><FileText size={17} /><h2 id="documents-title">Documents</h2></div>
            <form onSubmit={upload} className="upload-form">
              <input
                ref={fileInput}
                type="file"
                accept=".pdf,application/pdf"
                aria-label="Select PDF"
                className="visually-hidden"
                tabIndex={-1}
                disabled={uploading}
                onChange={(event) => {
                  selectFile(event.currentTarget.files?.[0] ?? null);
                  event.currentTarget.value = "";
                }}
              />
              {file ? (
                <div className="selected-file">
                  <Paperclip size={17} />
                  <span>{file.name}</span>
                  <button type="button" className="icon-button" aria-label="Remove selected PDF" disabled={uploading} onClick={() => selectFile(null)}><X size={16} /></button>
                </div>
              ) : (
                <button
                  className="file-picker"
                  type="button"
                  disabled={uploading}
                  onClick={() => fileInput.current?.click()}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    if (!uploading) selectFile(event.dataTransfer.files[0] ?? null);
                  }}
                >
                  <span className="upload-icon"><Upload size={18} /></span>
                  <strong>Choose a PDF</strong>
                  <span>or drop it here · up to 10 MiB</span>
                </button>
              )}
              {file && <button className="primary upload-button" disabled={uploading} type="submit">
                {uploading ? <LoaderCircle className="spinner" size={16} /> : <Upload size={16} />}
                {uploading ? "Indexing PDF…" : "Upload PDF"}
              </button>}
              {uploadNotice && <p role="status" className="notice"><Check size={15} />{uploadNotice}</p>}
              {uploadError && <p role="alert" className="error">{uploadError}</p>}
            </form>

            {indexed.length > 0 && <div className="indexed">
              <h3>PDFs added this session</h3>
              <ul>
                {indexed.map((item) => <li key={item.id}><FileText size={16} /><span>{item.name}</span><Check size={14} className="indexed-check" /></li>)}
              </ul>
            </div>}
          </aside>

          <section className="card ask" aria-labelledby="ask-title">
            <div className="section-label ask-label"><Quote size={17} /><h2 id="ask-title">Ask your documents</h2></div>
            <div className="answer-area">
              {!asked ? <div className="empty">
                <span className="empty-icon"><BookOpen size={28} strokeWidth={1.65} /></span>
                <h3>What would you like to know?</h3>
                <p>Using the sample handbook? Try a question below.</p>
                <div className="suggestions">
                  {questions.map((sample) => <button type="button" key={sample} onClick={() => {
                    setQuestion(sample);
                    questionInput.current?.focus();
                  }}><ArrowDownRight size={16} />{sample}</button>)}
                </div>
              </div> : <div className="conversation">
                <p className="question-bubble">{asked}</p>
                {asking && <p role="status" className="loading"><LoaderCircle size={18} className="spinner" />Looking for supporting passages…</p>}
                {askError && <p role="alert" className="error">{askError}</p>}
                <div aria-live="polite">{result && <div className="result">
                  <h3>Answer</h3>
                  <p className="answer-text">{result.answer}</p>
                  {result.citations.length > 0 && <div className="sources">
                    <h3>Sources</h3>
                    <ul>
                      {result.citations.map((source) => <li key={source.chunk_id}>
                        <div className="source-heading"><FileText size={16} /><strong>{source.title}</strong><span>Page {source.page_number}</span></div>
                        <blockquote>{source.text}</blockquote>
                      </li>)}
                    </ul>
                  </div>}
                </div>}</div>
              </div>}
            </div>

            <form className="question-form" onSubmit={ask}>
              <label htmlFor="question" className="visually-hidden">Question</label>
              <input id="question" ref={questionInput} placeholder="Ask a question about your documents…" value={question} maxLength={2000} onChange={(event) => setQuestion(event.target.value)} />
              <button className="primary send" type="submit" disabled={!question.trim() || asking} aria-label="Ask question">
                {asking ? <LoaderCircle size={19} className="spinner" /> : <ArrowUp size={20} />}
              </button>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}
