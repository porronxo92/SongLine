import { appPath } from '../lib/routes';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { Button, Card, Screen } from '../components/ui';
import { es } from '../i18n/es';
import { accountRequest } from '../lib/account';

export default function Recovery({ reset = false }: { reset?: boolean }) {
  const [params] = useSearchParams();
  const [token] = useState(() => params.get('token'));
  useEffect(() => {
    if (reset && token) window.history.replaceState(window.history.state, '', window.location.pathname);
  }, [reset, token]);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await accountRequest<unknown>(
        reset ? 'reset' : 'forgot',
        reset ? { token, password: value } : { email: value.trim() },
      );
      setDone(true);
      setValue('');
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 503
          ? es.account.recoveryUnavailable
          : reset
            ? es.account.resetInvalid
            : es.account.error,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen title={reset ? es.account.reset : es.account.forgot} back={appPath('login')}>
      <Card>
        {done ? (
          <p role="status">{reset ? es.account.resetDone : es.account.resetSent}</p>
        ) : reset && !token ? (
          <p role="alert">{es.account.resetInvalid}</p>
        ) : (
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              void submit(event);
            }}
          >
            <p className="help">{reset ? es.account.passwordHelp : es.account.resetHelp}</p>
            <label className="flex flex-col gap-2">
              {reset ? es.account.password : es.account.email}
              <input
                className="input"
                required
                type={reset ? 'password' : 'email'}
                autoComplete={reset ? 'new-password' : 'email'}
                minLength={reset ? 12 : undefined}
                maxLength={reset ? 128 : 254}
                value={value}
                onChange={(event) => {
                  setValue(event.target.value);
                }}
              />
            </label>
            {error ? <p role="alert">{error}</p> : null}
            <Button type="submit" busy={busy}>
              {reset ? es.account.reset : es.account.requestReset}
            </Button>
          </form>
        )}
      </Card>
      <Link className="btn btn-secondary" to={appPath('login')}>
        {es.account.login}
      </Link>
      {reset ? (
        <Link className="btn btn-ghost" to={appPath('recuperar')}>
          {es.account.requestReset}
        </Link>
      ) : null}
    </Screen>
  );
}
