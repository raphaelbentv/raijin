import { AmbientBg } from "@/components/app-shell/ambient-bg";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="raijin-shell relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      <AmbientBg />
      <div className="relative z-10 w-full max-w-md">{children}</div>
    </div>
  );
}
