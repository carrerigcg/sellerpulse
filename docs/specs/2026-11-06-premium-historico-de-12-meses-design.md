# Premium: histórico de 12 meses

Estado: mergeado em 2026-11-06 (#52), no ar no Render (`0e0c4cd`). A primeira
busca de 12 meses da loja real roda no delta seguinte; o tempo dela ainda não
foi medido. Item 1 da
etapa 11 (funções do Premium) de `docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`.

## O pedido

O Guilherme pediu, em 2026-11-06, as funções que diferenciam o Premium. Esta é a
primeira: o histórico de 12 meses que a vitrine promete. Decisões dele:

- **1.1:** ao virar Premium, o sistema busca sozinho os meses que faltam, em
  segundo plano, e a tela avisa enquanto não termina.
- **Corte em 12 meses**, como o Exclusive corta em 6. Sem corte, o Premium
  mostraria mais do que vende.

## O que se mediu (2026-11-06, leitura com o token da loja real, com ok dele)

- O `/orders/search` do ML devolve pedidos de **exatamente 12 meses** para trás.
  O mais antigo devolvido foi de 2025-11-06, o dia de hoje um ano antes. Antes
  disso, zero em todas as janelas de 30 dias até 24 meses atrás.
- A loja tem 1.704 pedidos nesses 12 meses; o banco tem 1.359, desde 2026-04-03.
  Faltam uns 345.
- Consequência: 12 meses é o máximo que se busca. Depois disso, o histórico se
  mantém só porque o banco guarda o que já veio.

## Decisões travadas

1. **`dias_de_historico` do Premium passa a 365.** O corte usa o mesmo
   `limita_ao_historico` dos outros planos.
2. **O backfill busca o que o plano mostra, com piso de 180 dias:**
   `dias_de_ingestao = max(180, dias_de_historico)`. O Essencial continua
   buscando 180 (já é assim): quem sobe para o Exclusive tem os 6 meses na hora.
   O Premium busca 365.
3. **Janelas de 30 dias, a última menor**, para fechar 365 sem pedir além do
   que o ML guarda. O cursor do job grava os `dias` no início: a retomada usa
   as mesmas janelas, mesmo que o plano mude no meio.
4. **Quanto já foi buscado é derivado da fila, sem coluna nova:** o maior
   `dias` entre os backfills concluídos do vendedor. Backfill antigo, sem
   `dias` no cursor, conta como 180, que é o que ele buscou. Assim não há
   migration.
5. **Quem dispara a busca é o delta.** Ao terminar, se o plano pede mais do que
   já foi buscado, o delta encadeia um backfill em vez das visitas, e o
   backfill encadeia as visitas como hoje. Isso cobre todos os caminhos que
   viram Premium (pagamento, troca, plano dado à mão) sem tocar em nenhum
   deles, e roda já na próxima sincronização.
   - O backfill refaz os 6 meses que já existem. O upsert é idempotente, e o
     custo medido é baixo: os pedidos vêm em páginas de 50, e os itens já estão
     no cache. Buscar só a metade antiga pediria um tipo de job novo, e com ele
     uma migration na constraint da fila.
6. **Enquanto a busca não termina, a tela mostra o que existe e diz por quê.**
   O histórico visível é `min(plano, já buscado)`, e não o do plano: mostrar 12
   meses com 6 buscados exibiria os 6 antigos como venda zero. Ausência não é
   zero. O `GET /conta/acesso` devolve esse número e `historico_buscando`, e o
   aviso de corte troca a frase do plano por "Ainda buscando no Mercado Livre
   os meses mais antigos".
   - Antes do primeiro backfill (loja recém-conectada) nada muda: a tela de
     conexão já mostra o progresso.
   - O corte efetivo é aplicado num lugar só, o `get_acesso`, que entrega aos
     routers o plano com os dias efetivos. Só o plano que mostra além de 180
     dias consulta a fila; os outros nem a leem.
7. **O teto de largura de janela (`MAX_JANELA_DIAS`) passa a 2 × 365.** Ele era
   2 × 180 = 360, e recusaria um pedido de 12 meses do Premium.

8. **Backfill que falhou há menos de 7 dias não é refeito pelo delta.** Com um
   erro persistente, cada delta trocaria as visitas por um backfill que morre,
   e o ML só guarda 150 dias de visitas. Passado o prazo, tenta de novo.

## Fora desta entrega

- **Visitas:** o ML entrega no máximo `MLClient.MAX_DIAS_DE_VISITAS` dias. Nos
  meses mais antigos, a conversão aparece com a cobertura parcial que já existe.
- **Volta do Premium à venda** (`a_venda`): só quando as outras funções
  existirem.
- **Antes da volta à venda (da auditoria de escala, 2026-11-06):**
  - feito (migration 0024): índice parcial `sync_jobs(seller_id) where kind =
    'backfill' and status = 'done'`. Sem ele, `dias_ja_buscados` lê a fila inteira: medido em 26 ms com
    300 vendedores e 1 ano de jobs, contra 0,18 ms com o índice. Hoje a fila
    tem 59 linhas.
  - medido em 2026-11-09: o backfill de 365 dias da loja real levou 13,2
    minutos (job de 2026-11-07), contra a estimativa de 7 a 12.
  - o aviso aparece desde a troca de plano, mas a busca começa no delta
    seguinte (até um dia depois).
- **Texto da vitrine e dos termos** sobre os 12 meses: entra com a volta à
  venda.
