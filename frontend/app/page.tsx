"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
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
type Member = { email: string; workspace_id: string };
type UploadResponse = { document_id: number; created: boolean };

const questions = [
  "How many paid parental leave days do employees receive?",
  "What is the annual home office equipment allowance?",
];

class RequestError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(action: string, body?: FormData | string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/${action}`, {
    method: body === undefined ? "GET" : "POST",
    headers: typeof body === "string" ? { "Content-Type": "application/json" } : undefined,
    body,
    signal,
    cache: "no-store",
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok || data === null) {
    throw new RequestError(
      response.status,
      typeof data?.detail === "string" ? data.detail : "Request failed. Please try again.",
    );
  }
  return data as T;
}

export default function Home() {
  const [member, setMember] = useState<Member | null>(null);
  const [checking, setChecking] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    request<Member>("session", undefined, controller.signal)
      .then(setMember)
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return;
        if (!(failure instanceof RequestError && failure.status === 401)) {
          setError(failure instanceof Error ? failure.message : "Could not check your session.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false);
      });
    return () => controller.abort();
  }, []);

  async function submitAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    const password = fields.get("password");
    if (creating && password !== fields.get("confirm-password")) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      setMember(await request<Member>(creating ? "signup" : "login", JSON.stringify({
        email: fields.get("email"),
        password,
      })));
      setCreating(false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : creating ? "Could not create your account." : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await request<void>("logout", "{}");
      setMember(null);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not sign out.");
    } finally {
      setBusy(false);
    }
  }

  function expireSession() {
    setMember(null);
    setError("Your session expired. Sign in again to continue.");
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><BookOpen size={19} /></span>KnowFlow<span className="brand-ai">AI</span></div>
        {member && <div className="account">
          <span>{member.workspace_id.startsWith("personal-") ? "Personal workspace" : member.workspace_id}</span>
          <button type="button" className="secondary" disabled={busy} onClick={signOut}>Sign out</button>
        </div>}
      </header>
      {checking ? <main className="workspace"><p role="status">Checking your session…</p></main>
        : member ? <>
          {error && <p role="alert" className="session-error">{error}</p>}
          <Workspace key={member.email} onExpired={expireSession} />
        </> : <main className="signin">
          <form className="card signin-form" onSubmit={submitAccount}>
            <h1>{creating ? "Create your account" : "Sign in"}</h1>
            <p>{creating ? "Create a private workspace for your PDFs." : "Use your workspace account to access your documents."}</p>
            <label htmlFor="email">Email</label>
            <input id="email" name="email" type="email" autoComplete="username" maxLength={254} required />
            <label htmlFor="password">Password</label>
            <input
              key={creating ? "new-password" : "current-password"}
              id="password"
              name="password"
              type="password"
              autoComplete={creating ? "new-password" : "current-password"}
              minLength={creating ? 12 : undefined}
              maxLength={256}
              aria-describedby={creating ? "password-hint" : undefined}
              required
            />
            {creating && <>
              <p id="password-hint">Use at least 12 characters.</p>
              <label htmlFor="confirm-password">Confirm password</label>
              <input id="confirm-password" name="confirm-password" type="password" autoComplete="new-password" maxLength={256} required />
            </>}
            {error && <p role="alert" className="error">{error}</p>}
            <button type="submit" className="primary" disabled={busy}>
              {creating ? (busy ? "Creating account…" : "Create account") : (busy ? "Signing in…" : "Sign in")}
            </button>
            <p className="account-switch">
              {creating ? "Already have an account?" : "New to KnowFlow?"}{" "}
              <button type="button" disabled={busy} onClick={() => {
                setError("");
                setCreating(!creating);
              }}>{creating ? "Sign in" : "Sign up"}</button>
            </p>
          </form>
        </main>}
    </div>
  );
}

function Workspace({ onExpired }: { onExpired: () => void }) {
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
    if (candidate && (!candidate.name.toLowerCase().endsWith(".pdf") || candidate.size > 4_000_000)) {
      setFile(null);
      setUploadError("Choose a PDF no larger than 4 MB.");
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
      const data = await request<UploadResponse>("documents", body);
      setIndexed((items) => items.some((item) => item.id === data.document_id)
        ? items
        : [...items, { id: data.document_id, name: file.name }]);
      setUploadNotice(data.created ? "PDF indexed." : "This PDF is already indexed.");
      setFile(null);
    } catch (error) {
      if (error instanceof RequestError && error.status === 401) onExpired();
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
      setResult(await request<Answer>("ask", JSON.stringify({ question: text })));
    } catch (error) {
      if (error instanceof RequestError && error.status === 401) onExpired();
      setAskError(error instanceof Error ? error.message : "Could not get an answer.");
    } finally {
      setAsking(false);
    }
  }

  return (
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
                <span>or drop it here · up to 4 MB</span>
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
  );
}
