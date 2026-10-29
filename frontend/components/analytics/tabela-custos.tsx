"use client";

import { useState } from "react";

import type { CustoLinha } from "@/lib/api";
import { removeCusto, salvaCusto } from "@/lib/custos-client";
import { leValorDigitado } from "@/lib/valor-digitado";

import { abcClassBadgeClass } from "./abc-class-badge";

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const brlExato = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

type Estado = "parado" | "salvando" | "salvo" | "erro";

/**
 * Tabela editável de custo por produto.
 *
 * SALVA POR LINHA, ao sair do campo. Não há botão "salvar tudo": um
 * formulário de 47 linhas que falha inteiro por causa de uma é hostil, e o
 * vendedor que preencheu 30 não deve perder as 30 porque a 31ª tinha um erro
 * de digitação.
 *
 * CAMPO VAZIO SIGNIFICA "NÃO INFORMADO", nunca zero. Zero é uma afirmação —
 * "este produto não me custa nada" — e precisa ser digitada. Esvaziar um
 * campo que tinha valor desfaz o que foi digitado hoje (inclusive o
 * retroativo de hoje), e só: o custo de ontem continua valendo para os
 * pedidos de ontem.
 *
 * A ordem vem do servidor (receita decrescente, que é "classe A primeiro") e
 * não é reordenada aqui: é a ordem em que preencher muda mais a conta.
 */
export function TabelaCustos({
  linhas,
  somenteLeitura = false,
}: {
  linhas: CustoLinha[];
  /**
   * `true` na demonstração: ela não tem usuário para escrever, e não existe
   * `PUT /demo/custos`. Um campo editável que sempre falha ao salvar seria
   * pior que nenhum campo.
   */
  somenteLeitura?: boolean;
}) {
  // Estado por SKU. Um `useState` por linha exigiria um componente por linha;
  // um mapa só mantém o componente simples e a linha independente.
  const [estados, setEstados] = useState<Record<string, Estado>>({});
  const [erros, setErros] = useState<Record<string, string>>({});
  const [valores, setValores] = useState<Record<string, number | null>>(() =>
    Object.fromEntries(linhas.map((l) => [l.sku, l.custo_unitario])),
  );
  // Ligada por padrão: quem chega com seis meses de histórico quer ver o
  // passado com custo, e marcar produto por produto não serve para centenas
  // deles. Só preenche o que está sem custo — nunca reescreve um período
  // informado (docs/specs/2026-10-28-custo-retroativo-design.md).
  const [retroativo, setRetroativo] = useState(true);
  const [salvoNoHistorico, setSalvoNoHistorico] = useState<Record<string, boolean>>({});

  function marca(sku: string, estado: Estado, erro?: string) {
    setEstados((anterior) => ({ ...anterior, [sku]: estado }));
    setErros((anterior) => ({ ...anterior, [sku]: erro ?? "" }));
  }

  async function aoSair(linha: CustoLinha, texto: string) {
    const lido = leValorDigitado(texto);

    if (lido === undefined) {
      marca(linha.sku, "erro", "Não entendi esse valor.");
      return;
    }
    // Nada mudou: não gasta requisição nem pisca "salvo" sem motivo.
    if (lido === (valores[linha.sku] ?? null)) {
      marca(linha.sku, "parado");
      return;
    }

    marca(linha.sku, "salvando");
    try {
      if (lido === null) {
        await removeCusto(linha.sku);
      } else {
        await salvaCusto(linha.sku, lido, retroativo);
      }
      setValores((anterior) => ({ ...anterior, [linha.sku]: lido }));
      setSalvoNoHistorico((anterior) => ({ ...anterior, [linha.sku]: lido !== null && retroativo }));
      marca(linha.sku, "salvo");
    } catch (e) {
      marca(linha.sku, "erro", e instanceof Error ? e.message : "Não foi possível salvar.");
    }
  }

  return (
    <div>
      {!somenteLeitura && (
        <label className="mb-4 flex items-start gap-2.5 rounded-lg border border-line px-3 py-2.5 text-sm">
          <input
            type="checkbox"
            checked={retroativo}
            onChange={(e) => setRetroativo(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
          />
          <span>
            <span className="font-medium">Aplicar também às vendas anteriores sem custo</span>
            <span className="block text-xs text-muted">
              O custo salvo passa a valer para as vendas que ainda não têm custo. Um período em que você
              já informou um custo nunca é alterado.
            </span>
          </span>
        </label>
      )}
    <div className="overflow-x-auto">
      <table className="w-full min-w-[42rem] text-left text-sm">
        <thead className="text-xs text-muted">
          <tr className="border-b border-line">
            <th className="py-2 pr-3 font-medium">Classe</th>
            <th className="py-2 pr-3 font-medium">Produto</th>
            <th className="py-2 pr-3 text-right font-medium">Receita</th>
            <th className="py-2 pr-3 text-right font-medium">Unidades</th>
            <th className="py-2 text-right font-medium">Custo unitário</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((linha) => {
            const estado = estados[linha.sku] ?? "parado";
            return (
              <tr key={linha.sku} className="border-b border-line/60 last:border-0">
                <td className="py-2.5 pr-3">
                  <span className={abcClassBadgeClass(linha.classe)}>{linha.classe}</span>
                </td>
                <td className="py-2.5 pr-3">
                  <span className="block max-w-[22rem] truncate" title={linha.titulo}>
                    {linha.titulo}
                  </span>
                  <span className="text-xs text-muted">{linha.sku}</span>
                </td>
                <td className="py-2.5 pr-3 text-right tabular">{brl.format(linha.receita)}</td>
                <td className="py-2.5 pr-3 text-right tabular">{linha.unidades}</td>
                <td className="py-2.5 text-right">
                  {somenteLeitura ? (
                    <span className="tabular">
                      {linha.custo_unitario === null ? (
                        <span className="text-muted">não informado</span>
                      ) : (
                        brlExato.format(linha.custo_unitario)
                      )}
                    </span>
                  ) : (
                    <>
                  <div className="flex items-center justify-end gap-2">
                    {estado === "salvando" && <span className="text-xs text-muted">salvando…</span>}
                    {estado === "salvo" && <span className="text-xs text-positive">salvo</span>}
                    <input
                      type="text"
                      inputMode="decimal"
                      defaultValue={
                        linha.custo_unitario === null ? "" : brlExato.format(linha.custo_unitario)
                      }
                      // Placeholder vazio de propósito: um "0,00" cinza ali
                      // sugere que o padrão é zero, e o padrão é "não sei".
                      placeholder="—"
                      aria-label={`Custo unitário de ${linha.titulo}`}
                      onBlur={(e) => aoSair(linha, e.target.value)}
                      onFocus={() => marca(linha.sku, "parado")}
                      className={`w-28 rounded-lg border px-2.5 py-1.5 text-right text-sm tabular outline-none focus:border-accent ${
                        estado === "erro" ? "border-negative" : "border-line"
                      }`}
                    />
                  </div>
                  {estado === "erro" && (
                    <p className="mt-1 text-xs text-negative">{erros[linha.sku]}</p>
                  )}
                  {/* No momento de salvar, e não depois: um retroativo errado
                      só se corrige no mesmo dia, então é agora que precisa
                      aparecer. */}
                  {estado === "salvo" && salvoNoHistorico[linha.sku] && (
                    <p className="mt-1 text-xs text-muted">também nas vendas anteriores sem custo</p>
                  )}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    </div>
  );
}
