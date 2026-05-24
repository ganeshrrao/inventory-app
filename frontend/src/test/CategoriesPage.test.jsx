import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import CategoriesPage from '../pages/CategoriesPage';

vi.mock('../api.js', () => ({
  apiFetch: vi.fn(),
  API: 'http://localhost:8000/api',
}));

import { apiFetch } from '../api.js';

const CATS = [
  { id: 'c1', name: 'Power Tools', description: 'Heavy duty', item_count: 3 },
  { id: 'c2', name: 'Hand Tools',  description: '',            item_count: 0 },
];

beforeEach(() => {
  apiFetch.mockReset();
  window.confirm = vi.fn(() => true);
});

describe('CategoriesPage', () => {
  it('shows empty state when there are no categories', async () => {
    apiFetch.mockResolvedValue([]);
    render(<CategoriesPage />);
    await waitFor(() => expect(screen.getByText(/no categories yet/i)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /load default categories/i })).toBeInTheDocument();
  });

  it('renders category cards when categories exist', async () => {
    apiFetch.mockResolvedValue(CATS);
    render(<CategoriesPage />);
    await waitFor(() => expect(screen.getByText('Power Tools')).toBeInTheDocument());
    expect(screen.getByText('Hand Tools')).toBeInTheDocument();
    expect(screen.getByText('3 items')).toBeInTheDocument();
    expect(screen.getByText('0 items')).toBeInTheDocument();
  });

  it('shows category description when present', async () => {
    apiFetch.mockResolvedValue(CATS);
    render(<CategoriesPage />);
    await waitFor(() => expect(screen.getByText('Heavy duty')).toBeInTheDocument());
  });

  it('opens the add modal on "Add Category" click', async () => {
    apiFetch.mockResolvedValue(CATS);
    render(<CategoriesPage />);
    await waitFor(() => screen.getByText('Power Tools'));
    fireEvent.click(screen.getByRole('button', { name: /add category/i }));
    expect(screen.getByText('New Category')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/e\.g\. Power Tools/i)).toBeInTheDocument();
  });

  it('saves a new category and refreshes the list', async () => {
    const newCat = { id: 'c3', name: 'Storage', description: '', item_count: 0 };
    apiFetch
      .mockResolvedValueOnce(CATS)               // initial load
      .mockResolvedValueOnce(newCat)             // POST /categories
      .mockResolvedValueOnce([...CATS, newCat]); // reload after save
    render(<CategoriesPage />);
    await waitFor(() => screen.getByText('Power Tools'));
    fireEvent.click(screen.getByRole('button', { name: /add category/i }));
    await userEvent.type(screen.getByPlaceholderText(/e\.g\. Power Tools/i), 'Storage');
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));
    await waitFor(() => expect(screen.getByText('Storage')).toBeInTheDocument());
  });

  it('shows an error if name is empty on save', async () => {
    apiFetch.mockResolvedValue(CATS);
    render(<CategoriesPage />);
    await waitFor(() => screen.getByText('Power Tools'));
    fireEvent.click(screen.getByRole('button', { name: /add category/i }));
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }));
    expect(screen.getByText(/name is required/i)).toBeInTheDocument();
  });

  it('opens edit modal with existing values pre-filled', async () => {
    apiFetch.mockResolvedValue(CATS);
    render(<CategoriesPage />);
    await waitFor(() => screen.getByText('Power Tools'));
    // click the first Edit button
    fireEvent.click(screen.getAllByRole('button', { name: /edit/i })[0]);
    expect(screen.getByText('Edit Category')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Power Tools')).toBeInTheDocument();
  });

  it('calls DELETE and reloads after confirming delete', async () => {
    apiFetch
      .mockResolvedValueOnce(CATS)      // initial load
      .mockResolvedValueOnce(null)      // DELETE
      .mockResolvedValueOnce([CATS[1]]);// reload
    render(<CategoriesPage />);
    await waitFor(() => screen.getByText('Power Tools'));
    fireEvent.click(screen.getAllByRole('button', { name: /del/i })[0]);
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByText('Power Tools')).not.toBeInTheDocument());
  });

  it('calls the seed endpoint when "Load Defaults" is clicked', async () => {
    apiFetch
      .mockResolvedValueOnce([])               // initial load (empty)
      .mockResolvedValueOnce({ created: 10 })  // POST /categories/seed
      .mockResolvedValueOnce(CATS);            // reload after seed
    render(<CategoriesPage />);
    await waitFor(() => screen.getByText(/no categories yet/i));
    fireEvent.click(screen.getByRole('button', { name: /load default categories/i }));
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/categories/seed', expect.objectContaining({ method: 'POST' })));
  });
});
