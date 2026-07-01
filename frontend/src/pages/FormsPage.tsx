import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { formsApi } from "../api/client";
import type { FieldDef, FieldType, FormDef, Language } from "../api/types";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Loading, Modal, PageHeader } from "../components/ui";
import { IconArrowLeft, IconCheck, IconForm, IconPlus, IconTrash } from "../components/Icons";
import { useToast } from "../components/Toast";

const TYPES: FieldType[] = ["string", "text", "date", "int", "number", "enum", "bool"];
const emptyField = (): FieldDef => ({ name: "", label: "", type: "string", required: false, enum_values: [], description: "" });

export function FormsPage() {
  const { id } = useParams();
  const accountId = Number(id);
  const [forms, setForms] = useState<FormDef[] | null>(null);
  const [open, setOpen] = useState(false);
  const [formId, setFormId] = useState("");
  const [titre, setTitre] = useState("");
  const [langue, setLangue] = useState<Language | "">("");
  const [fields, setFields] = useState<FieldDef[]>([emptyField()]);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const reload = () => formsApi.list(accountId).then(setForms).catch(() => setForms([]));
  useEffect(() => {
    reload();
  }, [accountId]);

  const setField = (i: number, patch: Partial<FieldDef>) => setFields((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)));

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await formsApi.create(accountId, { form_id: formId, titre, langue: langue || null, fields: fields.filter((f) => f.name) });
      toast("success", "Formulaire créé (brouillon).");
      setOpen(false);
      setFormId(""); setTitre(""); setFields([emptyField()]);
      reload();
    } catch (err: any) {
      toast("error", err?.message ?? "Création impossible.");
    } finally {
      setBusy(false);
    }
  };

  const publish = async (fid: string) => {
    await formsApi.publish(accountId, fid);
    toast("success", "Formulaire publié.");
    reload();
  };

  return (
    <div>
      <PageHeader
        breadcrumb={<><Link to="/accounts">Comptes</Link><span style={{ transform: "rotate(180deg)", display: "inline-flex" }}><IconArrowLeft size={12} /></span><Link to={`/accounts/${accountId}`}>Compte</Link><span style={{ transform: "rotate(180deg)", display: "inline-flex" }}><IconArrowLeft size={12} /></span><span>Formulaires</span></>}
        title="Formulaires"
        sub="Construisez les formulaires médicaux remplis par la voix."
        actions={<Button variant="primary" onClick={() => setOpen(true)}><IconPlus size={16} /> Nouveau formulaire</Button>}
      />

      <Card>
        {forms === null ? (
          <Loading />
        ) : forms.length === 0 ? (
          <EmptyState icon={<IconForm size={24} />} title="Aucun formulaire" sub="Créez et publiez un formulaire pour le rendre disponible aux clients."
            action={<Button variant="primary" onClick={() => setOpen(true)}><IconPlus size={16} /> Nouveau formulaire</Button>} />
        ) : (
          <table className="table">
            <thead><tr><th>Identifiant</th><th>Titre</th><th>Version</th><th>Statut</th><th></th></tr></thead>
            <tbody>
              {forms.map((f) => (
                <tr key={`${f.form_id}-${f.version}`}>
                  <td><span className="code-pill">{f.form_id}</span></td>
                  <td className="cell-strong">{f.titre}</td>
                  <td className="cell-muted">v{f.version}</td>
                  <td>{f.statut === "published" ? <Badge tone="success" dot>Publié</Badge> : <Badge tone="warning" dot>Brouillon</Badge>}</td>
                  <td className="actions">{f.statut === "draft" && <Button variant="secondary" className="btn-sm" onClick={() => publish(f.form_id)}><IconCheck size={15} /> Publier</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {open && (
        <Modal
          title="Nouveau formulaire"
          wide
          onClose={() => setOpen(false)}
          footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Annuler</Button><Button variant="primary" loading={busy} disabled={!formId || !titre} onClick={create as any}>Créer le brouillon</Button></>}
        >
          <form onSubmit={create}>
            <div className="grid-2">
              <Field label="Identifiant (slug)" hint="Référencé par le client à la création de session.">
                <input className="input" placeholder="consultation" value={formId} onChange={(e) => setFormId(e.target.value)} autoFocus />
              </Field>
              <Field label="Titre">
                <input className="input" placeholder="Consultation médicale" value={titre} onChange={(e) => setTitre(e.target.value)} />
              </Field>
            </div>
            <Field label="Langue" hint="Vide = langue du compte.">
              <select className="select" value={langue} onChange={(e) => setLangue(e.target.value as Language | "")}>
                <option value="">Langue du compte</option>
                <option value="fr">Français</option>
                <option value="en">English</option>
              </select>
            </Field>

            <div className="between" style={{ margin: "18px 0 8px" }}>
              <span className="label">Champs</span>
              <Button variant="secondary" className="btn-sm" type="button" onClick={() => setFields((fs) => [...fs, emptyField()])}><IconPlus size={15} /> Ajouter</Button>
            </div>
            <div className="stack">
              {fields.map((f, i) => (
                <div className="card card-pad" key={i} style={{ background: "var(--surface-2)" }}>
                  <div className="row">
                    <input className="input flex-1" placeholder="nom" value={f.name} onChange={(e) => setField(i, { name: e.target.value })} />
                    <input className="input flex-1" placeholder="Étiquette" value={f.label} onChange={(e) => setField(i, { label: e.target.value })} />
                    <select className="select" value={f.type} onChange={(e) => setField(i, { type: e.target.value as FieldType })}>
                      {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <label className="checkbox"><input type="checkbox" checked={f.required} onChange={(e) => setField(i, { required: e.target.checked })} /> requis</label>
                    <button type="button" className="icon-btn" onClick={() => setFields((fs) => fs.filter((_, j) => j !== i))}><IconTrash size={16} /></button>
                  </div>
                  {f.type === "enum" && (
                    <input className="input mt-2" placeholder="valeurs autorisées, séparées par des virgules" value={f.enum_values.join(",")}
                      onChange={(e) => setField(i, { enum_values: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
                  )}
                </div>
              ))}
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
