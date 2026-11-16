import { ConexoesDeIa } from "./conexoes-ia";
import { ContatoEDuasEtapas } from "./conta";

/**
 * Conta e segurança: o telefone de contato, a verificação em duas etapas e as
 * conexões de IA.
 *
 * Tudo mora no Supabase Auth (metadados do usuário e fatores TOTP), então a
 * tela é cliente: lê e grava direto pela sessão, sem passar pelo backend.
 */
export default function SegurancaPage() {
  return (
    <>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Conta e segurança</h1>
        <p className="mt-1 text-sm text-muted">
          O seu telefone de contato, a verificação em duas etapas ao entrar e as conexões
          de IA.
        </p>
      </header>
      <ContatoEDuasEtapas />
      <ConexoesDeIa />
    </>
  );
}
