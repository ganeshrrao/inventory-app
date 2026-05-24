import { NavLink, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import "./App.css";
import Icon from "./icons.jsx";
import InventoryPage from "./pages/InventoryPage.jsx";
import ReceiptsPage from "./pages/ReceiptsPage.jsx";
import CategoriesPage from "./pages/CategoriesPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";

const navItems = [
  { to: "/",          label: "All Inventory", icon: <Icon.Box />,     end: true },
  { to: "/low-stock", label: "Low Stock",     icon: <Icon.Alert /> },
  { to: "/receipts",  label: "Receipts",      icon: <Icon.Receipt /> },
  { to: "/categories",label: "Categories",    icon: <Icon.Tag /> },
  { to: "/history",   label: "History",       icon: <Icon.Clock /> },
];

function AppShell() {
  const navigate = useNavigate();

  function logout() {
    localStorage.removeItem("token");
    navigate("/login", { replace: true });
  }

  return (
    <div className="app">
      <nav className="sidebar">
        <div className="sidebar-logo">📦 InvManager</div>
        {navItems.map(({ to, label, icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
          >
            {icon} {label}
          </NavLink>
        ))}
        <button className="nav-item nav-logout" onClick={logout}>
          <Icon.LogOut /> Sign Out
        </button>
      </nav>

      <main className="main">
        <Routes>
          <Route path="/"           element={<InventoryPage />} />
          <Route path="/low-stock"  element={<InventoryPage lowStockOnly />} />
          <Route path="/receipts"   element={<ReceiptsPage />} />
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/history"    element={<HistoryPage />} />
          <Route path="*"           element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
