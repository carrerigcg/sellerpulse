import { Suspense } from "react";

import { getAcesso, getDesistencia, getPagamentos } from "@/lib/api";
import { NOMES_DOS_PLANOS, diaDe, ultimoDia } from "@/lib/plano";
import { PRECOS_MENSAIS, formatarPreco, precoAnual } from "@/lib/precos";

import { AcoesDaAssinatura } from "./acoes";
import { CabecalhoSimples } from "./cabecalho";
import { Desistir } from "./desistir";

/**
 * Minha assinatura: o plano, até quando está pago, e trocar ou cancelar.
 *
 * Plano dado à mão (origem `manual`) não tem cobrança no Asaas para mexer: a
 * tela diz isso em vez de mostrar botões que o backend recusaria.
 */
export default async function AssinaturaPage() {
  const acesso = await getAcesso().catch(() => null);

  if (!acesso || !acesso.plano) {
    return (
      <>
        <CabecalhoSimples />
        <p className="mt-8 rounded-lg bg-negative/10 px-4 py-3 text-sm text-negative">
          Não foi possível carregar a sua assinatura agora. Tente de novo em instantes.
        </p>
      </>
    );
  }

  const assinatura = acesso.assinatura;
  const plano = acesso.plano;
  // `pago_ate` e `acesso_ate` são a meia-noite em que o prazo ACABA. A próxima
  // cobrança cai nesse dia; "pago até" e "vale até" são o dia anterior.
  const cancelada = assinatura?.cancelada === true;
  const proximaCobranca =
    assinatura?.recorrente && assinatura.pago_ate ? diaDe(assinatura.pago_ate) : null;
  const pagoAte =
    !assinatura?.recorrente && assinatura?.pago_ate ? ultimoDia(assinatura.pago_ate) : null;
  const acessoAte = assinatura?.acesso_ate ? ultimoDia(assinatura.acesso_ate) : null;
  const proximoPlano = assinatura?.plano_no_proximo_ciclo ?? null;

  return (
    <>
      <CabecalhoSimples />

      <section className="mt-6 rounded-xl border border-line p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Seu plano</p>
        <p className="mt-1 text-2xl font-semibold">{NOMES_DOS_PLANOS[plano]}</p>

        {assinatura?.origem !== "gateway" ? (
          <p className="mt-2 text-sm text-muted">
            Liberado pela equipe do SellerPulse, sem cobrança automática.
          </p>
        ) : (
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">Pagamento</dt>
              <dd className="font-medium">
                {assinatura.ciclo === "anual"
                  ? `${formatarPreco(precoAnual(plano))} por ano`
                  : `${formatarPreco(PRECOS_MENSAIS[proximoPlano ?? plano])} por mês, no cartão`}
              </dd>
            </div>
            {proximaCobranca && (
              <div>
                <dt className="text-muted">Próxima cobrança</dt>
                <dd className="font-medium">{proximaCobranca}</dd>
              </div>
            )}
            {pagoAte && !cancelada && (
              <div>
                <dt className="text-muted">Pago até</dt>
                <dd className="font-medium">{pagoAte}</dd>
              </div>
            )}
            {assinatura.plano_no_proximo_ciclo && (
              <div className="sm:col-span-2">
                <dt className="text-muted">Troca agendada</dt>
                <dd className="font-medium">
                  Passa para o {NOMES_DOS_PLANOS[assinatura.plano_no_proximo_ciclo]} na próxima
                  cobrança.
                </dd>
              </div>
            )}
            {cancelada && acessoAte && (
              <div className="sm:col-span-2">
                <dt className="text-muted">Cancelada</dt>
                <dd className="font-medium">O acesso vale até {acessoAte}.</dd>
              </div>
            )}
          </dl>
        )}
      </section>

      {assinatura?.origem === "gateway" && (
        // Em Suspense: a consulta ao Asaas não segura o resto da tela.
        <Suspense fallback={null}>
          <SecaoDeDesistencia />
        </Suspense>
      )}
      {assinatura?.origem === "gateway" && assinatura.recorrente && (
        <AcoesDaAssinatura plano={plano} proximoPlano={proximoPlano} />
      )}
      {assinatura?.origem === "gateway" && assinatura.ciclo === "anual" && (
        <p className="mt-6 text-sm text-muted">
          O plano anual não renova sozinho. Quando ele terminar, você contrata de novo pela
          página de planos.
        </p>
      )}
      {assinatura?.origem === "gateway" && (
        <Suspense fallback={null}>
          <SecaoDePagamentos />
        </Suspense>
      )}
    </>
  );
}

/**
 * Os comprovantes, onde o recibo da primeira compra fica: o Asaas não o manda
 * por e-mail, porque o cliente que o checkout cria nasce com os avisos
 * desligados. Se o Asaas não responder, a seção não aparece.
 */
async function SecaoDePagamentos() {
  const resposta = await getPagamentos().catch(() => null);
  if (!resposta || resposta.pagamentos.length === 0) return null;
  return (
    <section className="mt-6 rounded-xl border border-line p-5">
      <h2 className="text-sm font-semibold">Pagamentos</h2>
      <ul className="mt-2 divide-y divide-line text-sm">
        {resposta.pagamentos.map((p) => (
          <li key={p.comprovante} className="flex flex-wrap items-center justify-between gap-x-4 py-1">
            <span>
              {p.dia.split("-").reverse().join("/")} · {formatarPreco(p.valor)}
              {/* Cada valor testado por si: um campo ausente (backend antigo
                  no ar) não pode virar a afirmação de um estorno. */}
              {p.situacao === "devolvido" && <span className="text-muted"> · devolvido</span>}
              {p.situacao === "devolvendo" && (
                <>
                  {" "}
                  <span className="whitespace-nowrap text-muted">· devolução em andamento</span>
                </>
              )}
            </span>
            <a
              href={p.comprovante}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center font-medium text-accent hover:underline"
            >
              Ver comprovante<span className="sr-only"> (abre em nova aba)</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Pergunta ao Asaas se o prazo de desistência está aberto. Se ele não
 * responder, a seção não aparece, e o caminho é o contato, como antes.
 */
async function SecaoDeDesistencia() {
  const desistencia = await getDesistencia().catch(() => null);
  if (!desistencia?.ate) return null;
  return (
    <Desistir
      ate={desistencia.ate.split("-").reverse().join("/")}
      jaDevolvido={desistencia.ja_devolvido === true}
    />
  );
}
