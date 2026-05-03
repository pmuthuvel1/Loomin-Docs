"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bot, Check, FilePlus2, Files, Highlighter, Loader2, Save, Sparkles, TextQuote, Upload, Wand2 } from "lucide-react";
import { AiResponse, api, DocSummary, RagFile } from "../lib/api";

const headerColors = ["#1677ff", "#0f8f62", "#b45309", "#b42318", "#6f42c1"];
const models = [
  { id: "llama3-local", label: "Llama3" },
  { id: "mistral-local", label: "Mistral" }
];

function htmlFromMarkdown(input: string) {
  return input
    .split("\n")
    .map((line, index) => {
      const escaped = line.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
      if (line.startsWith("### ")) return `<h3 style="color:${headerColors[index % headerColors.length]}">${escaped.slice(4)}</h3>`;
      if (line.startsWith("## ")) return `<h2 style="color:${headerColors[index % headerColors.length]}">${escaped.slice(3)}</h2>`;
      if (line.startsWith("# ")) return `<h1 style="color:${headerColors[index % headerColors.length]}">${escaped.slice(2)}</h1>`;
      if (line.trim() === "") return "<p><br /></p>";
      return `<p>${escaped.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\*(.*?)\*/g, "<em>$1</em>")}</p>`;
    })
    .join("");
}

function markdownFromHtml(html: string) {
  const div = document.createElement("div");
  div.innerHTML = html;
  return Array.from(div.childNodes)
    .map((node) => {
      if (node instanceof HTMLHeadingElement) return `${"#".repeat(Number(node.tagName.slice(1)))} ${node.textContent ?? ""}`;
      return node.textContent ?? "";
    })
    .join("\n");
}

