"use client";

import { useEffect, useState, type FormEvent } from "react";

import { usePatients, useUpload } from "../../../lib/api/hooks";

const STEPS = ["Uploading", "Reading documents", "Removing personal identifiers", "Building insights"];

export default function UploadPage() {
  const patients = usePatients();
  const upload = useUpload();
  const [patientId, setPatientId] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    if (!patientId && patients.data?.length) setPatientId(patients.data[0].id);
  }, [patients.data, patientId]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (file && patientId) upload.mutate({ id: patientId, file });
  };
  const queued = upload.isSuccess;

  return (
    <>
      <h1>Upload patient file</h1>
      <form className="drop" onSubmit={onSubmit}>
        <b style={{ fontSize: 18, color: "#1F4E79" }}>Drop PDFs, lab reports and notes here</b>
        <p className="muted">PDF, JPG or PNG · up to 25 MB each</p>
        <div className="row" style={{ justifyContent: "center" }}>
          <label>
            Patient{" "}
            <select value={patientId} onChange={(e) => setPatientId(e.target.value)}>
              {patients.data?.map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
            </select>
          </label>
          <input type="file" accept=".pdf,.jpg,.jpeg,.png" aria-label="File" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button className="btn" type="submit" disabled={!file || upload.isPending}>Upload</button>
        </div>
        {upload.isError && <p role="alert">The upload failed. Please try again.</p>}
      </form>
      <div className="steps" aria-label="Processing steps">
        {STEPS.map((s, i) => (
          <div key={s} className={`step ${queued && i === 0 ? "dn" : ""}`}>
            <b>{i + 1}.</b> {s}
            <div className="muted">{queued && i === 0 ? "Done (queued)" : "Waiting"}</div>
          </div>
        ))}
      </div>
      <p className="muted">Processing is not connected yet in this version. Files are stored and marked as queued.</p>
      <div className="card row">
        <span className="sev info">Privacy</span>
        <span>Personal identifiers are removed before AI analysis. Files are encrypted and every access is logged.</span>
      </div>
    </>
  );
}
