"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Wordmark } from "@/components/brand";

/**
 * Casca das telas de autenticação: formulário à esquerda, painel à direita.
 *
 * O painel usa laranja muito diluído (--sp-accent-soft) em vez de laranja
 * cheio. Meia tela preenchida com a cor saturada cansaria — o destaque forte
 * fica reservado a áreas pequenas (marca, botão, link, um trecho do título).
 *
 * Abaixo de `lg` o painel some e o formulário centraliza: num celular, meia
 * tela de conteúdo decorativo empurraria o formulário pra fora da dobra.
 */
export function AuthShell({
  children,
  panel,
}: {
  children: ReactNode;
  panel: ReactNode;
}) {
  return (
    <main className="flex min-h-screen">
      <div className="flex w-full flex-col justify-center px-6 py-12 lg:w-1/2 lg:px-16">
        <div className="mx-auto w-full max-w-sm">
          <Link href="/" className="inline-block">
            <Wordmark className="text-xl" />
          </Link>
          {children}
        </div>
      </div>

      <aside className="hidden w-1/2 flex-col justify-center bg-accent-soft px-16 lg:flex">
        <div className="max-w-md">{panel}</div>
      </aside>
    </main>
  );
}

export function PageTitle({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <>
      <h1 className="mt-10 text-3xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-sm text-muted">{subtitle}</p>
    </>
  );
}

export function TextField({
  id,
  label,
  type,
  autoComplete,
  value,
  onChange,
  minLength,
  hint,
}: {
  id: string;
  label: string;
  type: string;
  autoComplete: string;
  value: string;
  onChange: (v: string) => void;
  minLength?: number;
  hint?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        type={type}
        autoComplete={autoComplete}
        required
        minLength={minLength}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 w-full rounded-lg border border-line px-3 py-2.5 text-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20"
      />
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function PrimaryButton({
  children,
  disabled,
}: {
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function Alert({ tone, children }: { tone: "erro" | "ok"; children: ReactNode }) {
  const classes =
    tone === "erro"
      ? "bg-negative/10 text-negative"
      : "bg-positive/10 text-positive";
  return (
    <p role="alert" className={`rounded-lg px-3 py-2 text-sm ${classes}`}>
      {children}
    </p>
  );
}

export function Divider({ label }: { label: string }) {
  return (
    <div className="my-6 flex items-center gap-3">
      <span className="h-px flex-1 bg-line" />
      <span className="text-xs text-muted">{label}</span>
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}

export function GoogleButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-center justify-center gap-2 rounded-lg border border-line px-4 py-2.5 text-sm font-medium transition hover:bg-surface disabled:opacity-60"
    >
      <GoogleIcon />
      {children}
    </button>
  );
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.65l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.11a6.6 6.6 0 0 1 0-4.22V7.05H2.18a11 11 0 0 0 0 9.9l3.66-2.84z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 1.46 14.97.5 12 .5A11 11 0 0 0 2.18 7.05l3.66 2.84c.87-2.6 3.3-4.14 6.16-4.14z"
      />
    </svg>
  );
}
