import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import ItemModal from '../components/ItemModal';

vi.mock('../api.js', () => ({
  apiFetch: vi.fn(),
  API: 'http://localhost:8000/api',
}));

import { apiFetch } from '../api.js';

const CATEGORIES = [
  { id: 'cat-1', name: 'Power Tools' },
  { id: 'cat-2', name: 'Hand Tools' },
];

beforeEach(() => {
  apiFetch.mockReset();
  apiFetch.mockResolvedValue(CATEGORIES); // default: categories load
});

const noop = () => {};

describe('ItemModal', () => {
  it('renders all form fields', async () => {
    render(<ItemModal onClose={noop} onSaved={noop} />);
    expect(screen.getByPlaceholderText('Item name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('HD item #')).toBeInTheDocument();
    expect(screen.getByText('Quantity')).toBeInTheDocument();
    expect(screen.getByText(/unit price/i)).toBeInTheDocument();
    expect(screen.getByText(/low stock threshold/i)).toBeInTheDocument();
  });

  it('shows "Add Inventory Item" title for new items', () => {
    render(<ItemModal onClose={noop} onSaved={noop} />);
    expect(screen.getByText('Add Inventory Item')).toBeInTheDocument();
  });

  it('shows "Edit Item" title when editing', () => {
    const item = { id: '1', name: 'Drill', sku: '', quantity: 5, unit_price: 20, low_stock_threshold: 5, description: '', image_url: null, category: null };
    render(<ItemModal item={item} onClose={noop} onSaved={noop} />);
    expect(screen.getByText('Edit Item')).toBeInTheDocument();
  });

  it('pre-fills form fields when editing an existing item', () => {
    const item = { id: '1', name: 'Drill', sku: 'SKU-001', quantity: 10, unit_price: 29.99, low_stock_threshold: 5, description: 'A drill', image_url: null, category: { id: 'cat-1', name: 'Power Tools' } };
    render(<ItemModal item={item} onClose={noop} onSaved={noop} />);
    expect(screen.getByDisplayValue('Drill')).toBeInTheDocument();
    expect(screen.getByDisplayValue('SKU-001')).toBeInTheDocument();
    expect(screen.getByDisplayValue('10')).toBeInTheDocument();
  });

  it('loads and renders categories in the dropdown', async () => {
    render(<ItemModal onClose={noop} onSaved={noop} />);
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Power Tools' })).toBeInTheDocument();
      expect(screen.getByRole('option', { name: 'Hand Tools' })).toBeInTheDocument();
    });
  });

  it('shows inline new-category input when "+ New category" is selected', async () => {
    render(<ItemModal onClose={noop} onSaved={noop} />);
    await waitFor(() => screen.getByRole('option', { name: /New category/i }));
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '__new__' } });
    expect(screen.getByPlaceholderText('Category name')).toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', () => {
    const onClose = vi.fn();
    render(<ItemModal onClose={onClose} onSaved={noop} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onSaved after a successful save', async () => {
    const onSaved = vi.fn();
    apiFetch
      .mockResolvedValueOnce(CATEGORIES)   // categories load
      .mockResolvedValueOnce({ id: 'new-1', name: 'Hammer', quantity: 1 }); // POST /items
    render(<ItemModal onClose={noop} onSaved={onSaved} />);
    await userEvent.type(screen.getByPlaceholderText('Item name'), 'Hammer');
    fireEvent.click(screen.getByText('Save Item'));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it('shows an error message when save fails', async () => {
    apiFetch
      .mockResolvedValueOnce(CATEGORIES)
      .mockRejectedValueOnce(new Error('Server error'));
    render(<ItemModal onClose={noop} onSaved={noop} />);
    await userEvent.type(screen.getByPlaceholderText('Item name'), 'Hammer');
    fireEvent.click(screen.getByText('Save Item'));
    await waitFor(() => expect(screen.getByText('Server error')).toBeInTheDocument());
  });
});
