import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/auth";
import { Button, Field } from "../components/ui";
import { IconWave } from "../components/Icons";

export function LoginPage() {
  const { login, authenticated } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (authenticated) navigate("/", { replace: true });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(password);
      navigate("/", { replace: true });
    } catch {
      setError("Mot de passe incorrect.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <div className="brand-logo">
            <IconWave size={24} />
          </div>
          <div>
            <h1>Voice-to-Form Live</h1>
            <div className="sub">Console d'administration</div>
          </div>
        </div>

        <Field label="Mot de passe administrateur">
          <input
            className="input"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
          />
        </Field>
        {error && <p className="error-text" style={{ marginBottom: 12 }}>{error}</p>}
        <Button type="submit" variant="primary" size="lg" block loading={busy} disabled={!password}>
          Se connecter
        </Button>
      </form>
    </div>
  );
}
