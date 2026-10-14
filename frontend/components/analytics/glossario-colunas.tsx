import type { Coluna } from "@/lib/csv";
import { COLUNAS_ABC, COLUNAS_FLUXO, COLUNAS_RFM } from "@/lib/colunas-export";
import {
  GLOSSARIO_ABC,
  GLOSSARIO_FLUXO,
  GLOSSARIO_RFM,
  NOTA_SOBRE_SCORES,
  type Glossario,
} from "@/lib/glossario";

/**
 * O tutorial e o glossário das colunas.
 *
 * Server Component: é texto estático, e texto estático não precisa de
 * JavaScript no cliente.
 *
 * Os títulos dos verbetes vêm de `colunas-export.ts`, não repetidos aqui. É
 * o mesmo array que o botão usa para montar o cabeçalho do CSV, então o
 * glossário descreve necessariamente o arquivo que a pessoa baixou — e, se
 * uma coluna nova entrar lá sem verbete aqui, o TypeScript recusa a
 * compilação (ver o tipo `Glossario<T>`).
 */

function Bloco<T>({
  titulo,
  colunas,
  glossario,
  nota,
}: {
  titulo: string;
  colunas: readonly Coluna<T>[];
  glossario: Glossario<T>;
  nota?: string;
}) {
  return (
    <section className="mt-6 rounded-xl border border-line p-5">
      <h3 className="text-sm font-semibold">{titulo}</h3>
      <dl className="mt-3 divide-y divide-line">
        {colunas.map((coluna) => (
          <div key={coluna.campo} className="py-3 first:pt-0 last:pb-0 sm:flex sm:gap-5">
            <dt className="shrink-0 text-xs font-medium sm:w-56">{coluna.titulo}</dt>
            <dd className="mt-1 text-xs leading-relaxed text-muted sm:mt-0">
              {glossario[coluna.campo]}
            </dd>
          </div>
        ))}
      </dl>
      {nota && (
        <p className="mt-4 rounded-lg bg-highlight-soft px-3 py-2 text-xs leading-relaxed text-ink">
          {nota}
        </p>
      )}
    </section>
  );
}

export function GlossarioColunas({ demo = false }: { demo?: boolean }) {
  return (
    <>
      <section className="mt-10 rounded-xl border border-line p-5">
        <h2 className="text-sm font-semibold">Como exportar</h2>
        <ol className="mt-3 space-y-3 text-xs leading-relaxed text-muted">
          <li className="flex gap-3">
            <span className="shrink-0 font-medium text-accent">1.</span>
            <span>
              Escolha o período no alto da página e clique em Aplicar. As três tabelas
              passam a cobrir essa janela, e o período entra no nome do arquivo.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="shrink-0 font-medium text-accent">2.</span>
            <span>
              Clique em Baixar no cartão da tabela que você quer, ou em Baixar tudo para
              levar as três. Nada é processado no servidor: o arquivo é montado no seu
              navegador, a partir do que a página já carregou.
            </span>
          </li>
          <li className="flex gap-3">
            <span className="shrink-0 font-medium text-accent">3.</span>
            <span>
              Abra com dois cliques no Excel em português. O arquivo já vem com ponto e
              vírgula separando as colunas, vírgula no decimal e a acentuação correta —
              é o que o Excel brasileiro espera. No Google Sheets, use Arquivo e depois
              Importar, deixando o separador em detecção automática.
            </span>
          </li>
        </ol>
      </section>

      <section className="mt-6 rounded-xl border border-line bg-highlight-soft p-5">
        <h2 className="text-sm font-semibold">Duas coisas sobre o período</h2>
        <p className="mt-2 text-xs leading-relaxed text-ink">
          <strong className="font-medium">O campo Até não entra na conta.</strong>{" "}
          Escolhendo 13/10, o arquivo vai até 12/10. O nome do arquivo guarda a data que
          você escolheu, então ele diz 13/10 e a última linha é do dia anterior. Se for
          conferir um total contra o Mercado Livre, é esse dia de diferença que explica
          a sobra.
        </p>
        <p className="mt-3 text-xs leading-relaxed text-ink">
          <strong className="font-medium">
            Tudo é calculado dentro da janela, não contra a vida inteira da loja.
          </strong>{" "}
          A classe ABC de um produto, os scores de um comprador e a recência saem do
          período escolhido. O mesmo produto pode ser classe A em um mês e B em outro, e
          isso não é defeito: é a pergunta mudando.
        </p>
      </section>

      <h2 className="mt-10 text-sm font-semibold">O que cada coluna significa</h2>
      <p className="mt-1 text-xs text-muted">
        Os nomes abaixo são os mesmos que aparecem na primeira linha da planilha.
        {demo && " Os números são de um vendedor fictício, criado para a demonstração."}
      </p>

      <Bloco titulo="Fluxo financeiro" colunas={COLUNAS_FLUXO} glossario={GLOSSARIO_FLUXO} />
      <Bloco titulo="Produtos" colunas={COLUNAS_ABC} glossario={GLOSSARIO_ABC} />
      <Bloco
        titulo="Clientes"
        colunas={COLUNAS_RFM}
        glossario={GLOSSARIO_RFM}
        nota={NOTA_SOBRE_SCORES}
      />
    </>
  );
}
