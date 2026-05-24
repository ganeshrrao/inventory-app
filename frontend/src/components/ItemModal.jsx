import { useState, useEffect } from "react";
import { apiFetch } from "../api.js";
import Icon from "../icons.jsx";

export default function ItemModal({ item, prefill, onClose, onSaved }) {
  const [form, setForm] = useState({
    name:                item?.name                || prefill?.name                || "",
    sku:                 item?.sku                 || prefill?.sku                 || "",
    description:         item?.description         || prefill?.description         || "",
    quantity:            item?.quantity             ?? prefill?.quantity            ?? 0,
    unit_price:          item?.unit_price           || prefill?.unit_price          || "",
    low_stock_threshold: item?.low_stock_threshold  ?? prefill?.low_stock_threshold ?? 5,
    image_url:           item?.image_url            || prefill?.image_url           || null,
    category_id:         item?.category?.id         || null,
  });
  const [skuLoading, setSkuLoading] = useState(false);
  const [categories, setCategories]   = useState([]);
  const [showNewCat, setShowNewCat]   = useState(false);
  const [newCatName, setNewCatName]   = useState("");
  const [catCreating, setCatCreating] = useState(false);

  useEffect(() => {
    apiFetch("/categories").then(setCategories).catch(() => {});
  }, []);

  const createCategory = async () => {
    if (!newCatName.trim()) return;
    setCatCreating(true);
    try {
      const cat = await apiFetch("/categories", { method: "POST", body: JSON.stringify({ name: newCatName.trim() }) });
      setCategories(cs => [...cs, cat].sort((a, b) => a.name.localeCompare(b.name)));
      setForm(f => ({ ...f, category_id: cat.id }));
      setNewCatName("");
      setShowNewCat(false);
    } catch (e) { alert(e.message || "Failed to create category"); }
    setCatCreating(false);
  };

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  const lookupSku = async () => {
    if (!form.sku) return;
    setSkuLoading(true);
    try {
      const data = await apiFetch(`/vendor/sku/${form.sku}`);
      setForm(f => ({
        ...f,
        name: data.name || f.name,
        description: data.description || f.description,
        unit_price: data.unit_price || f.unit_price,
      }));
    } catch (e) { alert(e.message || "SKU not found in vendor catalog"); }
    setSkuLoading(false);
  };

  const [saveError, setSaveError] = useState(null);

  const save = async () => {
    setSaveError(null);
    const method = item ? "PATCH" : "POST";
    const url    = item ? `/items/${item.id}` : "/items";
    try {
      await apiFetch(url, {
        method,
        body: JSON.stringify({
          ...form,
          quantity:   Number(form.quantity),
          unit_price: form.unit_price ? Number(form.unit_price) : null,
          image_url:  form.image_url || null,
        }),
      });
      onSaved();
    } catch (e) {
      setSaveError(e.message || "Failed to save item");
    }
  };

  const sourceLabel = {
    openfoodfacts:   "Open Food Facts",
    openbeautyfacts: "Open Beauty Facts",
    openpetfoodfacts:"Open Pet Food Facts",
    upc_item_db:     "UPC Item DB",
    ai:              "AI (verify before saving)",
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-title">{item ? "Edit Item" : "Add Inventory Item"}</div>

        {prefill?._barcodeFound && (
          <div style={{
            background: "var(--success)", color: "#fff", borderRadius: 8,
            padding: "7px 12px", fontSize: "0.82rem", marginBottom: 12,
          }}>
            Product found via {sourceLabel[prefill._barcodeSource] || prefill._barcodeSource} — review and save
          </div>
        )}
        {prefill && !prefill._barcodeFound && prefill.sku && !item && (
          <div style={{
            background: "var(--warn)", color: "#fff", borderRadius: 8,
            padding: "7px 12px", fontSize: "0.82rem", marginBottom: 12,
          }}>
            Barcode {prefill.sku} not found in any database — fill in details below
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Name *</label>
          <input className="form-control" value={form.name} onChange={set("name")} placeholder="Item name" />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">SKU / Item #</label>
            <div style={{ display: "flex", gap: 6 }}>
              <input className="form-control" value={form.sku} onChange={set("sku")} placeholder="HD item #" />
              <button className="btn btn-ghost" style={{ whiteSpace: "nowrap" }} onClick={lookupSku} disabled={skuLoading}>
                {skuLoading ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <><Icon.Barcode /> Lookup</>}
              </button>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Quantity</label>
            <input className="form-control" type="number" value={form.quantity} onChange={set("quantity")} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Unit Price ($)</label>
            <input className="form-control" type="number" step="0.01" value={form.unit_price} onChange={set("unit_price")} />
          </div>
          <div className="form-group">
            <label className="form-label">Low Stock Threshold</label>
            <input className="form-control" type="number" value={form.low_stock_threshold} onChange={set("low_stock_threshold")} />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Category</label>
          <select
            className="form-control"
            value={form.category_id || ""}
            onChange={e => {
              if (e.target.value === "__new__") {
                setShowNewCat(true);
              } else {
                setForm(f => ({ ...f, category_id: e.target.value || null }));
                setShowNewCat(false);
              }
            }}
          >
            <option value="">No category</option>
            {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            <option value="__new__">＋ New category…</option>
          </select>
          {showNewCat && (
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <input
                className="form-control"
                placeholder="Category name"
                value={newCatName}
                onChange={e => setNewCatName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && createCategory()}
                autoFocus
              />
              <button className="btn btn-primary" style={{ whiteSpace: "nowrap" }} onClick={createCategory} disabled={catCreating}>
                {catCreating ? <span className="spinner" style={{ width: 14, height: 14 }} /> : "Add"}
              </button>
              <button className="btn btn-ghost" onClick={() => { setShowNewCat(false); setNewCatName(""); setForm(f => ({ ...f, category_id: null })); }}>✕</button>
            </div>
          )}
        </div>

        <div className="form-group">
          <label className="form-label">Description</label>
          <textarea className="form-control" rows={2} value={form.description} onChange={set("description")} />
        </div>

        {saveError && (
          <div style={{ background: "#fee2e2", color: "var(--danger)", padding: "8px 12px", borderRadius: 8, fontSize: "0.85rem", marginBottom: 12 }}>
            {saveError}
          </div>
        )}
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save}>Save Item</button>
        </div>
      </div>
    </div>
  );
}
