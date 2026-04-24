"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { setTokens } from "@/lib/auth";

export default function SamlCompletePage() {
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    const access = params.get("access_token");
    const refresh = params.get("refresh_token");
    if (access && refresh) {
      setTokens(access, refresh);
      router.replace("/dashboard");
    } else {
      router.replace("/login?error=saml_failed");
    }
  }, [params, router]);

  return (
    <div className="glass p-8 text-center text-white/70" style={{ borderRadius: 22 }}>
      Connexion SSO en cours…
    </div>
  );
}
