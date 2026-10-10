import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { getStoredRoom } from './lib/session';
import Create from './screens/Create';
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
    if (code && location.pathname === '/') navigate(`/sala/${code}`, { replace: true });
  }, [navigate, location.pathname]);
  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <Resume />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/crear" element={<Create />} />
        <Route path="/anfitrion/login" element={<HostLogin />} />
        <Route path="/anfitrion/audio" element={<HostAudio />} />
        <Route path="/anfitrion/equipo" element={<HostIdentity />} />
        <Route path="/unirse" element={<Join />} />
        <Route path="/unirse/:code" element={<Join />} />
        <Route path="/sala/:code" element={<Room />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
