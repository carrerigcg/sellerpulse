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
/** O valor do cookie e do cabeçalho que pede a visão que soma as contas (Premium). */
export const TODAS_AS_CONTAS = "todas";

export type ContaML = {
  id: string;
  /** O apelido no Mercado Livre. `null` = conta ainda não conectada. */
  apelido: string | null;
  principal: boolean;
  /** Abre neste plano. A extra fora do Premium não abre, mas os dados ficam. */
  ativa: boolean;
  /** Fim da última sincronização (ISO), ou `null` se nunca sincronizou. */
  sincronizada_em: string | null;
  /** A primeira importação do histórico terminou. */
  importacao_completa: boolean;
};

export type Contas = {
  contas: ContaML[];
  /** O id da conta aberta, ou `TODAS_AS_CONTAS` na visão somada. */
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

export type OpcaoDeConta = { valor: string; rotulo: string; principal: boolean };

/**
 * As opções do seletor do topo: as contas que abrem e, por último, a soma
 * delas. Com uma conta só não há o que trocar nem o que somar.
 */
export function opcoesDoSeletor(acesso: Contas): OpcaoDeConta[] {
  const contas = contasDoSeletor(acesso);
  if (contas.length === 0) return [];
  return [
    ...contas.map((c) => ({ valor: c.id, rotulo: nomeDaConta(c), principal: c.principal })),
    { valor: TODAS_AS_CONTAS, rotulo: "Todas as contas (soma)", principal: false },
  ];
}

/** O Premium sincroniza a cada 6 horas: parada há 12, já perdeu duas rodadas. */
const HORAS_PARA_AVISAR = 12;

const diaEHora = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/**
 * Na soma, uma conta parada, sem conexão ou ainda importando entra com dias a
 * menos, e a falta pareceria queda de venda. O aviso diz qual conta e desde
 * quando. Fora da soma não avisa: a conta aberta tem a própria tela de
 * conexão. Só as contas que abrem no plano entram, porque só elas são somadas.
 */
export function avisoDaSoma(acesso: Contas, agora: Date): string | null {
  if (!ehVisaoSomada(acesso)) return null;
  const problemas: string[] = [];
  for (const conta of acesso.contas.filter((c) => c.ativa)) {
    if (conta.apelido === null) {
      problemas.push("uma conta está sem conexão");
    } else if (!conta.importacao_completa) {
      problemas.push(`${conta.apelido} ainda está importando o histórico`);
    } else if (conta.sincronizada_em) {
      const em = new Date(conta.sincronizada_em);
      if (agora.getTime() - em.getTime() > HORAS_PARA_AVISAR * 3_600_000) {
        problemas.push(`${conta.apelido} não sincroniza desde ${diaEHora.format(em)}`);
      }
    }
  }
  if (problemas.length === 0) return null;
  return `A soma pode estar incompleta: ${problemas.join("; ")}. Os dias que faltam dessas contas aparecem como dias sem venda.`;
}

export function ehVisaoSomada(acesso: Contas | null): boolean {
  return acesso?.conta_aberta === TODAS_AS_CONTAS;
}

/**
 * Remover uma conta apaga a escolha do painel? Quando a removida era a aberta,
 * e também na soma: com uma conta a menos pode não sobrar seletor, e o
 * vendedor ficaria preso na soma, sem Custos nem Conectar.
 */
export function apagaEscolhaAoRemover(acesso: Contas, id: string): boolean {
  return acesso.conta_aberta === id || acesso.conta_aberta === TODAS_AS_CONTAS;
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
    return "Seu plano atual abre só a conta principal. As outras ficam guardadas: voltam a abrir num plano com várias contas, ou podem ser removidas aqui.";
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
