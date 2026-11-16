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

export type SituacaoDoPlano = "liberado" | "fora-do-plano" | "sem-resposta";

/**
 * O plano deixa autorizar? `null` é "o servidor não respondeu" (fora,
 * acordando), e não "fora do plano": quem não tem plano recebe a lista vazia.
 * Sem resposta, a tela não autoriza nem recusa: pede para tentar de novo.
 */
export function situacaoDoPlano(recursos: readonly string[] | null | undefined): SituacaoDoPlano {
  if (recursos == null) return "sem-resposta";
  return recursos.includes("mcp-conta") ? "liberado" : "fora-do-plano";
}

// Para onde o acesso vai depois de autorizar. Quem registra o cliente escolhe
// o nome ("Claude") e o endereço de retorno; é o retorno que diz quem recebe
// o acesso. Um aplicativo no próprio computador (Claude Desktop, Claude Code)
// volta por localhost, que alguém de fora não recebe.
const RETORNOS_CONHECIDOS = ["claude.ai", "claude.com", "chatgpt.com", "openai.com"];
const LOCAIS = ["localhost", "127.0.0.1", "[::1]"];

export function destinoDoRetorno(uri: string): { host: string | null; conhecido: boolean } {
  let host: string;
  try {
    host = new URL(uri).hostname;
  } catch {
    return { host: null, conhecido: false };
  }
  const conhecido =
    LOCAIS.includes(host) ||
    RETORNOS_CONHECIDOS.some((dominio) => host === dominio || host.endsWith(`.${dominio}`));
  return { host, conhecido };
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
