/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_EBRT_API_BASE_URL?: string;
  readonly VITE_EBRT_PUBLIC_LIVE?: string;
  readonly VITE_EBRT_RECORDED_ONLY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
