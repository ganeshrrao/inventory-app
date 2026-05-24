import { useState } from "react";
import { API } from "../api.js";
import Icon from "../icons.jsx";

export default function BarcodeScannerModal({ onScanned, onClose, searching = false }) {
  const [status,     setStatus]     = useState("idle"); // idle | scanning | error
  const [dragging,   setDragging]   = useState(false);
  const [manualCode, setManualCode] = useState("");

  const decode = async (file) => {
    setStatus("scanning");
    setManualCode("");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API}/barcode/decode-image`, {
        method: "POST",
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error();
      const { barcode } = await res.json();
      onScanned(barcode);
    } catch {
      setStatus("error");
    }
  };

  const submitManual = () => {
    const code = manualCode.replace(/\s/g, "");
    if (code) onScanned(code);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title"><Icon.Barcode /> Scan Barcode</div>

        <div
          className={`dropzone ${dragging ? "active" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f && !searching) decode(f); }}
          onClick={() => { if (!searching) document.getElementById("barcode-file-input").click(); }}
        >
          <input
            id="barcode-file-input"
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => { if (e.target.files[0]) decode(e.target.files[0]); }}
          />
          {searching ? (
            <>
              <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3, margin: "0 auto 10px" }} />
              <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>Looking up product...</div>
            </>
          ) : status === "scanning" ? (
            <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3, margin: "0 auto" }} />
          ) : (
            <>
              <div style={{ fontSize: "2rem", marginBottom: 8 }}>📷</div>
              <strong>Drop a barcode photo here</strong>
              <div style={{ fontSize: "0.8rem", marginTop: 4, color: "var(--muted)" }}>
                or click to browse — JPG, PNG, WEBP
              </div>
              <div style={{ fontSize: "0.75rem", marginTop: 6, color: "var(--muted)" }}>
                Tip: tap to focus on the barcode before shooting
              </div>
            </>
          )}
        </div>

        {status === "error" && (
          <div style={{ marginTop: 12 }}>
            <p style={{ color: "var(--danger)", fontSize: "0.83rem", marginBottom: 10 }}>
              Could not read the barcode — image may be too blurry.
            </p>
            <p style={{ fontSize: "0.83rem", color: "var(--muted)", marginBottom: 6 }}>
              Enter the barcode number manually:
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="text"
                inputMode="numeric"
                placeholder="e.g. 682891390608"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submitManual()}
                style={{
                  flex: 1, padding: "7px 10px", borderRadius: 8,
                  border: "1.5px solid var(--border)", fontSize: "0.9rem",
                  outline: "none",
                }}
                autoFocus
              />
              <button
                className="btn btn-primary"
                onClick={submitManual}
                disabled={!manualCode.replace(/\s/g, "")}
              >
                Lookup
              </button>
            </div>
          </div>
        )}

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
