"use client";

import { useEffect } from "react";

import { installFrontendErrorReporting } from "@/lib/sentry-lite";

export function ErrorReporter() {
  useEffect(() => {
    installFrontendErrorReporting();
  }, []);

  return null;
}
