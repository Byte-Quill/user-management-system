/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional API base; unset = same-origin "/api". */
  readonly VITE_API_URL?: string;
  /** Optional Google OAuth client ID; unset/empty disables Google Sign-In. */
  readonly VITE_GOOGLE_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}