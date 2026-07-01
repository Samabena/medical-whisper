import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { accountsApi } from "../api/client";
import type { Account, Language } from "../api/types";
import { Badge, Button, Card, EmptyState, Field, Loading, Modal, PageHeader } from "../components/ui";
import { IconAccounts, IconChevronRight, IconForm, IconPlus } from "../components/Icons";
import { useToast } from "../components/Toast";

export function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [open, setOpen] = useState(false);
  const [nom, setNom] = useState("");
  const [email, setEmail] = useState("");
  const [langue, setLangue] = useState<Language>("fr");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();

  const reload = () => accountsApi.list().then(setAccounts).catch(() => setAccounts([]));
  useEffect(() => {
    reload();
  }, []);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const acc = await accountsApi.create({ nom, email_contact: email, langue });
      toast("success", "Compte créé.");
      setOpen(false);
      setNom("");
      setEmail("");
      navigate(`/accounts/${acc.id}`);
    } catch (err: any) {
      toast("error", err?.message ?? "Création impossible.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Comptes"
        sub="Les applications clientes qui intègrent Voice-to-Form."
        actions={
          <Button variant="primary" onClick={() => setOpen(true)}>
            <IconPlus size={16} /> Nouveau compte
          </Button>
        }
      />

      <Card>
        {accounts === null ? (
          <Loading />
        ) : accounts.length === 0 ? (
          <EmptyState
            icon={<IconAccounts size={24} />}
            title="Aucun compte"
            sub="Créez un premier compte client pour générer une clé API."
            action={<Button variant="primary" onClick={() => setOpen(true)}><IconPlus size={16} /> Nouveau compte</Button>}
          />
        ) : (
          <table className="table">
            <thead>
              <tr><th>Nom</th><th>Email</th><th>Langue</th><th>Statut</th><th></th></tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id} style={{ cursor: "pointer" }} onClick={() => navigate(`/accounts/${a.id}`)}>
                  <td className="cell-strong">{a.nom}</td>
                  <td className="cell-muted">{a.email_contact}</td>
                  <td><Badge tone="primary">{a.langue.toUpperCase()}</Badge></td>
                  <td>{a.actif ? <Badge tone="success" dot>Actif</Badge> : <Badge tone="neutral" dot>Inactif</Badge>}</td>
                  <td className="actions" onClick={(e) => e.stopPropagation()}>
                    <Link to={`/accounts/${a.id}/forms`} className="btn btn-ghost btn-sm"><IconForm size={15} /> Formulaires</Link>
                    <Link to={`/accounts/${a.id}`} className="btn btn-secondary btn-sm">Gérer <IconChevronRight size={15} /></Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {open && (
        <Modal
          title="Nouveau compte"
          onClose={() => setOpen(false)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setOpen(false)}>Annuler</Button>
              <Button variant="primary" loading={busy} disabled={!nom || !email} onClick={create as any}>Créer le compte</Button>
            </>
          }
        >
          <form onSubmit={create} id="acc-form">
            <Field label="Nom de l'application">
              <input className="input" placeholder="Ex. Clinique Saint-Pierre" value={nom} onChange={(e) => setNom(e.target.value)} autoFocus />
            </Field>
            <Field label="Email de contact">
              <input className="input" type="email" placeholder="contact@exemple.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Langue" hint="Détermine la voix et la langue du dialogue par défaut.">
              <select className="select" value={langue} onChange={(e) => setLangue(e.target.value as Language)}>
                <option value="fr">Français</option>
                <option value="en">English</option>
              </select>
            </Field>
          </form>
        </Modal>
      )}
    </div>
  );
}
