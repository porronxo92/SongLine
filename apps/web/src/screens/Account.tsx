import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { Button, Card, Screen, Spinner } from '../components/ui';
import { es } from '../i18n/es';
import { useAccount } from '../lib/account';

export function AccountRequired({ children }: { children: ReactNode }) {
  const { user, ready, load } = useAccount();
  const location = useLocation();
  const [loadError, setLoadError] = useState(false);
  const [fake, setFake] = useState(false);
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    void load().catch((error: unknown) => {
      if (!(error instanceof ApiError && error.status === 401)) setLoadError(true);
    });
    void api
      .authStatus()
      .then((status) => {
        setFake(status.auth_mode === 'fake');
      })
      .catch(() => undefined)
      .finally(() => {
        setChecked(true);
      });
  }, [load]);
  if (loadError)
    return (
      <Screen title={es.account.title} back="/">
        <p role="alert">{es.account.unavailable}</p>
        <Button
          onClick={() => {
            setLoadError(false);
            void load().catch(() => {
              setLoadError(true);
            });
          }}
        >
          {es.common.retry}
        </Button>
      </Screen>
    );
  if (!ready || !checked) return <Spinner />;
  if (!user && !fake) return <Navigate to="/login" state={{ returnTo: location.pathname }} replace />;
  return <>{children}</>;
}

function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return es.account.error;
  if (error.status === 401) return es.account.invalid;
  if (error.status === 409) return es.account.duplicate;
  if (error.status === 429) return es.account.limited;
  if (error.status >= 500) return es.account.unavailable;
  return es.account.error;
}

export function AccountLogin({ register = false }: { register?: boolean }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { authenticate } = useAccount();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const state = location.state as { returnTo?: unknown } | null;
  const returnTo =
    typeof state?.returnTo === 'string' &&
    [
      '/crear',
      '/crear/generos',
      '/anfitrion/login',
      '/anfitrion/audio',
      '/anfitrion/equipo',
      '/cuenta',
      '/',
      '/jugar',
    ].includes(state.returnTo)
      ? state.returnTo === '/jugar'
        ? '/'
        : state.returnTo
      : '/';
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await authenticate(register, email.trim(), password, name.trim());
      navigate(returnTo, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen title={register ? es.account.register : es.account.login} back="/">
      <p className="help">{register ? es.account.registerHelp : es.account.loginHelp}</p>
      <Card>
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            void submit(event);
          }}
        >
          {register ? (
            <label className="flex flex-col gap-2">
              {es.account.name}
              <input
                className="input"
                autoComplete="nickname"
                maxLength={80}
                value={name}
                onChange={(event) => {
                  setName(event.target.value);
                }}
              />
            </label>
          ) : null}
          <label className="flex flex-col gap-2">
            {es.account.email}
            <input
              className="input"
              type="email"
              autoComplete="email"
              required
              maxLength={254}
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
              }}
            />
          </label>
          <label className="flex flex-col gap-2">
            {es.account.password}
            <input
              className="input"
              type="password"
              autoComplete={register ? 'new-password' : 'current-password'}
              required
              minLength={register ? 12 : undefined}
              maxLength={128}
              aria-describedby={register ? 'password-help' : undefined}
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
              }}
            />
          </label>
          {register ? (
            <p className="help" id="password-help">
              {es.account.passwordHelp}
            </p>
          ) : null}
          {error ? (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          ) : null}
          <Button type="submit" xl busy={busy}>
            {register ? es.account.register : es.account.login}
          </Button>
        </form>
      </Card>
      <Link className="btn btn-secondary" to={register ? '/login' : '/registro'} state={{ returnTo }}>
        {register ? es.account.hasAccount : es.account.noAccount}
      </Link>
      <p className="help">{es.account.spotifyHelp}</p>
      {!register ? (
        <Link className="btn btn-ghost" to="/recuperar">
          {es.account.forgot}
        </Link>
      ) : null}
    </Screen>
  );
}

export function Account() {
  const { user, logout } = useAccount();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!user) return <Navigate to="/login" replace />;
  return (
    <Screen title={es.account.title} back="/">
      <Card className="flex flex-col gap-3">
        <h2>{user.display_name || user.email}</h2>
        <p className="help break-words">{user.email}</p>
        <h3>{user.plan === 'premium' ? es.account.premium : es.account.free}</h3>
        <p>{user.plan === 'premium' ? es.account.premiumDetails : es.account.freeDetails}</p>
        <Link className="btn btn-secondary" to="/planes">
          {es.account.plans}
        </Link>
      </Card>
      <Card>
        <h2>{es.account.purchases}</h2>
        <p className="help">{es.account.noPurchases}</p>
      </Card>
      <Button
        variant="ghost"
        busy={busy}
        onClick={() => {
          setBusy(true);
          setError('');
          void logout()
            .then(() => {
              navigate('/', { replace: true });
            })
            .catch((err: unknown) => {
              setError(errorMessage(err));
            })
            .finally(() => {
              setBusy(false);
            });
        }}
      >
        {es.account.logout}
      </Button>
      {error ? <p role="alert">{error}</p> : null}
    </Screen>
  );
}
