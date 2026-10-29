/**
 * O acesso do vendedor, como o backend o descreve em `GET /conta/acesso`.
 *
 * Quem decide o que cada plano libera é o backend (`backend/planos.py`), e é
 * ele que trava os dados. Aqui só se lê a resposta para saber o que desenhar
 * com cadeado. Desenho em `docs/specs/2026-10-28-planos-e-acesso-design.md`.
 */

export type Recurso =
  | "abc-completa"
  | "desempenho-anuncios"
  | "clientes"
  | "cohort"
  | "exportar"
  | "sync-sob-demanda";

export type NomeDoPlano = "essencial" | "exclusive" | "premium";

export type Acesso = {
  plano: NomeDoPlano | null;
  recursos: Recurso[];
  /** `null` = sem limite além do que a ingestão trouxe. */
  dias_de_historico: number | null;
  produtos_na_abc: number | null;
  termos: { versao: string; aceito: boolean };
};

export function libera(acesso: Acesso, recurso: Recurso): boolean {
  return acesso.recursos.includes(recurso);
}

/** Para onde o layout do painel manda quem ainda não pode entrar nele. */
export function destinoSemAcesso(acesso: Acesso): "/planos" | "/aceite" | null {
  if (acesso.plano === null) return "/planos";
  if (!acesso.termos.aceito) return "/aceite";
  return null;
}

/**
 * O primeiro dia que o plano mostra, ou `null` se ele mostra tudo.
 *
 * Mesma conta do backend (`limita_ao_historico`): `hoje` menos os dias do
 * plano, no dia do vendedor. `hoje` é o "hoje" no fuso do vendedor, em
 * AAAA-MM-DD — o mesmo que `hojeNoFusoDoVendedor` devolve.
 */
export function inicioDoHistorico(acesso: Acesso, hoje: string): string | null {
  if (acesso.dias_de_historico === null) return null;
  const dia = new Date(`${hoje}T00:00:00Z`);
  dia.setUTCDate(dia.getUTCDate() - acesso.dias_de_historico);
  return dia.toISOString().slice(0, 10);
}

/** O período pedido começa antes do que o plano mostra? */
export function historicoCortado(acesso: Acesso, de: string, hoje: string): boolean {
  const inicio = inicioDoHistorico(acesso, hoje);
  return inicio !== null && de < inicio;
}

export const NOMES_DOS_PLANOS: Record<NomeDoPlano, string> = {
  essencial: "Essencial",
  exclusive: "Exclusive",
  premium: "Premium",
};

/**
 * Pode desenhar o recurso aberto? Sem resposta do acesso (backend fora do
 * ar), sim: quem trava os dados é o backend, e um cadeado por falha de rede
 * diria ao vendedor que o plano dele não cobre o que cobre.
 */
export function podeUsar(acesso: Acesso | null, recurso: Recurso): boolean {
  return acesso === null || libera(acesso, recurso);
}

/**
 * Dá para comparar com o período anterior? Só se ele couber INTEIRO no que o
 * plano mostra. Um anterior cortado pelo histórico teria menos dias que o
 * atual, e a variação sairia inflada ("+81%" com a venda estável): pior que
 * não comparar.
 */
export function comparaComAnterior(acesso: Acesso | null, anteriorDe: string, hoje: string): boolean {
  return acesso === null || !historicoCortado(acesso, anteriorDe, hoje);
}
