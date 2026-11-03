# Desistência pela tela

Estado: em revisão. Etapa 10 de `docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`.

## Por quê

Os Termos (seção 8) garantem o direito de arrependimento (CDC, art. 49): desistir em até
7 dias da contratação ou do primeiro pagamento e receber de volta o valor integral. Hoje
isso depende de o cliente escrever e de o dono estornar à mão no painel do Asaas
(`docs/operacao.md`, seção 9), com risco de perder o prazo legal.

## Decisões

- **O botão aparece em "Minha assinatura" só durante o prazo**: do primeiro pagamento do
  contrato até o fim do 7º dia depois dele, no dia do vendedor. Quem está no teste grátis
  e ainda não pagou nada não vê o botão: o "Cancelar" já resolve sem custo.
- **O Asaas é a fonte dos pagamentos.** Sem coluna nova: a tela e o endpoint perguntam ao
  Asaas os pagamentos do cliente e ficam com os do contrato atual (o `checkoutSession` do
  checkout vigente, ou a assinatura vigente). A data do pagamento é a mais cedo entre
  `confirmedDate`, `paymentDate` e `clientPaymentDate`.
- **Mensal e anual, pela mesma regra.** O arrependimento é o mesmo para os dois. O
  estorno proporcional do anual fora dos 7 dias continua manual, até o advogado aprovar
  a frase.
- **Ordem:** encerra a recorrência no Asaas, estorna cada pagamento do contrato e só
  então corta o acesso. Se o estorno falhar depois da recorrência encerrada, a conta fica
  cancelada como num cancelamento comum, a tela diz que o estorno está pendente e o log
  avisa o dono.
- **O acesso acaba na hora.** O dinheiro volta inteiro, então não há período pago a
  respeitar. O `PAYMENT_REFUNDED` que chega depois só encurta (`LEAST`), e não devolve
  a tolerância.
- **Alerta ao dono** a cada desistência, no log, como os outros casos que pedem olho.
- **O aviso atrasado do pagamento não devolve o acesso.** O botão olha o Asaas na hora,
  então dá para desistir antes de o aviso de pagamento confirmado chegar. Cada estorno
  grava `desistencia:<pagamento>` em `eventos_do_gateway`, e o aviso desse pagamento é
  ignorado. Sem coluna nova: a marca sai com a retenção de 5 anos dos eventos.
- **O status do estorno vai para o log.** Uma conta que exige autorização de ação crítica
  deixa o estorno parado até o dono aprovar no painel.
- **Pix do anual no mesmo dia pode ser recusado** por falta de saldo (as taxas não
  voltam, segundo o Asaas): cai no estorno pendente, e o dono estorna à mão.

## Fora desta spec

- Estorno proporcional do anual depois dos 7 dias (advogado).
- E-mail de confirmação da desistência: depende do domínio (etapa 9).
