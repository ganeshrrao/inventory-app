import { useState } from "react";
import { API, apiFetch } from "../api.js";

export default function ReceiptModal({ onClose, onDone }) {
  const [stage, setStage]       = useState("upload"); // upload | processing | confirm
  const [receipt, setReceipt]   = useState(null);
  const [selected, setSelected] = useState(new Set());
  const [dragging, setDragging] = useState(false);

  const upload = async (file) => {
    setStage("processing");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/receipts/upload`, {
        method: "POST",
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || `Upload failed (${res.status})`);
        setStage("upload");
        return;
      }
      setReceipt(data);
      setSelected(new Set(data.line_items?.map(li => li.id) || []));
      setStage("confirm");
    } catch { alert("Upload failed"); setStage("upload"); }
  };

  const confirm = async () => {
    await apiFetch(`/receipts/${receipt.id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ line_item_ids: Array.from(selected) }),
    });
    onDone();
  };

  const toggle = (id) => setSelected(s => {
    const n = new Set(s);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-title">📷 Scan Receipt</div>

        {stage === "upload" && (
          <div
            className={`dropzone ${dragging ? "active" : ""}`}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) upload(f); }}
            onClick={() => document.getElementById("receipt-file-input").click()}
          >
            <input id="receipt-file-input" type="file" accept="image/*" style={{ display: "none" }} onChange={e => { if (e.target.files[0]) upload(e.target.files[0]); }} />
            <div style={{ fontSize: "2rem", marginBottom: 8 }}>📄</div>
            <strong>Drop receipt image here</strong>
            <div style={{ fontSize: "0.8rem", marginTop: 4 }}>or click to browse — JPG, PNG, WEBP</div>
          </div>
        )}

        {stage === "processing" && (
          <div className="empty-state">
            <div className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
            <p style={{ marginTop: 16, fontWeight: 600 }}>Processing receipt with AI…</p>
          </div>
        )}

        {stage === "confirm" && receipt && (
          <>
            <p style={{ marginBottom: 12, fontSize: "0.85rem", color: "#6b7280" }}>
              Found <strong>{receipt.line_items?.length}</strong> items. Select which to add to inventory:
            </p>
            <div className="receipt-items">
              {receipt.line_items?.map(li => (
                <div key={li.id} className="receipt-item">
                  <input type="checkbox" checked={selected.has(li.id)} onChange={() => toggle(li.id)} />
                  <div className="item-name">{li.name || li.raw_text}</div>
                  <div className="item-meta">
                    {li.parsed_sku && <span className="sku-tag" style={{ marginRight: 6 }}>{li.parsed_sku}</span>}
                    {li.quantity}× {li.unit_price ? `$${li.unit_price.toFixed(2)}` : ""}
                  </div>
                </div>
              ))}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn btn-primary" onClick={confirm} disabled={selected.size === 0}>
                Add {selected.size} Item{selected.size !== 1 ? "s" : ""} →
              </button>
            </div>
          </>
        )}

        {stage !== "confirm" && (
          <div className="modal-footer">
            <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          </div>
        )}
      </div>
    </div>
  );
}
