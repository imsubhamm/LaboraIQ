"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Banknote, Check, CheckCircle2, CreditCard, Printer, ScanLine,
  Smartphone, WalletCards
} from "lucide-react";
import { api } from "@/lib/api";

type PaymentMethod = "UPI" | "CARD" | "CASH";
type PaymentSummary = {
  order_id: string; order_number: string; patient_number: string; patient_name: string;
  invoice_number: string; total: string; payment_status: string;
};
type PaymentResult = PaymentSummary & {
  payment_method: PaymentMethod; transaction_id: string | null; paid_at: string;
  specimens: Array<{ barcode: string; specimen_type: string; container_type: string; status: string }>;
};

const methods = [
  { id: "UPI" as const, label: "UPI", note: "Google Pay, PhonePe, BHIM or other UPI", Icon: Smartphone },
  { id: "CARD" as const, label: "Card", note: "Debit or credit card payment", Icon: CreditCard },
  { id: "CASH" as const, label: "Cash", note: "Cash received at the laboratory desk", Icon: Banknote }
];

export default function PaymentPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [method, setMethod] = useState<PaymentMethod>("UPI");
  const [transactionId, setTransactionId] = useState("");
  const [result, setResult] = useState<PaymentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void api<PaymentSummary>(`/orders/${orderId}/payment`)
      .then(setSummary)
      .catch(err => setError(err instanceof Error ? err.message : "Unable to load invoice"))
      .finally(() => setLoading(false));
  }, [orderId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const response = await api<PaymentResult>(`/orders/${orderId}/payment`, {
        method: "POST",
        body: JSON.stringify({
          payment_method: method,
          transaction_id: method === "CASH" ? null : transactionId
        })
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to record payment");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="panel loading" aria-label="Loading payment"><i/><i/><i/></div>;
  if (!summary) return <div className="error-state" role="alert">{error || "Invoice was not found"}</div>;

  return (
    <section className="payment-page">
      <div className="page-heading payment-heading">
        <div><p className="eyebrow">ORDER {summary.order_number}</p><h1>Payment & collection</h1><p>Confirm payment before generating specimen barcodes.</p></div>
        <div className="intake-progress"><span className="current"><b><Check size={13}/></b>Details</span><span className="current"><b>2</b>Payment</span><span><b>3</b>Barcode</span></div>
      </div>

      {!result ? <form className="payment-layout" onSubmit={submit}>
        <article className="panel payment-form">
          <div className="form-section-head"><span><WalletCards size={19}/></span><div><p className="eyebrow">PAYMENT METHOD</p><h2>How did the patient pay?</h2><small>Select the recorded payment method.</small></div></div>
          <div className="payment-methods">
            {methods.map(({id,label,note,Icon}) => <label key={id} className={method === id ? "selected" : ""}><input type="radio" name="method" value={id} checked={method === id} onChange={() => { setMethod(id); setTransactionId(""); }}/><span className="payment-icon"><Icon size={22}/></span><strong>{label}</strong><small>{note}</small><i>{method === id && <Check size={13}/>}</i></label>)}
          </div>
          {method !== "CASH" && <label className="transaction-field">Transaction ID *<input required autoFocus placeholder={method === "UPI" ? "Enter UPI transaction/reference ID" : "Enter card transaction/reference ID"} value={transactionId} onChange={e => setTransactionId(e.target.value)}/><small>Verify this ID against the payment receipt before continuing.</small></label>}
          {method === "CASH" && <div className="cash-confirm"><Banknote size={20}/><div><strong>Cash payment selected</strong><small>No transaction ID is required. Confirm that ₹{summary.total} has been received.</small></div></div>}
          {error && <div className="error-state" role="alert">{error}</div>}
          <button className="primary payment-submit" disabled={saving}>{saving ? "Recording payment…" : "Confirm payment & generate barcode"}<ScanLine size={17}/></button>
        </article>
        <aside className="panel invoice-card">
          <p className="eyebrow">INVOICE SUMMARY</p><h2>{summary.invoice_number}</h2>
          <dl><div><dt>Patient</dt><dd>{summary.patient_name}</dd></div><div><dt>Patient ID</dt><dd>{summary.patient_number}</dd></div><div><dt>Order</dt><dd>{summary.order_number}</dd></div><div className="invoice-total"><dt>Amount due</dt><dd>₹{summary.total}</dd></div></dl>
          <span className="status pending">Payment pending</span>
        </aside>
      </form> :
      <div className="payment-complete">
        <div className="panel payment-success"><CheckCircle2 size={34}/><div><p className="eyebrow">PAYMENT CONFIRMED</p><h2>Collection labels are ready</h2><p>{result.payment_method}{result.transaction_id ? ` · ${result.transaction_id}` : ""} · ₹{result.total}</p></div><button className="primary" onClick={() => window.print()}><Printer size={17}/>Print labels</button></div>
        <section className="print-label-sheet">
          <header className="print-only-heading"><strong>LaboraIQ</strong><span>{result.order_number} · {result.patient_number}</span></header>
          {result.specimens.map(specimen => <article className="specimen-label" key={specimen.barcode}>
            <div className="label-brand">LaboraIQ <small>SPECIMEN</small></div>
            <strong>{result.patient_name}</strong><span>{result.patient_number} · {result.order_number}</span>
            <div className="barcode-bars" aria-hidden="true"/>
            <b>{specimen.barcode}</b>
            <footer><span>{specimen.specimen_type}</span><span>{specimen.container_type}</span></footer>
          </article>)}
        </section>
      </div>}
    </section>
  );
}
