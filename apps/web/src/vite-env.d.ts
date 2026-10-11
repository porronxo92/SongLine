/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** wss://… del servidor cuando la web y el servidor están en dominios distintos (Vercel + Render). */
  readonly VITE_WS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
