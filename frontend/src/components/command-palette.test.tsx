import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  CommandPaletteProvider,
  useCommandPalette,
} from "./command-palette";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

function OpenButton() {
  const palette = useCommandPalette();
  return <button onClick={palette.open}>Open palette</button>;
}

describe("CommandPalette", () => {
  beforeEach(() => {
    push.mockReset();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ invoices: [], suppliers: [] }), {
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  });

  it("opens from context and filters navigation items", () => {
    render(
      <CommandPaletteProvider>
        <OpenButton />
      </CommandPaletteProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open palette" }));
    expect(screen.getByPlaceholderText("Rechercher une facture, un fournisseur, une page…")).toBeVisible();

    fireEvent.change(screen.getByPlaceholderText("Rechercher une facture, un fournisseur, une page…"), {
      target: { value: "four" },
    });

    expect(screen.getByRole("button", { name: /Fournisseurs/ })).toBeVisible();
    expect(screen.queryByRole("button", { name: /Tableau de bord/ })).not.toBeInTheDocument();
  });

  it("opens with keyboard shortcut and navigates with enter", () => {
    render(
      <CommandPaletteProvider>
        <div>App</div>
      </CommandPaletteProvider>,
    );

    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByPlaceholderText("Rechercher une facture, un fournisseur, une page…")).toBeVisible();

    fireEvent.keyDown(window, { key: "Enter" });

    expect(push).toHaveBeenCalledWith("/dashboard");
  });
});
