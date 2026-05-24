import { useState, useEffect, useCallback } from "react";
import { API, apiFetch } from "../api.js";
import Icon from "../icons.jsx";
import ItemModal from "../components/ItemModal.jsx";
import ReceiptModal from "../components/ReceiptModal.jsx";
import BarcodeScannerModal from "../components/BarcodeScannerModal.jsx";
import ItemHistoryDrawer from "../components/ItemHistoryDrawer.jsx";

export default function InventoryPage({ lowStockOnly = false }) {
  const [items, setItems]           = useState([]);
  const [summary, setSummary]       = useState({});
  const [search, setSearch]         = useState("");
  const [loading, setLoading]       = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [categories, setCategories]         = useState([]);
  const [categoryFilter, setCategoryFilter] = useState("");

  const [showAddModal, setShowAddModal]         = useState(false);
  const [showReceiptModal, setShowReceiptModal] = useState(false);
  const [showBarcodeModal, setShowBarcodeModal] = useState(false);
  const [editItem, setEditItem]                 = useState(null);
  const [historyItem, setHistoryItem]           = useState(null);
  const [barcodePrefill, setBarcodePrefill]     = useState(null);
  const [barcodeSearching, setBarcodeSearching] = useState(false);

  // Bulk selection
  const [selectedIds, setSelectedIds]   = useState(new Set());
  const [showBulkQty, setShowBulkQty]   = useState(false);
  const [bulkDelta, setBulkDelta]       = useState(1);
  const [showBulkCat, setShowBulkCat]   = useState(false);
  const [bulkCatId, setBulkCatId]       = useState("");
  const [bulkLoading, setBulkLoading]   = useState(false);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (lowStockOnly) params.set("low_stock_only", "true");
      if (categoryFilter) params.set("category_id", categoryFilter);
      const data = await apiFetch(`/items?${params}`);
      setItems(data.items || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [search, lowStockOnly, categoryFilter]);

  const loadSummary = async () => {
    try { setSummary(await apiFetch("/dashboard/summary")); } catch {}
  };

  useEffect(() => { loadItems(); }, [loadItems]);
  useEffect(() => { loadSummary(); }, []);
  useEffect(() => { apiFetch("/categories").then(setCategories).catch(() => {}); }, []);
  useEffect(() => { setSelectedIds(new Set()); }, [search, categoryFilter, lowStockOnly]);

  // ── Selection helpers ────────────────────────────────────────────────────────

  const toggleSelect = (id) => setSelectedIds(prev => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  const toggleSelectAll = () => {
    setSelectedIds(selectedIds.size === items.length ? new Set() : new Set(items.map(i => i.id)));
  };

  const clearBulk = () => {
    setSelectedIds(new Set());
    setShowBulkQty(false);
    setShowBulkCat(false);
  };

  // ── Bulk actions ─────────────────────────────────────────────────────────────

  const bulkDelete = async () => {
    if (!confirm(`Permanently delete ${selectedIds.size} item(s)?`)) return;
    setBulkLoading(true);
    try {
      await apiFetch("/items/bulk-delete", { method: "POST", body: JSON.stringify({ ids: [...selectedIds] }) });
      clearBulk();
      loadItems();
      loadSummary();
    } catch (e) { alert(e.message); }
    setBulkLoading(false);
  };

  const bulkAdjustQty = async () => {
    const delta = Number(bulkDelta);
    if (!delta) { alert("Enter a non-zero delta"); return; }
    setBulkLoading(true);
    try {
      await apiFetch("/items/bulk-adjust", { method: "POST", body: JSON.stringify({ ids: [...selectedIds], delta }) });
      clearBulk();
      loadItems();
    } catch (e) { alert(e.message); }
    setBulkLoading(false);
  };

  const bulkAssignCategory = async () => {
    setBulkLoading(true);
    try {
      await apiFetch("/items/bulk-category", { method: "POST", body: JSON.stringify({ ids: [...selectedIds], category_id: bulkCatId || null }) });
      clearBulk();
      loadItems();
    } catch (e) { alert(e.message); }
    setBulkLoading(false);
  };

  // ── Single-item actions ──────────────────────────────────────────────────────

  const handleBarcodeScan = async (code) => {
    setBarcodeSearching(true);
    let prefill = { sku: code, name: "", description: "", quantity: 1, unit_price: "", low_stock_threshold: 5, _barcodeFound: false };
    try {
      const product = await apiFetch(`/barcode/${code}`);
      prefill = {
        sku: code,
        name: product.name || "",
        description: [product.brand, product.description].filter(Boolean).join(" — "),
        quantity: 1,
        unit_price: "",
        low_stock_threshold: 5,
        image_url: product.image_url || null,
        _barcodeFound: true,
        _barcodeSource: product.source,
      };
    } catch { /* not in any database — open modal with just the barcode */ }
    setBarcodeSearching(false);
    setShowBarcodeModal(false);
    setBarcodePrefill(prefill);
    setEditItem(null);
    setShowAddModal(true);
  };

  const exportItems = async (fmt) => {
    setShowExport(false);
    const token = localStorage.getItem("token");
    const params = new URLSearchParams({ format: fmt });
    if (search) params.set("search", search);
    if (lowStockOnly) params.set("low_stock_only", "true");
    const res  = await fetch(`${API}/items/export?${params}`, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = `inventory.${fmt}`; a.click();
    URL.revokeObjectURL(url);
  };

  const deleteItem = async (id) => {
    if (!confirm("Delete this item?")) return;
    await apiFetch(`/items/${id}`, { method: "DELETE" });
    loadItems();
    loadSummary();
  };

  const allSelected = items.length > 0 && selectedIds.size === items.length;
  const someSelected = selectedIds.size > 0 && !allSelected;

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">{lowStockOnly ? "⚠️ Low Stock" : "Inventory"}</h1>
        <div style={{ display: "flex", gap: 10 }}>
          <div style={{ position: "relative" }}>
            <button className="btn btn-ghost" onClick={() => setShowExport(v => !v)}>
              <Icon.Download /> Export
            </button>
            {showExport && (
              <div className="export-dropdown" onMouseLeave={() => setShowExport(false)}>
                <button onClick={() => exportItems("csv")}>Download CSV</button>
                <button onClick={() => exportItems("xlsx")}>Download Excel</button>
              </div>
            )}
          </div>
          <button className="btn btn-ghost" onClick={() => setShowBarcodeModal(true)}>
            <Icon.Barcode /> Scan Barcode
          </button>
          <button className="btn btn-ghost" onClick={() => setShowReceiptModal(true)}>
            <Icon.Receipt /> Scan Receipt
          </button>
          <button className="btn btn-primary" onClick={() => { setEditItem(null); setBarcodePrefill(null); setShowAddModal(true); }}>
            <Icon.Plus /> Add Item
          </button>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total Items</div>
          <div className="stat-value">{summary.total_items ?? "—"}</div>
        </div>
        <div className="stat-card success">
          <div className="stat-label">Total Value</div>
          <div className="stat-value">${(summary.total_value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
        <div className="stat-card warn">
          <div className="stat-label">Low Stock</div>
          <div className="stat-value">{summary.low_stock_count ?? "—"}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Categories</div>
          <div className="stat-value">{summary.category_count ?? "—"}</div>
        </div>
      </div>

      <div className="toolbar">
        <div className="search-wrap">
          <Icon.Search />
          <input
            className="search-input"
            placeholder="Search by name, SKU, description…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <select
          className="form-control"
          style={{ width: "auto", minWidth: 160 }}
          value={categoryFilter}
          onChange={e => setCategoryFilter(e.target.value)}
        >
          <option value="">All categories</option>
          {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {selectedIds.size > 0 && (
        <div className="bulk-bar">
          <span className="bulk-count">{selectedIds.size} selected</span>
          <button className="btn btn-ghost" style={{ padding: "5px 12px", fontSize: "0.8rem" }} onClick={clearBulk}>Clear</button>

          <button className="btn btn-danger" style={{ padding: "5px 12px", fontSize: "0.8rem" }} onClick={bulkDelete} disabled={bulkLoading}>
            Delete
          </button>

          <div style={{ position: "relative" }}>
            <button
              className="btn btn-ghost"
              style={{ padding: "5px 12px", fontSize: "0.8rem" }}
              onClick={() => { setShowBulkQty(v => !v); setShowBulkCat(false); }}
            >
              Adjust Qty
            </button>
            {showBulkQty && (
              <div className="bulk-popover">
                <label className="form-label" style={{ marginBottom: 6 }}>Delta (+ to add, − to remove)</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    className="form-control"
                    type="number"
                    value={bulkDelta}
                    onChange={e => setBulkDelta(e.target.value)}
                    style={{ width: 90 }}
                    autoFocus
                    onKeyDown={e => e.key === "Enter" && bulkAdjustQty()}
                  />
                  <button className="btn btn-primary" style={{ padding: "5px 12px" }} onClick={bulkAdjustQty} disabled={bulkLoading}>
                    {bulkLoading ? <span className="spinner" style={{ width: 12, height: 12 }} /> : "Apply"}
                  </button>
                </div>
              </div>
            )}
          </div>

          <div style={{ position: "relative" }}>
            <button
              className="btn btn-ghost"
              style={{ padding: "5px 12px", fontSize: "0.8rem" }}
              onClick={() => { setShowBulkCat(v => !v); setShowBulkQty(false); }}
            >
              Assign Category
            </button>
            {showBulkCat && (
              <div className="bulk-popover">
                <label className="form-label" style={{ marginBottom: 6 }}>Category</label>
                <div style={{ display: "flex", gap: 8 }}>
                  <select
                    className="form-control"
                    value={bulkCatId}
                    onChange={e => setBulkCatId(e.target.value)}
                    style={{ minWidth: 160 }}
                    autoFocus
                  >
                    <option value="">No category</option>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <button className="btn btn-primary" style={{ padding: "5px 12px" }} onClick={bulkAssignCategory} disabled={bulkLoading}>
                    {bulkLoading ? <span className="spinner" style={{ width: 12, height: 12 }} /> : "Apply"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="table-wrap">
        {loading ? (
          <div className="empty-state"><div className="spinner" /></div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <Icon.Box />
            <p>No items found</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={el => { if (el) el.indeterminate = someSelected; }}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th>Name</th>
                <th>SKU</th>
                <th>Category</th>
                <th>Qty</th>
                <th>Unit Price</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id} className={selectedIds.has(item.id) ? "row-selected" : ""}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(item.id)}
                      onChange={() => toggleSelect(item.id)}
                    />
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{item.name}</div>
                    {item.created_by_email && (
                      <div className="item-added-by">by {item.created_by_email}</div>
                    )}
                  </td>
                  <td>{item.sku ? <span className="sku-tag">{item.sku}</span> : <span style={{ color: "#ccc" }}>—</span>}</td>
                  <td>{item.category?.name ?? <span style={{ color: "#ccc" }}>—</span>}</td>
                  <td style={{ fontFamily: "IBM Plex Mono", fontWeight: 600 }}>{item.quantity}</td>
                  <td style={{ fontFamily: "IBM Plex Mono" }}>{item.unit_price ? `$${item.unit_price.toFixed(2)}` : "—"}</td>
                  <td>
                    {item.is_low_stock
                      ? <span className="badge badge-warn">⚠ Low</span>
                      : <span className="badge badge-success">OK</span>}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="btn btn-ghost" style={{ padding: "5px 10px" }} onClick={() => { setEditItem(item); setShowAddModal(true); }}>Edit</button>
                      <button className="btn btn-ghost" style={{ padding: "5px 10px" }} title="View history" onClick={() => setHistoryItem(item)}><Icon.Clock /></button>
                      <button className="btn btn-danger" style={{ padding: "5px 10px" }} onClick={() => deleteItem(item.id)}>Del</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showAddModal && (
        <ItemModal
          item={editItem}
          prefill={barcodePrefill}
          onClose={() => { setShowAddModal(false); setBarcodePrefill(null); }}
          onSaved={() => { setShowAddModal(false); setBarcodePrefill(null); loadItems(); loadSummary(); }}
        />
      )}
      {showBarcodeModal && (
        <BarcodeScannerModal
          onScanned={handleBarcodeScan}
          searching={barcodeSearching}
          onClose={() => setShowBarcodeModal(false)}
        />
      )}
      {showReceiptModal && (
        <ReceiptModal
          onClose={() => setShowReceiptModal(false)}
          onDone={() => { setShowReceiptModal(false); loadItems(); loadSummary(); }}
        />
      )}
      {historyItem && (
        <ItemHistoryDrawer item={historyItem} onClose={() => setHistoryItem(null)} />
      )}
    </>
  );
}
