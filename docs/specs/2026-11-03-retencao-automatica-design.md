# Retenção automática

Estado: código no ar desde 2026-11-03 (#42). Desligado até `RETENCAO_IN_PROCESS=1` no Render. Etapa 8 de `docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`.

## Por quê

A Política (seção 7) promete prazos que nada cumpria: credencial do Mercado Livre apagada
30 dias depois do fim do plano, dados da loja guardados por até 12 meses sem plano, registro
de acesso por 6 meses e a prova de conta excluída por 5 anos.

## Decisões

- **Uma rotina diária no processo da API**, no boot e a cada 24 horas, sem agendador nem
  custo novo (o worker já mora ali pelo mesmo motivo).
- **Opt-in por `RETENCAO_IN_PROCESS=1`**, como o refresh da demo: a rotina apaga, e o
  default desligado é a falha barata.
- **"Fim do plano" é `assinaturas.acesso_ate`**, que para quem cancelou já é o fim do
  período pago. Plano dado à mão (`acesso_ate` nulo) e a demonstração não vencem.
- **Aos 12 meses sai o dado da loja, não a conta.** Quem voltar reconecta, e a marca
  d'água volta a nulo para a ingestão inicial trazer o histórico de novo.
- **Sem a credencial, a conta volta a "não conectada"** (`ml_seller_id` nulo), para a tela
  oferecer a conexão e o worker não tentar sincronizar sem token.
- **Uma transação por etapa**, e a lista de vencidos trava a linha da assinatura: um
  pagamento que chegue no meio da limpeza espera e não perde os dados.
- **Lista fechada do que sai e do que fica**, com um teste que cai quando uma tabela nova
  com `seller_id` não entra em nenhuma das duas.
- **Prova de conta excluída sai aos 5 anos**, contados de `contas_excluidas.excluida_em`.
- **Eventos do Asaas saem aos 5 anos do recebimento** (`recebido_em`): são os "registros
  da cobrança" que a Política guarda por 5 anos. O evento não tem `seller_id`, então o
  prazo é o mesmo para todos, com ou sem conta.

## Medido em produção (2026-11-03)

Nenhuma conta seria afetada hoje: a única com plano vencendo termina em 06/11/2026 e não tem
credencial nem pedidos; a conta do dono tem plano manual.

## Fora desta spec

- Cópias de segurança: o Supabase Free não tem, e o backup ficou para depois.
