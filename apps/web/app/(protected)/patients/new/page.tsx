"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import {
  Check, ChevronRight, FileText, FlaskConical, Mail, Phone, Search, Stethoscope,
  UploadCloud, UserRound, X
} from "lucide-react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

type CatalogTest = {
  id: string; code: string; name: string; specimen_type: string;
  container_type: string; price: string;
};

type IntakeResult = {
  patient_id: string; order_id: string; patient_number: string; order_number: string; invoice_number: string;
  subtotal: string; discount: string; total: string; payment_status: string;
  specimens: Array<{ barcode: string; specimen_type: string; container_type: string; status: string }>;
};

type PatientLookup = {
  id: string; patient_number: string; full_name: string; phone: string; email: string;
  age_years: number | null; sex: string | null; address: string | null; blood_group: string | null;
  country: string | null; race: string | null; nationality: string | null;
  additional_patient_data: Record<string, string> | null;
  visit_count: number; last_visit_at: string | null;
};

const bloodGroups = ["A+", "A−", "B+", "B−", "AB+", "AB−", "O+", "O−", "Unknown"];
const additionalPatientFields = [
  "Account Number", "Address Lines", "Address Location", "Admission Date",
  "Admitting Physician", "Age Units", "Alternate Patient ID", "Body Weight",
  "Body Weight - Units", "CPT Code", "Date of Birth", "Discharge Date",
  "Expected Date of Birth", "Financial Class",
  "Hospital Service Code", "ICD Code", "Location - Bed", "Location - Facility",
  "Location - Room", "Location Nurse Station", "Menstruation Cycle",
  "Mother's Maiden Name", "MRN", "Owner Name", "Patient Comment(s)",
  "Patient Height", "Patient Height Units", "Patient Icons", "Patient Status",
  "Phone - Business", "Phone - Home", "Previous Account Number", "Previous MRN",
  "Previous Patient ID", "Previous SSN", "Previous Visit Numbers", "SSN",
  "VIP Indicator", "Visit Number"
] as const;

type IntakeForm = {
  patientId: string;
  fullName: string;
  phone: string;
  email: string;
  ageYears: string;
  sex: string;
  bloodGroup: string;
  address: string;
  country: string;
  race: string;
  nationality: string;
  visitType: string;
  department: string;
  ward: string;
  doctorName: string;
  diagnosis: string;
  notes: string;
};

const initialForm: IntakeForm = {
  patientId: "",
  fullName: "",
  phone: "",
  email: "",
  ageYears: "",
  sex: "",
  bloodGroup: "",
  address: "",
  country: "",
  race: "",
  nationality: "",
  visitType: "",
  department: "",
  ward: "",
  doctorName: "",
  diagnosis: "",
  notes: ""
};

