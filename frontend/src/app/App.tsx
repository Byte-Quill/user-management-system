import { GoogleOAuthProvider } from "@react-oauth/google";

import AppRoutes from "@/app/router";
import { GOOGLE_CLIENT_ID } from "@/app/config";

export default function App() {
  if (!GOOGLE_CLIENT_ID) {
    return <AppRoutes />;
  }
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AppRoutes />
    </GoogleOAuthProvider>
  );
}
