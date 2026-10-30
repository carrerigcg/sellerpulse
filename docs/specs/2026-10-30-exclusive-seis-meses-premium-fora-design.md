# Exclusive com 6 meses de histórico e Premium fora da venda

Estado: no ar desde 2026-10-30 (#38). Etapa 2 de `docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`.

## Por quê

A vitrine e os Termos prometem 6 meses no Exclusive, mas o código não cortava. Com o
tempo, o Exclusive entregaria de graça o histórico longo que o Premium vai vender. E o
Premium custa mais sem entregar as funções anunciadas, então não pode ser vendido ainda.

## Decisões (Guilherme, 2026-10-30)

- **Exclusive corta em 180 dias**, o mesmo número da ingestão inicial.
- **Premium sai da venda:** o checkout e a troca recusam com 409 `plano-fora-de-venda`, e
  a recusa vem antes do aceite, para não gravar aceite de algo que não acontece.
- **Quem já tem Premium continua, sem corte.** Hoje é só a conta do dono. Ele ainda pode
  desfazer um downgrade agendado, porque continuar no plano não é contratar.
- **A vitrine mostra só dois planos**, sem "em construção": não se anuncia o que não está
  à venda. Os preços do Premium ficam em `lib/precos.ts`, porque quem já tem ainda o vê.
- **O aviso de corte diz o plano de quem lê**, e só o Essencial recebe convite para subir.
  No Exclusive não há para onde ir.
- **Clientes, Custos e Exportar passam a avisar o corte.** Clientes e Exportar nunca
  precisaram, porque o Essencial não chega a elas, e o CSV sairia cortado em silêncio.

- **Checkout de Premium aberto antes do merge é honrado:** quem pagou recebe o que comprou.
  Medido em produção em 2026-10-30: nenhum aberto.
- **Janela inteira fora do plano diz o limite**, em vez de culpar o backend, e o nome do
  CSV leva o período que o arquivo cobre.

## Fora desta spec

- O lançamento do Premium (etapa 11).
