"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { clearTokens, getAccessToken } from "@/lib/auth";
import type { User } from "@/lib/types";
import { AmbientBg } from "@/components/app-shell/ambient-bg";
import { Sidebar } from "@/components/app-shell/sidebar";
import { CommandPaletteProvider } from "@/components/command-palette";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }
    apiFetch<User>("/auth/me")
      .then((u) => {
        setUser(u);
        setReady(true);
      })
      .catch(() => {
        clearTokens();
        router.replace("/login");
      });
  }, [router]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#050508] text-sm text-white/50">
        Chargement…
      </div>
    );
  }

  return (
    <CommandPaletteProvider>
      <div className="raijin-shell relative flex h-screen overflow-hidden">
        <AmbientBg />
        <div className="relative z-10 flex h-screen w-full">
          <Sidebar user={user} />
          <main className="raijin-scroll relative flex-1 overflow-y-auto px-7 pb-10 pt-7">
            {children}
          </main>
        </div>
      </div>
    </CommandPaletteProvider>
  );
}
