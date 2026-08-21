"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, ListChecks, Search, X } from "lucide-react";
import { api, Page } from "@/lib/api";
import { can } from "@/lib/auth";

type WorklistItem = {
  id: string;
  specimen_barcode: string;
  accession_number: string | null;
  order_number: string;
  lis_test_code: string;
  test_name: string;
  analyzer_code: string;
  analyzer_name: string;
  machine_test_code: string;
  status: string;
  latest_attempt_no: number | null;
  latest_attempt_state: string | null;
  created_at: string;
};

type AnalyzerMessage = {
  id: string;
  direction: string;
  content_type: string;
  body: string;
  correlation_id: string;
  created_at: string;
};

type ProcessResult = {
  processed: number;
  attempts: Array<{ id: string; attempt_no: number; state: string; error: string | null }>;
};

function formatHl7(body: string) {
  return body.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function messageLabel(body: string, direction: string) {
  const head = body.slice(0, 80);
  if (head.includes("OML^O33") || head.includes("OML^O21")) return "Order (OML)";
  if (head.includes("ORU^R01")) return "Result (ORU)";
  if (head.includes("ACK")) return "Acknowledgement (ACK)";
  if (body.startsWith("LABORAIQ-ORDER-V0")) return "Stub order";
  return direction === "outbound" ? "Outbound message" : "Inbound message";
}

export default function AnalyzerWorklistPage() {
  const [items, setItems] = useState<WorklistItem[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [processSummary, setProcessSummary] = useState("");
  const [messageItem, setMessageItem] = useState<WorklistItem | null>(null);
  const [messages, setMessages] = useState<AnalyzerMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [messagesError, setMessagesError] = useState("");
  const [selectedMessageId, setSelectedMessageId] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const query = new URLSearchParams({ limit: "100", offset: "0" });
      if (status) query.set("status", status);
      const page = await api<Page<WorklistItem>>(`/analyzer-worklist?${query}`);
      setItems(page.items);
      setTotal(page.total);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load analyzer worklist");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function openMessages(item: WorklistItem) {
    setMessageItem(item);
    setMessages([]);
    setSelectedMessageId("");
    setMessagesError("");
    setMessagesLoading(true);
    try {
      const rows = await api<AnalyzerMessage[]>(`/analyzer-worklist/${item.id}/messages`);
      setMessages(rows);
      setSelectedMessageId(rows[0]?.id ?? "");
    } catch (reason) {
      setMessagesError(reason instanceof Error ? reason.message : "Unable to load messages");
    } finally {
      setMessagesLoading(false);
    }
  }

  async function enqueue(id: string) {
    try {
      setBusyId(id);
      setError("");
      await api(`/analyzer-worklist/${id}/enqueue`, { method: "POST", body: "{}" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to enqueue item");
    } finally {
      setBusyId("");
    }
  }

  async function normalize(id: string) {
    try {
      setBusyId(id);
      setError("");
      await api(`/analyzer-worklist/${id}/normalize-result`, { method: "POST", body: "{}" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to normalize result");
    } finally {
      setBusyId("");
    }
  }

  async function cancel(id: string) {
    try {
      setBusyId(id);
      setError("");
      await api(`/analyzer-worklist/${id}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason: "Cancelled from worklist UI" }),
      });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to cancel item");
    } finally {
      setBusyId("");
    }
  }

  async function processQueue() {
    try {
      setProcessing(true);
      setError("");
      const result = await api<ProcessResult>("/analyzer-orders/process?limit=20", {
        method: "POST",
        body: "{}",
      });
      setProcessSummary(
        result.processed === 0
          ? "No queued order attempts to process."
          : `Processed ${result.processed} attempt(s): ${result.attempts
              .map((item) => `#${item.attempt_no} ${item.state}`)
              .join(", ")}`
      );
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to process order queue");
    } finally {
      setProcessing(false);
    }
  }

  const selectedMessage = messages.find((row) => row.id === selectedMessageId) ?? null;

  return (
    <section>
      <div className="page-heading">
        <div>
          <p className="eyebrow">INSTRUMENT INTERFACE</p>
          <h1>Analyzer worklist</h1>
          <p>Accepted specimens routed to analyzers by active LIS ↔ machine mappings.</p>
        </div>
        {can("analyzer.manage") && (
          <button className="primary" disabled={processing} onClick={() => void processQueue()}>
            {processing ? "Processing…" : "Process order queue"}
          </button>
        )}
      </div>
      {processSummary && (
        <div className="import-summary panel">
          <ListChecks size={22} />
          <div>
            <strong>Order queue</strong>
            <p>{processSummary}</p>
          </div>
        </div>
      )}
      {error && (
        <div className="error-state">
          <AlertCircle size={18} />
          {error}
          <button onClick={() => void load()}>Retry</button>
        </div>
      )}
      <div className="panel">
        <div className="toolbar">
          <label className="search">
            <Search size={17} />
            <select
              aria-label="Filter worklist status"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="queued">Queued</option>
              <option value="in_flight">In flight</option>
              <option value="awaiting_result">Awaiting result</option>
              <option value="result_received">Result received</option>
              <option value="normalized">Normalized</option>
              <option value="released">Released</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
              <option value="completed">Completed</option>
            </select>
          </label>
          <span>{total} items</span>
        </div>
        {loading ? (
          <div className="loading">
            <i />
            <i />
            <i />
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <ListChecks />
            <h3>No worklist items</h3>
            <p>Accept a specimen whose ordered tests have active analyzer mappings.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Specimen</th>
                  <th>Order</th>
                  <th>LIS test</th>
                  <th>Analyzer</th>
                  <th>Machine code</th>
                  <th>Status</th>
                  <th>Attempt</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.specimen_barcode}</strong>
                      <span>{item.accession_number || "No accession"}</span>
                    </td>
                    <td>{item.order_number}</td>
                    <td>
                      <strong>{item.lis_test_code}</strong>
                      <span>{item.test_name}</span>
                    </td>
                    <td>
                      <strong>{item.analyzer_code}</strong>
                      <span>{item.analyzer_name}</span>
                    </td>
                    <td>
                      <code>{item.machine_test_code}</code>
                    </td>
                    <td>
                      <span className={`status ${item.status}`}>{item.status}</span>
                    </td>
                    <td>
                      {item.latest_attempt_no != null ? (
                        <>
                          <strong>#{item.latest_attempt_no}</strong>
                          <span>{item.latest_attempt_state}</span>
                        </>
                      ) : (
                        <span>None</span>
                      )}
                    </td>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                    <td>
                      <div className="analyzer-actions">
                        <button
                          className="mapping-button"
                          onClick={() => void openMessages(item)}
                        >
                          Messages
                        </button>
                        {can("result.review") && item.status === "result_received" && (
                          <button
                            className="mapping-button"
                            disabled={busyId === item.id}
                            onClick={() => void normalize(item.id)}
                          >
                            Normalize
                          </button>
                        )}
                        {can("analyzer.manage") &&
                          (item.status === "pending" || item.status === "failed") && (
                            <button
                              className="mapping-button"
                              disabled={busyId === item.id}
                              onClick={() => void enqueue(item.id)}
                            >
                              Enqueue
                            </button>
                          )}
                        {can("analyzer.manage") &&
                          item.status !== "cancelled" &&
                          item.status !== "completed" && (
                            <button
                              className="mapping-button"
                              disabled={busyId === item.id}
                              onClick={() => void cancel(item.id)}
                            >
                              Cancel
                            </button>
                          )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {messageItem && (
        <div className="modal-backdrop">
          <section className="modal message-modal">
            <div className="modal-head">
              <div>
                <p className="eyebrow">ANALYZER EXCHANGE</p>
                <h2>{messageItem.specimen_barcode}</h2>
                <small>
                  {messageItem.analyzer_code} · {messageItem.lis_test_code} →{" "}
                  {messageItem.machine_test_code}
                </small>
              </div>
              <button
                aria-label="Close message viewer"
                onClick={() => {
                  setMessageItem(null);
                  setMessages([]);
                  setSelectedMessageId("");
                  setMessagesError("");
                }}
              >
                <X />
              </button>
            </div>
            {messagesError && (
              <div className="connection-error">
                <AlertCircle size={16} />
                <span>
                  <strong>Unable to load messages</strong>
                  {messagesError}
                </span>
              </div>
            )}
            {messagesLoading ? (
              <div className="loading" style={{ padding: 28 }}>
                <i />
                <i />
                <i />
              </div>
            ) : messages.length === 0 ? (
              <div className="empty-state" style={{ padding: 40 }}>
                <ListChecks />
                <h3>No messages yet</h3>
                <p>Enqueue and process the order queue to send an OML to the analyzer.</p>
              </div>
            ) : (
              <div className="message-layout">
                <aside>
                  <h3>Traffic</h3>
                  {messages.map((row) => (
                    <button
                      key={row.id}
                      className={selectedMessageId === row.id ? "active" : ""}
                      onClick={() => setSelectedMessageId(row.id)}
                    >
                      <strong>{messageLabel(row.body, row.direction)}</strong>
                      <span>
                        {row.direction} · {new Date(row.created_at).toLocaleString()}
                      </span>
                    </button>
                  ))}
                </aside>
                <div className="message-detail">
                  {selectedMessage ? (
                    <>
                      <div className="message-meta">
                        <span className={`status ${selectedMessage.direction}`}>
                          {selectedMessage.direction}
                        </span>
                        <small>{selectedMessage.content_type}</small>
                        <small>{selectedMessage.correlation_id}</small>
                      </div>
                      <pre>{formatHl7(selectedMessage.body)}</pre>
                    </>
                  ) : (
                    <p>Select a message to inspect the HL7 payload.</p>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}
