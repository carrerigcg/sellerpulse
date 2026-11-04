# Avisos por e-mail do Asaas e comprovantes na tela

Estado: mergeado em 2026-11-04 (#47); chamada real ao Asaas ainda não provada.

## O problema

Na compra de teste de 2026-11-03, quem pagou não recebeu recibo nem
comprovante por e-mail. O aviso "Cobrança recebida" do cliente estava
desligado no Asaas.

O suporte do Asaas confirmou em 2026-11-04:

- A conta não tem configuração geral de avisos: cada cliente tem os seus.
- O cliente criado pela API nasce com os avisos ligados.
- O cliente que o próprio Checkout cria na hora do pagamento, que é o nosso
  caso, nasce com **todos** os avisos sem e-mail e sem SMS.

## Decisões travadas

1. **Ligar depois, e não criar o cliente antes.** Criar o cliente pelo
   `POST /v3/customers` exigiria telefone e endereço completos, e o
   SellerPulse não coleta dados de cobrança (spec da cobrança, "Contratar").
2. **Todos os avisos, só o e-mail.** Cada aviso do cliente fica `enabled` e com
   `emailEnabledForCustomer`, inclusive cobrança gerada, vencimento, atraso e
   recebida. O SMS fica como está, porque pode ter custo por envio e o e-mail
   basta. Decisão do Guilherme, 2026-11-04.
3. **Quando ligar:**
   - Depois da resposta do webhook, no primeiro aviso que traz o `customer`
     (pagamento ou assinatura). O `CHECKOUT_PAID` traz `customer: null`.
   - Também ao abrir "Minha assinatura", para alcançar quem pagou antes desta
     mudança.
   - Uma vez só por cliente. A marca `avisos:{cliente}` fica no
     `eventos_do_gateway`, como a da desistência, sem coluna nova.
   - Só para cliente de um checkout ou assinatura nossa.
   - A falha vira aviso no log, sem marca, e a próxima chance tenta de novo.
     O 200 do webhook não depende dela.
   - É um `PUT /v3/notifications/{id}` por aviso, como o suporte indicou, e
     só nos que ainda faltam.
4. **O recibo da primeira compra fica na tela.** O cliente nasce no pagamento,
   então o recibo dessa cobrança sai antes de dar tempo de ligar o e-mail.
   - "Minha assinatura" ganha a seção **Pagamentos**: dia, valor, "devolvido"
     quando estornado, e o link **Ver comprovante**. Os dados vêm de
     `GET /conta/pagamentos`, lidos do Asaas na hora.
   - O link (`transactionReceiptUrl`) abre, sem login, a página do Asaas com
     os dados de quem pagou. Por isso continua fora do log de eventos
     (`sem_dados_pessoais`), não é guardado em lugar nenhum, e só é entregue à
     conta dona do contrato.
   - A política de privacidade não muda, porque nada novo é guardado.
   - Lista todos os pagamentos do cliente com comprovante. Um cliente que
     recontratou vê também os do contrato antigo, que também são dele.
   - Se o Asaas não responder, a seção não aparece.

## O que ficou de fora

- Mandar recibo por e-mail próprio do SellerPulse: não há envio de e-mail no
  produto.
- Corrigir os avisos de clientes antigos sem que o vendedor abra a tela. Hoje
  existe um cliente só, o da compra de teste.
- Paginação: `pagamentos_do_cliente` traz até 100 pagamentos, oito anos de
  mensalidade.
- Resolvido na branch `fix/assinatura-acabamentos`: o backend manda `situacao`
  (`pago`, `devolvendo`, `devolvido`), e a tela mostra "devolução em andamento"
  enquanto o estorno está pedido ou em andamento. "devolvido" só com `REFUNDED`.
- A lista é por cliente do Asaas, sem o filtro de contrato. Se o Checkout
  reaproveitar o cliente de um pagador que paga duas lojas (um contador), uma
  loja veria os recibos da outra, com os dados do mesmo pagador. Não foi
  verificado se o Asaas reaproveita. O filtro possível é o `externalReference`,
  se ele vier repetido nos pagamentos da assinatura, o que precisa ser medido.
