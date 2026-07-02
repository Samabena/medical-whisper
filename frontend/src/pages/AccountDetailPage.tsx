import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { accountsApi, keysApi } from "../api/client";
import type { Account, ApiKey, Language } from "../api/types";
import { Badge, Button, Card, CardHeader, Field, Loading, PageHeader } from "../components/ui";
import { IconArrowLeft, IconCopy, IconForm, IconKey, IconPlus, IconTrash } from "../components/Icons";
import { useToast } from "../components/Toast";

export function AccountDetailPage() {
  const { id } = useParams();
  const accountId = Number(id);
  const [account, setAccount] = useState<Account | null>(null);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [nouvelleCle, setNouvelleCle] = useState<string | null>(null);
  const toast = useToast();

  const reloadKeys = () => keysApi.list(accountId).then(setKeys).catch(() => {});
  useEffect(() => {
    accountsApi.get(accountId).then(setAccount).catch(() => {});
    reloadKeys();
  }, [accountId]);

  const save = async (patch: Partial<Account>, label: string) => {
    try {
      setAccount(await accountsApi.update(accountId, patch));
      toast("success", `${label} enregistré.`);
    } catch (e: any) {
      toast("error", e?.message ?? "Échec.");
    }
  };

  const createKey = async () => {
    try {
      const created = await keysApi.create(accountId, "Clé");
      setNouvelleCle(created.cle_en_clair);
      reloadKeys();
    } catch (e: any) {
      toast("error", e?.message ?? "Échec.");
    }
  };

  const revoke = async (keyId: number) => {
    await keysApi.revoke(accountId, keyId);
    toast("success", "Clé révoquée.");
    reloadKeys();
  };

  const copy = (text: string) => {
    navigator.clipboard?.writeText(text);
    toast("success", "Copié dans le presse-papiers.");
  };

  if (!account) return <Loading />;

  return (
    <div>
      <PageHeader
        breadcrumb={<><Link to="/accounts">Comptes</Link><IconArrowLeft size={12} style={{ transform: "rotate(180deg)" }} /><span>{account.nom}</span></>}
        title={account.nom}
        sub={account.email_contact}
        actions={
          <>
            {account.actif ? <Badge tone="success" dot>Actif</Badge> : <Badge tone="neutral" dot>Inactif</Badge>}
            <Link to={`/accounts/${accountId}/forms`} className="btn btn-secondary"><IconForm size={16} /> Formulaires</Link>
          </>
        }
      />

      <Card>
        <CardHeader title="Configuration" sub="Langue, persona vocale et voix de l'agent." />
        <div className="card-body">
          <div className="grid-2">
            <Field label="Langue par défaut">
              <select className="select" value={account.langue} onChange={(e) => save({ langue: e.target.value as Language }, "Langue")}>
                <option value="fr">Français</option>
                <option value="en">English</option>
              </select>
            </Field>
            <Field label="Référence de voix" hint="Identifiant de la voix de synthèse (Piper).">
              <input className="input" defaultValue={account.voice_prompt} placeholder="voix-fr-medium" onBlur={(e) => e.target.value !== account.voice_prompt && save({ voice_prompt: e.target.value }, "Voix")} />
            </Field>
          </div>
          <Field label="Persona (prompt vocal)" hint="Laisser vide pour générer automatiquement depuis le formulaire.">
            <textarea className="textarea" defaultValue={account.persona_prompt} placeholder="Tu es un assistant clinique courtois…" onBlur={(e) => e.target.value !== account.persona_prompt && save({ persona_prompt: e.target.value }, "Persona")} />
          </Field>
          <label className="checkbox">
            <input type="checkbox" checked={account.actif} onChange={(e) => save({ actif: e.target.checked }, "Statut")} />
            Compte actif (les clés inactives sont refusées)
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Clés API"
          sub="Utilisées par le backend client pour démarrer des sessions."
          action={<Button variant="primary" onClick={createKey}><IconPlus size={16} /> Générer une clé</Button>}
        />
        <div className="card-body">
          {nouvelleCle && (
            <div className="key-reveal">
              <div className="flex-1">
                <div className="subtle" style={{ color: "#cbd5e1", marginBottom: 4 }}>Clé créée — copiez-la, elle ne sera plus affichée.</div>
                <code>{nouvelleCle}</code>
              </div>
              <Button variant="secondary" className="btn-sm" onClick={() => copy(nouvelleCle)}><IconCopy size={15} /> Copier</Button>
            </div>
          )}
        </div>
        {keys.length === 0 ? (
          <div className="card-body" style={{ paddingTop: 0 }}><p className="muted">Aucune clé. Générez-en une pour permettre l'intégration.</p></div>
        ) : (
          <table className="table">
            <thead><tr><th>Label</th><th>Clé</th><th>Statut</th><th></th></tr></thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td className="cell-strong"><span className="row" style={{ gap: 8 }}><IconKey size={15} /> {k.label}</span></td>
                  <td><span className="code-pill">{k.key_masquee}</span></td>
                  <td>{k.actif ? <Badge tone="success" dot>Active</Badge> : <Badge tone="neutral" dot>Révoquée</Badge>}</td>
                  <td className="actions">{k.actif && <Button variant="danger" className="btn-sm" onClick={() => revoke(k.id)}><IconTrash size={15} /> Révoquer</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