export default function Home() {
  const [user, setUser] = useState("alice");
  const [docs, setDocs] = useState<DocSummary[]>([]);
  const [files, setFiles] = useState<RagFile[]>([]);
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [title, setTitle] = useState("Untitled");
  const [content, setContent] = useState("# Untitled\n\nStart writing...");
  const [selectedText, setSelectedText] = useState("");
  const [tab, setTab] = useState<"docs" | "files">("docs");
  const [model, setModel] = useState("llama3-local");
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; text: string; meta?: AiResponse }>>([]);
  const editorRef = useRef<HTMLDivElement>(null);

  const tokenPercent = useMemo(() => {
    const docTokens = Math.ceil(content.length / 4);
    const ragTokens = Math.min(1800, files.length * 220);
    return Math.min(100, Math.round(((docTokens + ragTokens) / 8192) * 100));
  }, [content, files.length]);

  useEffect(() => {
    refresh();
  }, [user]);

  async function refresh() {
    const [nextDocs, nextFiles] = await Promise.all([api.listDocs(user), api.listFiles(user)]);
    setDocs(nextDocs);
    setFiles(nextFiles);
  }

  async function openDoc(id: number) {
    const doc = await api.getDoc(user, id);
    setActiveDocId(doc.id);
    setTitle(doc.title);
    setContent(doc.content);
    setTimeout(() => {
      if (editorRef.current) editorRef.current.innerHTML = htmlFromMarkdown(doc.content);
    });
  }

  async function saveDoc(returnToGrid = false) {
    const html = editorRef.current?.innerHTML ?? htmlFromMarkdown(content);
    const nextContent = markdownFromHtml(html);
    const saved = await api.saveDoc(user, activeDocId, title, nextContent);
    setActiveDocId(saved.id);
    setContent(nextContent);
    await refresh();
    if (returnToGrid) setActiveDocId(null);
  }

  function newDoc() {
    setActiveDocId(-1);
    setTitle("New document");
    setContent("# New document\n\n");
    setTimeout(() => {
      if (editorRef.current) editorRef.current.innerHTML = htmlFromMarkdown("# New document\n\n");
    });
  }

  function captureSelection() {
    const selection = window.getSelection()?.toString().trim() ?? "";
    if (selection) setSelectedText(selection);
  }

  function applyReplacement(text: string) {
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0 && editorRef.current?.contains(selection.anchorNode)) {
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const fragment = range.createContextualFragment(htmlFromMarkdown(text));
      range.insertNode(fragment);
      selection.removeAllRanges();
    } else if (editorRef.current) {
      editorRef.current.insertAdjacentHTML("beforeend", htmlFromMarkdown(`\n${text}`));
    }
    colorizeHeaders();
  }

  function colorizeHeaders() {
    editorRef.current?.querySelectorAll("h1,h2,h3").forEach((h, i) => {
      (h as HTMLElement).style.color = headerColors[i % headerColors.length];
      h.classList.add("detected-header");
    });
  }

  async function runAi(action: "chat" | "summarize" | "improve") {
    setBusy(true);
    const doc = markdownFromHtml(editorRef.current?.innerHTML ?? "");
    const question = action === "chat" ? prompt : `${action} this selection`;
    setMessages((m) => [...m, { role: "user", text: question }]);
    try {
      const res = await api.askAi(user, {
        action,
        model,
        question,
        document: doc,
        selection: selectedText
      });
      setMessages((m) => [...m, { role: "assistant", text: res.answer, meta: res }]);
      if (res.replacement && action !== "chat") applyReplacement(res.replacement);
      setPrompt("");
    } finally {
      setBusy(false);
    }
  }

  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    await api.uploadFile(user, file);
    await refresh();
    e.target.value = "";
  }

  if (activeDocId === null) {
    return (
      <main className="shell">
        <header className="topbar">
          <div>
            <p className="eyebrow">Private workspace</p>
            <h1>Loomin Docs</h1>
          </div>
          <div className="userSwitch">
            <button className={user === "alice" ? "active" : ""} onClick={() => setUser("alice")}>Alice</button>
            <button className={user === "bob" ? "active" : ""} onClick={() => setUser("bob")}>Bob</button>
          </div>
        </header>
        <nav className="tabs">
          <button className={tab === "docs" ? "active" : ""} onClick={() => setTab("docs")}><Files size={18} /> Documents</button>
          <button className={tab === "files" ? "active" : ""} onClick={() => setTab("files")}><Upload size={18} /> Files</button>
        </nav>
        {tab === "docs" ? (
          <section className="grid">
            <button className="docTile new" onClick={newDoc}><FilePlus2 /> New document</button>
            {docs.map((doc) => (
              <button className="docTile" key={doc.id} onClick={() => openDoc(doc.id)}>
                <TextQuote />
                <strong>{doc.title}</strong>
                <span>{new Date(doc.updated_at).toLocaleString()}</span>
              </button>
            ))}
          </section>
        ) : (
          <section className="grid">
            <label className="docTile new">
              <Upload />
              Upload .pdf, .md, .txt
              <input hidden type="file" accept=".pdf,.md,.txt" onChange={upload} />
            </label>
            {files.map((file) => (
              <div className="docTile" key={file.sha256}>
                <Files />
                <strong>{file.name}</strong>
                <span>{Math.ceil(file.size / 1024)} KB - {file.sha256.slice(0, 10)}</span>
              </div>
            ))}
          </section>
        )}
      </main>
    );
  }

  return (
    <main className="editorShell">
      <header className="docHeader">
        <button onClick={() => saveDoc(true)}><Check size={18} /> Done</button>
        <input value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Document title" />
        <button onClick={() => saveDoc()}><Save size={18} /> Save</button>
        <button onClick={colorizeHeaders}><Highlighter size={18} /> Headers</button>
      </header>
      <section className="workspace">
        <article className="paperWrap">
          <div
            ref={editorRef}
            className="paper"
            contentEditable
            suppressContentEditableWarning
            onMouseUp={captureSelection}
            onKeyUp={() => {
              setContent(markdownFromHtml(editorRef.current?.innerHTML ?? ""));
              captureSelection();
              colorizeHeaders();
            }}
            dangerouslySetInnerHTML={{ __html: htmlFromMarkdown(content) }}
          />
        </article>
        <aside className="assistant">
          <div className="assistantTop">
            <Bot />
            <strong>AI Assistant</strong>
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {models.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </div>
          <div className="meter"><span style={{ width: `${tokenPercent}%` }} /></div>
          <p className="meterText">{tokenPercent}% context used - document plus retrieved snippets</p>
          <div className="selection">{selectedText || "Select editor text for contextual actions."}</div>
          <div className="actions">
            <button disabled={busy || !selectedText} onClick={() => runAi("summarize")}><Sparkles size={17} /> Summarize</button>
            <button disabled={busy || !selectedText} onClick={() => runAi("improve")}><Wand2 size={17} /> Improve</button>
          </div>
          <div className="chatLog">
            {messages.map((m, i) => (
              <div className={`bubble ${m.role}`} key={i}>
                <p>{m.text}</p>
                {m.meta && <small>{m.meta.request_id} - {m.meta.metadata.retrieval_ms}ms retrieval - {m.meta.metadata.tokens_per_second.toFixed(1)} tok/s</small>}
                {m.meta?.citations.map((c) => <a key={c.chunk_id} href={`#${c.chunk_id}`}>{c.file}: {c.quote.slice(0, 72)}</a>)}
              </div>
            ))}
          </div>
          <div className="promptRow">
            <input value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Talk to your files..." />
            <button disabled={busy || !prompt} onClick={() => runAi("chat")}>{busy ? <Loader2 className="spin" /> : <Bot size={18} />}</button>
          </div>
        </aside>
      </section>
    </main>
  );
}
