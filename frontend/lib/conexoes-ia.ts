/**
 * Conexões de IA: o Claude (ou outro cliente) lendo a loja do vendedor pelo MCP.
 *
 * Quem autoriza e guarda a conexão é o servidor OAuth do Supabase; quem trava
 * o dado é o backend (`backend/mcp_conta.py`). Aqui só o que as duas telas
 * (consentimento e Segurança) precisam decidir e mostrar. Spec:
 * docs/specs/2026-11-09-premium-mcp-conta-real-design.md.
 */

/** O endereço que o vendedor cola no Claude para conectar a própria loja. */
export const ENDERECO_DO_MCP = "https://api.usesellerpulse.com/mcp/conta";

/** O plano deixa autorizar? Sem resposta do acesso, não: o servidor recusaria. */
export function podeConectarIa(recursos: readonly string[] | null | undefined): boolean {
  return recursos?.includes("mcp-conta") ?? false;
}

/** O nome que o cliente deu ao se registrar, que pode vir vazio. */
export function nomeDoCliente(nome: string | null | undefined): string {
  return nome?.trim() || "Aplicativo sem nome";
}

/** Data da autorização no dia do vendedor (Brasília), e não em UTC. */
export function dataDaAutorizacao(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(iso));
}
