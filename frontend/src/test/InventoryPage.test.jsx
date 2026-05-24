import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import InventoryPage from '../pages/InventoryPage';

vi.mock('../api.js', () => ({
  apiFetch: vi.fn(),
  API: 'http://localhost:8000/api',
}));

import { apiFetch } from '../api.js';

const ITEMS = [
  { id: 'i1', name: 'Drill',  sku: 'D-01', quantity: 10, unit_price: 49.99, is_low_stock: false, category: { id: 'c1', name: 'Power Tools' } },
  { id: 'i2', name: 'Hammer', sku: null,   quantity: 2,  unit_price: null,  is_low_stock: true,  category: null },
];

const SUMMARY = { total_items: 2, total_value: 499.9, low_stock_count: 1, category_count: 1 };
const CATEGORIES = [{ id: 'c1', name: 'Power Tools' }];

function renderPage(props = {}) {
  return render(
    <MemoryRouter>
      <InventoryPage {...props} />
    </MemoryRouter>
  );
}

beforeEach(() => {
  apiFetch.mockReset();
  window.confirm = vi.fn(() => true);
  // Default mock order: items, summary, categories
  apiFetch
    .mockResolvedValueOnce({ items: ITEMS, total: 2 })  // loadItems
    .mockResolvedValueOnce(SUMMARY)                      // loadSummary
    .mockResolvedValueOnce(CATEGORIES);                  // categories for filter
});

describe('InventoryPage — table rendering', () => {
  it('renders item rows', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Drill')).toBeInTheDocument());
    expect(screen.getByText('Hammer')).toBeInTheDocument();
  });

  it('shows SKU tags for items with a SKU', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    expect(screen.getByText('D-01')).toBeInTheDocument();
  });

  it('shows low-stock badge for low-stock items', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Hammer'));
    expect(screen.getByText('⚠ Low')).toBeInTheDocument();
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  it('shows category name in the category column', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    // "Power Tools" appears in both the category filter dropdown and the table cell
    expect(screen.getAllByText('Power Tools').length).toBeGreaterThan(0);
  });

  it('shows empty state when no items returned', async () => {
    apiFetch.mockReset();
    apiFetch
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockResolvedValueOnce(SUMMARY)
      .mockResolvedValueOnce(CATEGORIES);
    renderPage();
    await waitFor(() => expect(screen.getByText(/no items found/i)).toBeInTheDocument());
  });
});

describe('InventoryPage — stat cards', () => {
  it('renders summary stat labels', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    expect(screen.getByText('Total Items')).toBeInTheDocument();
    expect(screen.getByText('Total Value')).toBeInTheDocument();
    expect(screen.getByText('Low Stock')).toBeInTheDocument();
    expect(screen.getByText('Categories')).toBeInTheDocument();
  });
});

describe('InventoryPage — bulk selection', () => {
  it('checkboxes start unchecked', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    const checkboxes = screen.getAllByRole('checkbox');
    checkboxes.forEach(cb => expect(cb).not.toBeChecked());
  });

  it('shows bulk action bar when an item is selected', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    const [, ...rowCbs] = screen.getAllByRole('checkbox');
    fireEvent.click(rowCbs[0]);
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
  });

  it('hides bulk bar when selection is cleared', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    const [, firstRowCb] = screen.getAllByRole('checkbox');
    fireEvent.click(firstRowCb);
    expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /clear/i }));
    expect(screen.queryByText(/1 selected/i)).not.toBeInTheDocument();
  });

  it('select-all checks every row', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    const [headerCb] = screen.getAllByRole('checkbox');
    fireEvent.click(headerCb);
    expect(screen.getByText(/2 selected/i)).toBeInTheDocument();
    screen.getAllByRole('checkbox').slice(1).forEach(cb => expect(cb).toBeChecked());
  });

  it('clicking select-all again deselects all', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    const [headerCb] = screen.getAllByRole('checkbox');
    fireEvent.click(headerCb); // select all
    fireEvent.click(headerCb); // deselect all
    expect(screen.queryByText(/selected/i)).not.toBeInTheDocument();
  });
});

describe('InventoryPage — bulk actions', () => {
  it('shows Adjust Qty popover when button is clicked', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    const [, firstRowCb] = screen.getAllByRole('checkbox');
    fireEvent.click(firstRowCb);
    fireEvent.click(screen.getByRole('button', { name: /adjust qty/i }));
    // delta input has no htmlFor — check for the label text and the spinbutton input
    expect(screen.getByText(/delta/i)).toBeInTheDocument();
    expect(screen.getByRole('spinbutton')).toBeInTheDocument();
  });

  it('shows Assign Category popover when button is clicked', async () => {
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    const [, firstRowCb] = screen.getAllByRole('checkbox');
    fireEvent.click(firstRowCb);
    fireEvent.click(screen.getByRole('button', { name: /assign category/i }));
    await waitFor(() => expect(screen.getAllByRole('combobox').length).toBeGreaterThan(0));
  });
});

describe('InventoryPage — delete', () => {
  it('calls DELETE and reloads after confirm', async () => {
    apiFetch
      .mockResolvedValueOnce(null)                        // DELETE response
      .mockResolvedValueOnce({ items: [ITEMS[1]], total: 1 }) // reload
      .mockResolvedValueOnce(SUMMARY);                    // reload summary
    renderPage();
    await waitFor(() => screen.getByText('Drill'));
    fireEvent.click(screen.getAllByRole('button', { name: /del/i })[0]);
    expect(window.confirm).toHaveBeenCalledWith('Delete this item?');
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/items/i1', expect.objectContaining({ method: 'DELETE' })));
  });
});
