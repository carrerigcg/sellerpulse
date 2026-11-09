# Premium: sincronização a cada 6 horas

Estado: no ar desde 2026-11-06 (#53, `e8602ad`). Item 2 das funções do
Premium. Medido em 2026-11-09 (aba Actions, 7 a 9/11): o cron do GitHub não
cumpre as 4 rodadas. A das 03 UTC não rodou nenhuma vez, e as outras atrasaram
de 0,8 a 4,5 horas; na prática o Premium sincronizou 3 vezes por dia, com
intervalo de até 10,5 horas. Trocar o gatilho é decisão pendente.

## O pedido

O Guilherme escolheu, em 2026-11-06, a opção 2.1: o Premium sincroniza sozinho
a cada 6 horas, e os outros planos continuam com uma vez por dia.

## Como era

- O GitHub Actions (`sincronizacao-agendada.yml`) chamava `POST /ml/sync-todos`
  uma vez por dia, às 06:00 de São Paulo.
- O endpoint pulava quem tinha sincronizado havia menos de 6 horas
  (`LIMIAR_DELTA`, o mesmo do login).

## Decisões travadas

1. **O agendador roda 4 vezes por dia**, às 00:00, 06:00, 12:00 e 18:00 de São
   Paulo. A das 06:00 continua lá, antes do expediente.
2. **Quem decide quem sincroniza em cada rodada é o plano**, em
   `backend/planos.py`: `horas_entre_syncs` = 6 no Premium e 24 nos outros. O
   YAML não sabe de plano nenhum (`_hora_de_sincronizar` em
   `backend/routers/ml.py`).
3. **Premium: em cada rodada, com folga de 1 hora.** O `last_synced_at` é
   gravado no fim do job, e o cron do GitHub atrasa minutos. Com limiar de 6
   horas exatas, a rodada seguinte veria 5h50 e pularia o Premium, que na
   prática sincronizaria a cada 12 horas.
4. **Planos diários: só na rodada da manhã** (das 06:00 às 11:59 em São Paulo,
   para absorver o atraso do cron), com o limiar de 6 horas do login para não
   repetir quem acabou de sincronizar. Um limiar de 23 horas faria o horário
   escorregar para a primeira rodada depois do último sync (um backfill às
   14:00 fixaria as 18:00) e não voltar. Achado do `revisor-de-codigo`.
5. **As visitas são colhidas uma vez por dia**, também no Premium. Visita
   existe por dia, e cada colheita custa uma chamada ao ML por item (1.118
   itens na loja real, cerca de 10 minutos). Nas rodadas de dentro do dia, a
   cadeia vai do delta direto para o frete quando houve colheita há menos de
   20 horas. Medido pelo `auditor-de-escala`: sem isso, o Premium passaria de
   cerca de 1.100 para 4.470 chamadas por dia.
6. **O limiar do login e do botão não muda** (6 horas, `LIMIAR_DELTA`).
7. **O passo que mantém o serviço acordado continua em cada rodada**: com os
   ~15 minutos até hibernar, são cerca de 50 horas por mês das 750 do Render
   gratuito.

## Limite conhecido

A fila é serial. Com muitos vendedores, o delta de quem fica no fim da fila
termina mais de 1 hora depois da rodada, e esse Premium passa a sincronizar de
12 em 12 horas sem nada falhar. Hoje há um vendedor só. Resolve-se com o worker
próprio (bloco B da avaliação de escala).

## Fora desta entrega

- Texto da vitrine sobre a frequência: entra com a volta do Premium à venda.
- Worker próprio que agenda a si mesmo (bloco B da avaliação de escala).