export default function NewPatientPage() {
  const router = useRouter();
  const [form, setForm] = useState(initialForm);
  const [tests, setTests] = useState<string[]>([]);
  const [catalog, setCatalog] = useState<CatalogTest[]>([]);
  const [testQuery, setTestQuery] = useState("");
  const [patientQuery, setPatientQuery] = useState("");
  const [patientMatch, setPatientMatch] = useState<PatientLookup | null>(null);
  const [searchingPatient, setSearchingPatient] = useState(false);
  const [showOptional, setShowOptional] = useState(false);
  const [additionalData, setAdditionalData] = useState<Record<string, string>>({});
  const [prescription, setPrescription] = useState<File | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<IntakeResult | null>(null);

  useEffect(() => {
    void api<CatalogTest[]>("/test-catalog")
      .then(setCatalog)
      .catch(err => setError(err instanceof Error ? err.message : "Unable to load test catalogue"));
  }, []);

  const matchingTests = useMemo(() => {
    const query = testQuery.trim().toLowerCase();
    if (!query) return catalog;
    return catalog.filter(test =>
      test.name.toLowerCase().includes(query) || test.code.toLowerCase().includes(query)
    );
  }, [catalog, testQuery]);
  const visibleTests = matchingTests.slice(0, testQuery.trim() ? 50 : 20);

  function update(field: keyof IntakeForm, value: string) {
    setForm(current => ({ ...current, [field]: value }));
    setSaved(false);
  }

  async function findPatient() {
    if (patientQuery.trim().length < 3) return;
    setSearchingPatient(true);
    setError("");
    try {
      const patient = await api<PatientLookup | null>(`/patients/lookup?query=${encodeURIComponent(patientQuery.trim())}`);
      if (!patient) {
        setPatientMatch(null);
        setForm(current => ({ ...current, patientId: "" }));
        setError("No existing patient found. Complete the form to register a new patient.");
        return;
      }
      setPatientMatch(patient);
      setAdditionalData(patient.additional_patient_data ?? {});
      setForm(current => ({
        ...current,
        patientId: patient.id,
        fullName: patient.full_name,
        phone: patient.phone,
        email: patient.email ?? "",
        ageYears: patient.age_years?.toString() ?? "",
        sex: patient.sex ?? "",
        bloodGroup: patient.blood_group ?? "",
        address: patient.address ?? "",
        country: patient.country ?? "",
        race: patient.race ?? "",
        nationality: patient.nationality ?? ""
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to search patients");
    } finally {
      setSearchingPatient(false);
    }
  }

  function toggleTest(test: string) {
    setTests(current =>
      current.includes(test) ? current.filter(item => item !== test) : [...current, test]
    );
  }

  function choosePrescription(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    if (file && file.size > 10 * 1024 * 1024) {
      event.target.value = "";
      setPrescription(null);
      return;
    }
    setPrescription(file);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setReviewing(true);
  }

  async function confirmEntry() {
    setSaving(true);
    setError("");
    try {
      const response = await api<IntakeResult>("/intake-workflows", {
        method: "POST",
        body: JSON.stringify({
          patient_id: form.patientId || null,
          full_name: form.fullName,
          phone: form.phone,
          email: form.email,
          age_years: form.ageYears ? Number(form.ageYears) : null,
          sex: form.sex || null,
          blood_group: form.bloodGroup,
          address: form.address || null,
          country: form.country,
          race: form.race || null,
          nationality: form.nationality,
          visit_type: form.visitType,
          department: form.department,
          ward: form.ward || null,
          doctor_name: form.doctorName,
          diagnosis: form.diagnosis || null,
          additional_patient_data: Object.fromEntries(
            Object.entries(additionalData).filter(([, value]) => value.trim())
          ),
          prescription_filename: prescription?.name ?? null,
          notes: form.notes || null,
          test_ids: tests,
          discount: 0
        })
      });
      setResult(response);
      setReviewing(false);
      setSaved(true);
      router.push(`/payments/${response.order_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register this order");
    } finally {
      setSaving(false);
    }
  }

  const complete = Boolean(
    form.fullName && form.ageYears && form.sex && form.phone && form.email &&
    form.bloodGroup && form.country && form.nationality &&
    form.visitType && form.department && form.doctorName && tests.length
  );
  const missingFields = [
    !form.fullName && "patient name",
    !form.ageYears && "age",
    !form.sex && "sex",
    !form.phone && "phone number",
    !form.email && "email address",
    !form.bloodGroup && "blood group",
    !form.country && "country",
    !form.nationality && "nationality",
    !form.visitType && "IP / OP",
    !form.department && "department",
    !tests.length && "requested test",
    !form.doctorName && "consultant name"
  ].filter(Boolean) as string[];

  return (
    <section className="intake-page">
      <div className="page-heading intake-heading">
        <div>
          <p className="eyebrow">NEW LABORATORY REQUEST</p>
          <h1>Patient intake</h1>
          <p>Enter patient, test, and prescription details before sample collection.</p>
        </div>
        <div className="intake-progress" aria-label="Intake progress">
          <span className="current"><b>1</b>Details</span><ChevronRight size={14}/>
          <span><b>2</b>Review</span><ChevronRight size={14}/>
          <span><b>3</b>Complete</span>
        </div>
      </div>

      {saved && result && (
        <div className="intake-success" role="status">
          <span><Check size={19}/></span>
          <div><strong>Order {result.order_number} registered</strong><p>Invoice {result.invoice_number} · ₹{result.total} · {result.specimens.length} barcode(s) generated</p></div>
          <button onClick={() => { setSaved(false); setResult(null); setForm(initialForm); setTests([]); setPrescription(null); setPatientMatch(null); setPatientQuery(""); setAdditionalData({}); setShowOptional(false); }}>Start another entry</button>
        </div>
      )}
      {error && <div className="error-state" role="alert">{error}</div>}

      <form className="intake-layout" onSubmit={submit}>
        <div className="intake-main">
          <article className="panel form-section">
            <div className="form-section-head">
              <span><UserRound size={19}/></span>
              <div><p className="eyebrow">SECTION 01 · REQUIRED</p><h2>Required information</h2><small>Complete every field marked with * before entering optional details.</small></div>
            </div>
            <div className="form-grid">
              <label className="wide">Find returning patient
                <div className="patient-search">
                  <div className="input-with-icon"><Search size={16}/><input placeholder="Patient UUID, patient number, phone, or email" value={patientQuery} onChange={e => setPatientQuery(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); void findPatient(); } }}/></div>
                  <button type="button" onClick={() => void findPatient()} disabled={searchingPatient || patientQuery.trim().length < 3}>{searchingPatient ? "Searching…" : "Search"}</button>
                </div>
                {patientMatch && <small className="patient-match"><Check size={12}/> Existing patient {patientMatch.patient_number} · UUID {patientMatch.id} · {patientMatch.visit_count} previous visit(s). Details loaded and editable.</small>}
              </label>
              <label className="wide">Patient ID (UUID)<input readOnly value={form.patientId || "Generated automatically when saved"} aria-label="Patient ID"/></label>
              <label>Patient name *<input required autoComplete="name" placeholder="Full patient name" value={form.fullName} onChange={e => update("fullName", e.target.value)}/></label>
              <label>Age *<input required type="number" min="0" max="130" inputMode="numeric" placeholder="Age in years" value={form.ageYears} onChange={e => update("ageYears", e.target.value)}/></label>
              <label>Sex *<select required value={form.sex} onChange={e => update("sex", e.target.value)}><option value="">Select sex</option><option>Female</option><option>Male</option><option>Intersex</option><option>Other</option><option>Unknown</option></select></label>
              <label>Patient type *<select required value={form.visitType} onChange={e => update("visitType", e.target.value)}><option value="">Select IP / OP</option><option value="OP">OP — Outpatient</option><option value="IP">IP — Inpatient</option></select></label>
              <label>Consulting department *<input required placeholder="Department" value={form.department} onChange={e => update("department", e.target.value)}/></label>
              <label>Consultant name *<div className="input-with-icon"><Stethoscope size={16}/><input required placeholder="Dr. full name" value={form.doctorName} onChange={e => update("doctorName", e.target.value)}/></div></label>
              <label>Phone number *<div className="input-with-icon"><Phone size={16}/><input required type="tel" autoComplete="tel" inputMode="tel" placeholder="+91 98765 43210" value={form.phone} onChange={e => update("phone", e.target.value)}/></div></label>
              <label>Email address *<div className="input-with-icon"><Mail size={16}/><input required type="email" autoComplete="email" placeholder="patient@example.com" value={form.email} onChange={e => update("email", e.target.value)}/></div></label>
              <label>Blood group *<select required value={form.bloodGroup} onChange={e => update("bloodGroup", e.target.value)}><option value="">Select blood group</option>{bloodGroups.map(group => <option key={group}>{group}</option>)}</select><small className="field-hint">Choose Unknown when it has not been confirmed.</small></label>
              <label>Country *<input required autoComplete="country-name" placeholder="Country" value={form.country} onChange={e => update("country", e.target.value)}/></label>
              <label>Nationality *<input required placeholder="Nationality" value={form.nationality} onChange={e => update("nationality", e.target.value)}/></label>
            </div>
          </article>

          <article className="panel form-section">
            <div className="form-section-head">
              <span><FlaskConical size={19}/></span>
              <div><p className="eyebrow">SECTION 02</p><h2>Requested tests</h2><small>Select one or more tests from the current catalogue.</small></div>
            </div>
            <div className="test-picker">
              <input aria-label="Find a test" placeholder="Search test name or code…" value={testQuery} onChange={e => setTestQuery(e.target.value)}/>
              {tests.length > 0 && <div className="selected-tests"><strong>{tests.length} selected</strong>{tests.map(testId => { const test = catalog.find(item => item.id === testId); return <button type="button" key={testId} onClick={() => toggleTest(testId)}>{test?.name ?? testId}<X size={12}/></button>; })}</div>}
              <div className="test-result-status"><span>{testQuery.trim() ? `${matchingTests.length} matching tests` : `Showing 20 of ${catalog.length} tests`}</span>{!testQuery.trim() && <small>Search to find the complete catalogue.</small>}</div>
              <div className="test-options">
                {visibleTests.map(test => <button type="button" key={test.id} className={`test-option ${tests.includes(test.id) ? "selected" : ""}`} aria-pressed={tests.includes(test.id)} onClick={() => toggleTest(test.id)}><span className="check-box"><Check size={13}/></span><span className="test-copy">{test.name}<small>{test.code} · {test.specimen_type} · ₹{test.price}</small></span></button>)}
              </div>
              {visibleTests.length === 0 && <div className="test-empty">No tests match “{testQuery}”.</div>}
              {matchingTests.length > visibleTests.length && <div className="test-more-hint">Showing the first {visibleTests.length} results. Refine the search to narrow the list.</div>}
            </div>
          </article>

          <article className="panel form-section">
            <div className="form-section-head">
              <span><Stethoscope size={19}/></span>
              <div><p className="eyebrow">SECTION 03 · OPTIONAL</p><h2>Additional details & prescription</h2><small>Add supporting information only when it is available.</small></div>
            </div>
            <div className="form-grid">
              <label>Race<input placeholder="Optional" value={form.race} onChange={e => update("race", e.target.value)}/></label>
              <label>Location - Ward<input placeholder="Optional" value={form.ward} onChange={e => update("ward", e.target.value)}/></label>
              <label className="wide">Diagnosis - Code / Text<input placeholder="Optional diagnosis" value={form.diagnosis} onChange={e => update("diagnosis", e.target.value)}/></label>
              <label className="wide">Address<textarea rows={2} autoComplete="street-address" placeholder="Optional address" value={form.address} onChange={e => update("address", e.target.value)}/></label>
              <div className="wide optional-intro"><div><strong>Extended prescription data</strong><small>Load additional administrative fields only when needed.</small></div><button type="button" onClick={() => setShowOptional(value => !value)}>{showOptional ? "Show less" : "Load more"}<ChevronRight size={14}/></button></div>
              {showOptional && <div className="wide optional-fields">
                {additionalPatientFields.map(field => <label key={field}>{field}<input value={additionalData[field] ?? ""} placeholder="From prescription" onChange={e => setAdditionalData(current => ({ ...current, [field]: e.target.value }))}/></label>)}
              </div>}
              <label className="wide">Prescription document
                <div className={`upload-zone ${prescription ? "has-file" : ""}`}>
                  <input aria-label="Upload prescription" type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={choosePrescription}/>
                  {prescription ? <><FileText size={25}/><strong>{prescription.name}</strong><small>{(prescription.size / 1024).toFixed(0)} KB · Ready to upload</small></> :
                  <><UploadCloud size={25}/><strong>Drop prescription here or browse</strong><small>PDF, JPG or PNG · Maximum 10 MB</small></>}
                </div>
              </label>
              <label className="wide">Notes <textarea rows={4} placeholder="Optional collection instructions or relevant notes" value={form.notes} onChange={e => update("notes", e.target.value)}/></label>
            </div>
          </article>
        </div>

        <aside className="intake-summary">
          <div className="panel summary-card">
            <p className="eyebrow">ENTRY SUMMARY</p>
            <h2>Review readiness</h2>
            <div className={form.fullName && form.ageYears && form.sex && form.phone && form.email && form.bloodGroup && form.country && form.nationality ? "done" : ""}><span>{form.fullName && form.ageYears && form.sex && form.phone && form.email && form.bloodGroup && form.country && form.nationality ? <Check size={14}/> : "1"}</span><p><strong>Patient details</strong><small>{patientMatch ? `${patientMatch.patient_number} · returning` : form.fullName || "New patient"}</small></p></div>
            <div className={tests.length ? "done" : ""}><span>{tests.length ? <Check size={14}/> : "2"}</span><p><strong>Requested tests</strong><small>{tests.length ? `${tests.length} selected` : "None selected"}</small></p></div>
            <div className={form.visitType && form.department && form.doctorName ? "done" : ""}><span>{form.visitType && form.department && form.doctorName ? <Check size={14}/> : "3"}</span><p><strong>Visit details</strong><small>{form.visitType ? `${form.visitType} · ${form.department || "department pending"}` : "Not entered"}</small></p></div>
            <button className="primary review-button" type="submit">Review patient entry<ChevronRight size={16}/></button>
            {!complete && <small className="missing-fields">Still required: {missingFields.join(", ")}.</small>}
            <small className="privacy-note">Only authorized laboratory staff should handle identifiable patient information.</small>
          </div>
        </aside>
      </form>

      {reviewing && <div className="modal-backdrop"><section className="modal review-modal" role="dialog" aria-modal="true" aria-labelledby="review-title">
        <div className="modal-head"><div><p className="eyebrow">CONFIRM INFORMATION</p><h2 id="review-title">Review patient entry</h2></div><button aria-label="Close review" onClick={() => setReviewing(false)}><X/></button></div>
        <div className="review-content">
          <dl><div><dt>Patient</dt><dd>{form.fullName || "Name not provided"}<br/>{form.patientId || "New UUID will be generated"}</dd></div><div><dt>Contact</dt><dd>{form.phone}<br/>{form.email}</dd></div><div><dt>Demography</dt><dd>{[form.ageYears && `Age ${form.ageYears}`, form.sex, form.country, form.nationality, form.race].filter(Boolean).join(" · ")}</dd></div><div><dt>Visit</dt><dd>{form.visitType} · {form.department}<br/>{[form.ward, form.doctorName].filter(Boolean).join(" · ")}</dd></div>{form.diagnosis && <div className="wide"><dt>Diagnosis</dt><dd>{form.diagnosis}</dd></div>}<div className="wide"><dt>Requested tests</dt><dd>{tests.map(id => catalog.find(item => item.id === id)?.name).filter(Boolean).join(", ")}</dd></div><div className="wide"><dt>Prescription</dt><dd>{prescription?.name ?? "No file attached"}</dd></div></dl>
          <p className="review-warning">Confirm the details against the original prescription before continuing.</p>
        </div>
        <div className="form-actions review-actions"><button type="button" onClick={() => setReviewing(false)}>Go back and edit</button><button className="primary" disabled={saving} type="button" onClick={confirmEntry}><Check size={16}/>{saving ? "Registering…" : "Confirm & continue to payment"}</button></div>
      </section></div>}
      {result && <section className="panel barcode-result"><div><p className="eyebrow">COLLECTION LABELS</p><h2>Generated specimen barcodes</h2></div>{result.specimens.map(item => <article key={item.barcode}><strong>{item.barcode}</strong><span>{item.specimen_type}</span><small>{item.container_type}</small></article>)}</section>}
    </section>
  );
}
