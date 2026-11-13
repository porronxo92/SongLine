import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Recovery from './screens/Recovery';
import Plans from './screens/Plans';
import { Account, AccountLogin, AccountRequired } from './screens/Account';
import { useAccount } from './lib/account';
import { APP_BASE_PATH, appPath } from './lib/routes';
import Create from './screens/Create';
import CreateGenres from './screens/CreateGenres';
import Landing from './screens/Landing';
import GameHome from './screens/GameHome';
import { HostAudio, HostIdentity, HostLogin } from './screens/HostFlow';
import Join from './screens/Join';
import Room from './screens/Room';

/** Old bookmarks, shared rooms and OAuth/email callbacks keep their query and fragment. */
function LegacyAppRedirect() {
  const location = useLocation();
  const destination = location.pathname === '/jugar' ? appPath() : appPath(location.pathname);
  return (
    <Navigate to={destination + location.search + location.hash} state={location.state as unknown} replace />
  );
}

export default function App() {
  const load = useAccount((state) => state.load);
  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path={APP_BASE_PATH}>
          <Route index element={<GameHome />} />
          <Route path="recuperar" element={<Recovery />} />
          <Route path="reset-password" element={<Recovery key="reset" reset />} />
          <Route path="login" element={<AccountLogin />} />
          <Route path="registro" element={<AccountLogin key="register" register />} />
          <Route
            path="cuenta"
            element={
              <AccountRequired>
                <Account />
              </AccountRequired>
            }
          />
          <Route path="planes" element={<Plans />} />
          <Route
            path="crear"
            element={
              <AccountRequired>
                <Create />
              </AccountRequired>
            }
          />
          <Route
            path="crear/generos"
            element={
              <AccountRequired>
                <CreateGenres />
              </AccountRequired>
            }
          />
          <Route
            path="anfitrion/login"
            element={
              <AccountRequired>
                <HostLogin />
              </AccountRequired>
            }
          />
          <Route
            path="anfitrion/audio"
            element={
              <AccountRequired>
                <HostAudio />
              </AccountRequired>
            }
          />
          <Route
            path="anfitrion/equipo"
            element={
              <AccountRequired>
                <HostIdentity />
              </AccountRequired>
            }
          />
          <Route path="unirse" element={<Join />} />
          <Route path="unirse/:code" element={<Join />} />
          <Route path="sala/:code" element={<Room />} />
          <Route path="*" element={<Navigate to={appPath()} replace />} />
        </Route>
        {[
          '/jugar',
          '/crear/*',
          '/anfitrion/*',
          '/unirse',
          '/unirse/:code',
          '/sala/:code',
          '/login',
          '/registro',
          '/cuenta',
          '/planes',
          '/recuperar',
          '/reset-password',
        ].map((path) => (
          <Route key={path} path={path} element={<LegacyAppRedirect />} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
