# Desistência pela tela

Estado: no ar desde 2026-11-03 (#45); estorno real ainda não provado. Etapa 10 de `docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`.

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

## Pendências da revisão, que não travam

- Estorno parado à espera de autorização e depois rejeitado deixa a marca e o acesso
  cortado com o pagamento valendo. O status do estorno no log permite conciliar à mão.
- O foco volta ao `body` quando a confirmação fecha (Voltar, erro, fim da ação). O
  conserto é uma `ref` no botão que abre. O grupo de botões da confirmação também não
  tem nome para o leitor de tela.

Resolvidas na branch `fix/desistencia-termina-o-servico`:

- Processo que cai entre o estorno aceito e o corte do acesso: dentro do prazo, com
  pagamento já estornado e acesso ainda aberto, a tela continua oferecendo a desistência,
  e a nova tentativa grava as marcas e corta sem estornar de novo. Com o acesso já
  cortado, segue "já devolvido". O mesmo caminho pega o estorno feito à mão pelo suporte
  dentro do prazo: o `GET` devolve `ja_devolvido` e a tela troca a promessa do valor
  por "encerrar o acesso", porque o backend não distingue os dois casos.
- Foco do teclado: ao abrir a confirmação de "Desistir", "Cancelar" ou da cobrança
  em `/planos`, e na troca de plano, o foco vai para o botão de voltar, a saída que não confirma nada.
