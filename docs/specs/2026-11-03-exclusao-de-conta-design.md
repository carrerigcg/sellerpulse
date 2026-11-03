# Exclusão de conta a pedido

Estado: em revisão. Etapa 7 de `docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`.

## Por quê

Os Termos (seção 12) e a Política (seção 7) prometem apagar a conta em até 30 dias e
guardar por 5 anos a prova do aceite e os registros da cobrança. As duas promessas se
chocavam: apagar a conta cascateava de `sellers` e levava a prova junto.

## Decisões

- **Escopo A, operado por nós** (Guilherme, 2026-10-30): um script, sem botão na tela.
- **`aceites_de_termos` e `checkouts` perdem a chave estrangeira.** O `seller_id` fica como
  identificador da conta que já não existe. Os checkouts guardam os ids do Asaas, que
  ligam o aceite a quem pagou sem guardar nome nem e-mail aqui.
- **`contas_excluidas` liga o seller ao usuário** e marca a data, que é onde começam os
  5 anos e por onde se acham os registros de acesso numa contestação. Só identificadores.
- **Recusa quem ainda tem assinatura recorrente:** apagar a conta não para a cobrança.
  Cancelar no Asaas fica com quem opera, como no passo a passo de estorno.
- **Recusa a conta de demonstração**, e `--dry-run` mostra o que sai antes de apagar.
- **Checkout pago depois da exclusão** não reativa nada: o aviso responde
  `conta-excluida` e o log pede estorno. Sem isso, gravar em `assinaturas` quebraria a
  chave estrangeira e o Asaas repetiria o aviso para sempre.
- **O relatório lê do banco as tabelas com `seller_id`**, para tabela nova entrar sem
  ninguém lembrar.

## Fora desta spec

- Apagar a prova depois dos 5 anos e o registro de acesso órfão: entra com a limpeza de
  12 meses (etapa 8).
- Botão de exclusão na tela, e cancelar a assinatura no Asaas pelo próprio script.
