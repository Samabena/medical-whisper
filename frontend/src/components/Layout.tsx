import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/auth";
import { IconAccounts, IconConsole, IconDashboard, IconLogout, IconWave } from "./Icons";

export function Layout() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">
            <IconWave size={18} />
          </div>
          <div>
            <div className="brand-name">Voice-to-Form</div>
          </div>
          <span className="brand-badge">LIVE</span>
        </div>

        <nav className="nav">
          <div className="nav-section">Plateforme</div>
          <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <IconDashboard size={18} /> Tableau de bord
          </NavLink>
          <NavLink to="/accounts" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <IconAccounts size={18} /> Comptes
          </NavLink>
          <NavLink to="/console" className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <IconConsole size={18} /> Console live
          </NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="user-row">
            <div className="avatar">A</div>
            <div className="flex-1">
              <div style={{ fontWeight: 600, fontSize: 13 }}>Administrateur</div>
              <div className="subtle">admin@local</div>
            </div>
          </div>
          <button
            className="btn btn-ghost btn-sm btn-block"
            style={{ marginTop: 6, justifyContent: "flex-start" }}
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            <IconLogout size={16} /> Déconnexion
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="container">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
