import { GoogleLogin } from "@react-oauth/google";
import type { CredentialResponse } from "@react-oauth/google";

import { useAuth } from "../auth";

/**
 * Google Sign-In button. Rendered only when a Google OAuth client ID is
 * configured (VITE_GOOGLE_CLIENT_ID); otherwise the caller hides it entirely.
 *
 * On success the Google-issued ID token (`credential`) is exchanged with the
 * backend for our JWT session (access token in memory, refresh in the
 * HttpOnly cookie), exactly like password login.
 */
export default function GoogleSignInButton({
  onSuccess,
  onError,
}: {
  onSuccess: () => void;
  onError: (message: string) => void;
}) {
  const { loginWithGoogle } = useAuth();

  const handleSuccess = async (response: CredentialResponse) => {
    const credential = response.credential;
    if (!credential) {
      onError("Google did not return a credential.");
      return;
    }
    try {
      await loginWithGoogle(credential);
      onSuccess();
    } catch {
      onError("Could not sign in with Google. Please try again.");
    }
  };

  return (
    <div className="flex justify-center">
      <GoogleLogin
        onSuccess={handleSuccess}
        onError={() => onError("Google Sign-In failed. Please try again.")}
        useOneTap={false}
        theme="outline"
        size="large"
        width="100%"
      />
    </div>
  );
}
