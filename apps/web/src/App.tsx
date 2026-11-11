import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import Recovery from './screens/Recovery';
import Landing, { Plans } from './screens/Landing';
import { Account, AccountLogin, AccountRequired } from './screens/Account';
import { useAccount } from './lib/account';
import { getStoredRoom } from './lib/session';
import Create from './screens/Create';
import CreateGenres from './screens/CreateGenres';
import Home from './screens/Home';
import { HostAudio, HostIdentity, HostLogin } from './screens/HostFlow';
import Join from './screens/Join';
import Room from './screens/Room';

let resumed = false;

/** Al recargar en la raíz con una sala guardada, vuelve a ella. */
function Resume() {
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    if (resumed) return;
    resumed = true;
    const code = getStoredRoom();
    if (code && location.pathname === '/jugar') navigate(`/sala/${code}`, { replace: true });
  }, [navigate, location.pathname]);
  return null;
}

export default function App() {
  const load = useAccount((state) => state.load);
  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);
  return (
    <BrowserRouter>
      <Resume />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/jugar" element={<Home />} />
        <Route path="/recuperar" element={<Recovery />} />
        <Route path="/reset-password" element={<Recovery key="reset" reset />} />
        <Route path="/login" element={<AccountLogin />} />
        <Route path="/registro" element={<AccountLogin key="register" register />} />
        <Route
          path="/cuenta"
          element={
            <AccountRequired>
              <Account />
            </AccountRequired>
          }
        />
        <Route path="/planes" element={<Plans />} />
        <Route
          path="/crear"
          element={
            <AccountRequired>
              <Create />
            </AccountRequired>
          }
        />
        <Route
          path="/crear/generos"
          element={
            <AccountRequired>
              <CreateGenres />
            </AccountRequired>
          }
        />
        <Route
          path="/anfitrion/login"
          element={
            <AccountRequired>
              <HostLogin />
            </AccountRequired>
          }
        />
        <Route
          path="/anfitrion/audio"
          element={
            <AccountRequired>
              <HostAudio />
            </AccountRequired>
          }
        />
        <Route
          path="/anfitrion/equipo"
          element={
            <AccountRequired>
              <HostIdentity />
            </AccountRequired>
          }
        />
        <Route path="/unirse" element={<Join />} />
        <Route path="/unirse/:code" element={<Join />} />
        <Route path="/sala/:code" element={<Room />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
