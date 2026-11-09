/**
 * Várias contas do Mercado Livre num login só (Premium, até 3). Spec
 * `docs/specs/2026-11-06-premium-varias-contas-design.md`.
 *
 * A conta aberta mora num cookie e vai para o backend no cabeçalho `X-Conta`.
 * Quem confere que a conta é do usuário, e que o plano a abre, é o backend: o
 * cookie é só a escolha da tela.
 */

export const COOKIE_DA_CONTA = "sp_conta";
export const CABECALHO_DA_CONTA = "X-Conta";

export type ContaML = {
  id: string;
  /** O apelido no Mercado Livre. `null` = conta ainda não conectada. */
  apelido: string | null;
  principal: boolean;
  /** Abre neste plano. A extra fora do Premium não abre, mas os dados ficam. */
  ativa: boolean;
};

export type Contas = {
  contas: ContaML[];
  conta_aberta: string;
  max_contas: number;
};

/** O cabeçalho da conta escolhida. Sem escolha, nenhum: o backend abre a principal. */
export function cabecalhoDaConta(valor: string | undefined | null): Record<string, string> {
  return valor ? { [CABECALHO_DA_CONTA]: valor } : {};
}

/** O valor de um cookie em `document.cookie`, para os Client Components. */
export function valorDoCookie(cookies: string, nome: string): string | undefined {
  for (const parte of cookies.split(";")) {
    const [chave, ...resto] = parte.trim().split("=");
    if (chave === nome) return decodeURIComponent(resto.join("="));
  }
  return undefined;
}

/** O seletor só aparece com mais de uma conta que abre: com uma, não há o que trocar. */
export function contasDoSeletor(acesso: Contas): ContaML[] {
  const ativas = acesso.contas.filter((c) => c.ativa);
  return ativas.length > 1 ? ativas : [];
}

export function podeAdicionarConta(acesso: Contas): boolean {
  return acesso.max_contas > 1 && acesso.contas.length < acesso.max_contas;
}

/**
 * Quantas contas o plano abre. Fora do Premium, as extras ficam guardadas
 * (decisão 2.1): "2 de 1" não diria isso.
 */
export function fraseDasContas(acesso: Contas): string {
  const n = acesso.contas.length;
  if (n > acesso.max_contas) {
    return "Seu plano atual abre só a conta principal. As outras ficam guardadas: voltam a abrir no Premium, ou podem ser removidas aqui.";
  }
  const vaga = `${n} de ${acesso.max_contas} contas no seu plano.`;
  // Com uma conta só não há seletor no topo: mandar trocar lá apontaria para nada.
  return contasDoSeletor(acesso).length > 0
    ? `${vaga} Troque a conta aberta no topo do painel.`
    : vaga;
}

export function nomeDaConta(conta: ContaML): string {
  const nome = conta.apelido ?? "Conta sem conexão";
  return conta.principal ? `${nome} (principal)` : nome;
}
