# Premium: até 3 contas do Mercado Livre

Estado: em implementação, parte A (várias contas, com seletor) na branch
`feat/premium-varias-contas`. A parte B (visão somada) vem num PR seguinte.
Item 5 das funções do Premium.

## O pedido

Quem tem mais de uma conta no Mercado Livre acompanha todas num login só:
até 3 contas, um seletor para trocar entre elas e uma visão que soma as
contas.

## Decisões do Guilherme (2026-11-06)

- **1.1 — A visão somada soma todas as telas, menos Custos e Conectar.**
  Resumo, Financeiro, Produtos, Clientes e Alertas somam as contas. Em
  Clientes, o comprador que comprou em duas contas conta uma vez: o id do
  comprador no ML é o mesmo nas duas. Custos e Conectar são por conta, porque
  cada conta tem os próprios anúncios e a própria credencial.
- **2.1 — Ao sair do Premium, as contas extras param de sincronizar e somem
  do seletor, mas os dados ficam.** Voltando ao Premium, elas voltam sem
  buscar 12 meses de novo. No plano menor só a conta principal funciona.
  Apagar dados continua sendo pelo "Excluir conta" (e pelo "Remover", abaixo).

## Desenho

1. **Várias linhas em `sellers` por usuário.** A migration tira o `UNIQUE`
   de `sellers.user_id` e cria a coluna `principal` (padrão `true`), com um
   índice único parcial: um usuário tem uma principal só. Toda linha que
   existe hoje é principal, e o trigger de cadastro continua criando a
   principal. Todas as tabelas de dado já são por `seller_id`, e as policies
   de RLS já usam `seller_id in (select id from sellers where user_id =
   auth.uid())`, que cobre várias contas sem mudar.
   - Por que não uma tabela nova de contas: todo o dado, a fila e o worker já
     são por `sellers.id`. Uma conta extra é exatamente um seller a mais.
2. **Plano, aceite e cobrança são da conta principal.** `assinaturas`,
   `aceites_de_termos`, `checkouts` e as telas de assinatura continuam presas
   à principal. A conta extra herda o plano dela. As rotas de conta (`/conta/*`)
   seguem com o seller principal, qualquer que seja a conta aberta.
3. **Limite por plano:** `Plano.max_contas`, 3 no Premium e 1 nos outros.
   Conta extra só abre, sincroniza e aparece no seletor enquanto o plano da
   principal permitir mais de uma (decisão 2.1). Se o Premium voltar, tudo
   volta.
4. **Conta aberta: cabeçalho `X-Conta`.** O front guarda a escolha num cookie
   e manda o id da conta no cabeçalho. O backend confere que a conta é do
   usuário logado e que o plano permite; sem o cabeçalho, vale a principal.
   - Conta que não é do usuário: **403 `conta-invalida`**, nunca a principal
     no lugar. Trocar em silêncio mostraria o número de uma conta com o nome
     de outra. O front apaga o cookie e volta para a principal.
   - O histórico visível (`historico_visivel`) é o da conta aberta: cada
     conta tem o próprio backfill.
5. **Adicionar conta:** botão em Conectar, só com vaga no plano. O `state`
   do OAuth leva o seller principal e o modo "nova". O callback cria a linha
   da conta extra sob trava na linha da principal, para dois callbacks
   simultâneos não passarem do limite. Conta do ML já conectada em qualquer
   lugar continua recusada (`ja-conectada`).
   - O ML conecta a conta que está logada no navegador. A tela avisa: para
     adicionar outra, saia da conta do ML antes.
6. **Remover conta extra:** apaga a linha e, em cascata, todos os dados
   dela, depois de confirmação na tela. A principal não se remove: sai com
   "Excluir conta". Desconectar continua como hoje (apaga a credencial, os
   dados ficam).
7. **Agendador e worker:** a rodada de sincronização e o `plano_vigente` do
   worker leem plano e aceite pela principal. A conta extra entra só se o
   plano permitir mais de uma conta.
8. **Retenção:** o prazo de uma conta extra é o da assinatura da principal.
   Sem isso, conta extra nunca venceria, porque não tem assinatura própria.
9. **Exclusão de conta:** o script trata todas as contas do usuário. Cada uma
   entra em `contas_excluidas`, e as checagens de assinatura viva olham a
   principal.

## Parte B: visão somada (próximo PR)

`X-Conta: todas` faz as consultas de Resumo, Financeiro, Produtos, Clientes
e Alertas filtrarem por `seller_id = ANY($1)`. Custos e Conectar recusam a
visão somada. Os detalhes ficam para a spec ser atualizada com a parte B.

## Fora desta entrega

- Trocar a conta principal por outra.
- Preço por conta: o Premium inclui as 3.
- Volume: cada conta extra traz o próprio histórico de 12 meses e a própria
  sincronização a cada 6 horas. Um cliente com 3 contas ocupa perto do triplo
  do banco, o que aproxima o limite do Supabase gratuito.
