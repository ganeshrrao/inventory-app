import { useState, useEffect } from "react";
import { apiFetch } from "../api.js";
import Icon from "../icons.jsx";

const EMPTY_FORM = { name: "", description: "" };

export default function CategoriesPage() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading]       = useState(false);
  const [showModal, setShowModal]   = useState(false);
  const [editCat, setEditCat]       = useState(null);
  const [form, setForm]             = useState(EMPTY_FORM);
  const [error, setError]           = useState(null);
  const [seeding, setSeeding]       = useState(false);

  const load = async () => {
    setLoading(true);
    try { setCategories(await apiFetch("/categories")); } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const openAdd = () => {
    setEditCat(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowModal(true);
  };

  const openEdit = (cat) => {
    setEditCat(cat);
    setForm({ name: cat.name, description: cat.description || "" });
    setError(null);
    setShowModal(true);
  };

  const save = async () => {
    if (!form.name.trim()) { setError("Name is required"); return; }
    setError(null);
    try {
      if (editCat) {
        await apiFetch(`/categories/${editCat.id}`, { method: "PATCH", body: JSON.stringify(form) });
      } else {
        await apiFetch("/categories", { method: "POST", body: JSON.stringify(form) });
      }
      setShowModal(false);
      load();
    } catch (e) { setError(e.message || "Failed to save"); }
  };

  const deleteCat = async (cat) => {
    const msg = cat.item_count > 0
      ? `Delete "${cat.name}"? The ${cat.item_count} item(s) in this category will become uncategorized.`
      : `Delete "${cat.name}"?`;
    if (!confirm(msg)) return;
    try {
      await apiFetch(`/categories/${cat.id}`, { method: "DELETE" });
      load();
    } catch (e) { alert(e.message); }
  };

  const seedDefaults = async () => {
    setSeeding(true);
    try {
      const res = await apiFetch("/categories/seed", { method: "POST" });
      await load();
      if (res?.created === 0) alert("All default categories already exist.");
    } catch (e) { alert(e.message); }
    setSeeding(false);
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Categories</h1>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-ghost" onClick={seedDefaults} disabled={seeding}>
            {seeding ? <span className="spinner" style={{ width: 14, height: 14 }} /> : "Load Defaults"}
          </button>
          <button className="btn btn-primary" onClick={openAdd}>
            <Icon.Plus /> Add Category
          </button>
        </div>
      </div>

      {loading ? (
        <div className="empty-state"><div className="spinner" /></div>
      ) : categories.length === 0 ? (
        <div className="empty-state">
          <Icon.Tag />
          <p style={{ marginBottom: 16 }}>No categories yet</p>
          <button className="btn btn-primary" onClick={seedDefaults} disabled={seeding}>
            {seeding ? "Loading…" : "Load Default Categories"}
          </button>
        </div>
      ) : (
        <div className="cat-grid">
          {categories.map(cat => (
            <div key={cat.id} className="cat-card">
              <div className="cat-card-header">
                <span className="cat-name">{cat.name}</span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: "0.78rem" }} onClick={() => openEdit(cat)}>Edit</button>
                  <button className="btn btn-danger" style={{ padding: "4px 10px", fontSize: "0.78rem" }} onClick={() => deleteCat(cat)}>Del</button>
                </div>
              </div>
              {cat.description && <p className="cat-desc">{cat.description}</p>}
              <div style={{ marginTop: 8 }}>
                <span className="badge badge-muted">{cat.item_count} item{cat.item_count !== 1 ? "s" : ""}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-title">{editCat ? "Edit Category" : "New Category"}</div>
            <div className="form-group">
              <label className="form-label">Name *</label>
              <input
                className="form-control"
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Power Tools"
                autoFocus
                onKeyDown={e => e.key === "Enter" && save()}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <input
                className="form-control"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="Optional description"
              />
            </div>
            {error && (
              <div style={{ background: "#fee2e2", color: "var(--danger)", padding: "8px 12px", borderRadius: 8, fontSize: "0.85rem", marginBottom: 12 }}>
                {error}
              </div>
            )}
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={save}>Save</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
