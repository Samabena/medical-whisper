import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { accountsApi } from "../api/client";
import type { Account } from "../api/types";
import { Badge, Card, CardHeader, Loading, PageHeader } from "../components/ui";
import { IconAccounts, IconConsole, IconGlobe } from "../components/Icons";

export function DashboardPage() {
  const [accounts, setAccounts] = useState<Account[] | null>(null);

  useEffect(() => {
    accountsApi.list().then(setAccounts).catch(() => setAccounts([]));
  }, []);

  const total = accounts?.length ?? 0;
  const actifs = accounts?.filter((a) => a.actif).length ?? 0;
  const fr = accounts?.filter((a) => a.langue === "fr").length ?? 0;
  const en = total - fr;

  const stats = [
    { icon: <IconAccounts size={20} />, value: total, label: "Comptes clients" },
    { icon: <IconConsole size={20} />, value: actifs, label: "Comptes actifs" },
    { icon: <IconGlobe size={20} />, value: `${fr} / ${en}`, label: "Français / English" },
  ];

  return (
    <div>
      <PageHeader title="Tableau de bord" sub="Vue d'ensemble de votre plateforme Voice-to-Form." />

      <div className="stats-grid">
        {stats.map((s) => (
          <div className="stat-card" key={s.label}>
            <div className="stat-top">
              <div className="stat-icon">{s.icon}</div>
            </div>
            <div className="stat-value">{accounts === null ? "—" : s.value}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      <Card>
        <CardHeader title="Comptes récents" action={<Link to="/accounts" className="btn btn-secondary btn-sm">Voir tout</Link>} />
        {accounts === null ? (
          <Loading />
        ) : (
          <table className="table">
            <thead>
              <tr><th>Nom</th><th>Email</th><th>Langue</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {accounts.slice(0, 5).map((a) => (
                <tr key={a.id}>
                  <td className="cell-strong"><Link to={`/accounts/${a.id}`}>{a.nom}</Link></td>
                  <td className="cell-muted">{a.email_contact}</td>
                  <td><Badge tone="primary">{a.langue.toUpperCase()}</Badge></td>
                  <td>
                    {a.actif ? <Badge tone="success" dot>Actif</Badge> : <Badge tone="neutral" dot>Inactif</Badge>}
                  </td>
                </tr>
              ))}
              {accounts.length === 0 && (
                <tr><td colSpan={4} className="muted" style={{ textAlign: "center", padding: 24 }}>Aucun compte pour le moment.</td></tr>
              )}
            </tbody>
          </table>
        )}
      </Card>

      <p className="subtle mt-4">
        Les métriques d'usage et de latence détaillées sont exposées sur <code>/metrics</code> (observabilité).
      </p>
    </div>
  );
}
