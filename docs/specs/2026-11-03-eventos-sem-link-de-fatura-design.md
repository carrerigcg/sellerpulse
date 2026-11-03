# Eventos do Asaas sem link de fatura

Estado: no ar desde 2026-11-03 (#41). Os 5 eventos já gravados foram limpos. Etapa 6 de `docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`.

## Por quê

`eventos_do_gateway` guarda o aviso do Asaas para auditar. Os links da fatura, do
comprovante, do boleto e do checkout abrem sem login a página do Asaas com os dados de
quem pagou, e ficavam guardados sem prazo, inclusive depois da exclusão da conta.

## Decisões

- **As chaves saem antes de gravar**, junto com CPF e cartão em `_CHAVES_PESSOAIS`:
  `invoiceUrl`, `transactionReceiptUrl` (também dentro de cada estorno), `bankSlipUrl` e
  `link`. Medido em produção em 2026-11-03: são as únicas chaves com URL de pagamento.
  Os `callback` do checkout ficam, porque são endereços do próprio SellerPulse.
- **Nenhum código lê esses campos do que foi gravado.** O `link` que `/conta/checkout`
  devolve vem da resposta da API, não do log.
- **Os 5 eventos já gravados são limpos pela 0022**, migration de dado como a 0014.

## Fora desta spec

- Prazo de retenção da tabela e a limpeza diária: dependem da etapa 5.
