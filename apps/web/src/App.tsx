import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Recovery from './screens/Recovery';
import Plans from './screens/Plans';
import { Account, AccountLogin, AccountRequired } from './screens/Account';
import { useAccount } from './lib/account';
import Create from './screens/Create';
import CreateGenres from './screens/CreateGenres';
import Home from './screens/Home';
import { HostAudio, HostIdentity, HostLogin } from './screens/HostFlow';
import Join from './screens/Join';
import Room from './screens/Room';

export default function App() {
  const load = useAccount((state) => state.load);
  useEffect(() => {
    void load().catch(() => undefined);
  }, [load]);
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/jugar" element={<Navigate to="/" replace />} />
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
