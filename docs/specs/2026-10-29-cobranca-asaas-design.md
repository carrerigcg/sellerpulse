# Cobrança pelo Asaas

Estado: no ar desde 2026-10-30 (#35), com a conta de produção do Asaas. Falta a
compra real de teste, seguida de estorno, e os termos finais antes de divulgar.

## Por quê

Os planos e a trava de acesso estão no ar (#34), mas o plano é atribuído à
mão. Para vender sem depender do dono liberar cada conta, o vendedor precisa
escolher o plano, aceitar os termos, pagar, e ter o acesso liberado sozinho
quando o pagamento se confirmar. Isso também precisa valer para a renovação, a
inadimplência e o cancelamento.

## Decisões travadas (com o Guilherme, 2026-10-29)

1. **Gateway: Asaas.** Não tem mensalidade e é o único com Pix recorrente
   (Pix Automático) confirmado na documentação.
2. **Ordem da contratação:** escolhe o plano, aceita os termos, paga, e o
   acesso é liberado quando o Asaas confirma. O aceite acontece ANTES do
   pagamento, como contrato.
3. **Pagamento na página do Asaas** (checkout hospedado). O cartão nunca passa
   pelo SellerPulse.
4. **Pagamento que falha:** 7 dias de tolerância. Depois, o acesso volta a ser
   só a demo. Nenhum dado é apagado.
5. **Cancelamento:** o acesso vale até o fim do período já pago. Os dados ficam.
6. **Troca de plano:**
   - o upgrade libera na hora, e o valor novo vale a partir da próxima
     cobrança; a diferença do mês corrente fica por nossa conta (no máximo
     R$ 30 ou R$ 60);
   - o downgrade vale no próximo ciclo.
7. **Teste de 7 dias, só no Exclusive mensal**, com o cartão cadastrado no
   início e a primeira cobrança no 8º dia. Quem cancela antes não paga.
8. **Plano anual:** paga 10 meses e leva 12.
9. **Meios de pagamento:**
   - o mensal é no cartão, porque o checkout recorrente do Asaas só aceita
     cartão;
   - o anual é um pagamento único, por Pix ou cartão;
   - o Pix Automático no mensal fica para a fase 2.

### Preços

| plano | mensal | anual (10 × mensal) |
| --- | --- | --- |
| Essencial | R$ 49,90 | R$ 499,00 |
| Exclusive | R$ 79,90 | R$ 799,00 |
| Premium | R$ 139,90 | R$ 1.399,00 |

### Promoção de lançamento (2026-10-29)

Os preços acima são de lançamento. A vitrine mostra riscado o preço de depois
do lançamento (R$ 59,90 / 109,90 / 169,90), com o desconto ("−17%", "−27%",
"−18%"; o Exclusive tem o maior de propósito) e a economia por mês.

- **O riscado é dito como o preço depois do lançamento, nunca como um "de"
  que já foi cobrado.** Anunciar um preço anterior que nunca existiu é
  propaganda enganosa (CDC, art. 37). Por isso, esses números têm que ser
  mesmo o preço futuro.
- **"No plano mensal, você mantém este preço enquanto continuar no mesmo
  plano"** é uma promessa ao cliente. Ela é verdade pelo jeito que a cobrança
  funciona: a assinatura mensal no Asaas guarda o valor do dia em que foi
  criada. Não vale para o anual (pagamento único, recontratado pelo preço do
  dia) nem para a troca de plano (que usa a tabela vigente), e o texto diz
  isso.
- **Antes de subir os preços**, a tela "Minha assinatura" precisa mostrar o
  valor que a pessoa de fato paga, e não o da tabela. Hoje os dois são iguais;
  depois do aumento não serão.

Quem cobra é `backend/planos.py`: o checkout é montado com esses valores, e
o valor nunca vem do navegador. A vitrine mostra os mesmos números a partir de
`frontend/lib/precos.ts`, sem depender do backend acordado para desenhar a
landing. Um teste do backend lê esse arquivo e falha se os dois divergirem.

## Como

### O acesso passa a ter prazo

`assinaturas` ganha `acesso_ate` (timestamptz, nulo = sem prazo) e
`cancelada_em`. O vendedor
tem acesso se tem linha em `assinaturas` e `acesso_ate` é nulo ou está no
futuro. Os planos atribuídos à mão continuam sem prazo.

O prazo é o que torna a régua simples: **nenhum agendador desliga ninguém**.

- Cada pagamento confirmado empurra `acesso_ate` para o fim do período pago
  mais os 7 dias de tolerância.
- Se a próxima cobrança não for paga, o prazo simplesmente vence.
- Cancelar põe `acesso_ate` no fim do período pago, sem a tolerância, e marca
  `cancelada_em`. Um recebimento atrasado de um período antigo que chegue
  depois não devolve a tolerância a quem cancelou.

Também ganha: `ciclo` (`mensal | anual`), `asaas_cliente`, `asaas_assinatura`
e `plano_no_proximo_ciclo`, este último para o downgrade.

### Contratar

`POST /conta/checkout` recebe `{plano, ciclo, versao_dos_termos}`:

1. Confere a versão dos termos e grava o aceite (a mesma prova de hoje).
2. Monta o checkout do Asaas com o valor de `backend/planos.py`:
   - no mensal, `chargeTypes: RECURRENT` e cartão;
   - no Exclusive mensal, a primeira cobrança vai para daqui a 7 dias;
   - no anual, `DETACHED`, com Pix e cartão.
3. Guarda em `checkouts` (id do checkout, vendedor, plano, ciclo), porque é por
   ele que o webhook descobre de quem é o pagamento.
4. Devolve o link, e o front redireciona.

**Os dados de cobrança não passam pelo SellerPulse** (decisão de 2026-10-29,
depois da medição no sandbox). Mandar `customerData` faz o Asaas exigir
endereço completo e telefone (CEP, rua, número, bairro); sem ele, a página do
Asaas pede nome, CPF/CNPJ, endereço e cartão ela mesma. O nosso formulário
fica só com o plano, o ciclo e o aceite, e o SellerPulse não recebe CPF nem
endereço nem de passagem (minimização, LGPD art. 6º, III).

### Webhook

`POST /pagamentos/webhook`:

- Autentica pelo header `asaas-access-token`, comparado em tempo constante.
  Sem o segredo configurado, recusa: falha fechada, como o `sync-todos`.
- É idempotente pelo `id` do evento (tabela `eventos_do_gateway`). O Asaas
  entrega "pelo menos uma vez".
- Responde **200** mesmo a evento que ignora, porque qualquer outro código
  conta como falha. Depois de 15 falhas seguidas o Asaas pausa a fila.
- Eventos tratados:
  - **checkout pago:** liga o checkout à assinatura e ao cliente do Asaas e
    ativa o plano;
  - **pagamento confirmado** (`PAYMENT_CONFIRMED` / `PAYMENT_RECEIVED`):
    empurra o prazo e aplica um downgrade pendente;
  - **assinatura removida:** prazo no fim do período pago;
  - **estorno e chargeback:** prazo agora mais a tolerância, e um alerta no
    log para o dono olhar.

### Trocar e cancelar

- `POST /conta/plano` troca o plano. No upgrade, muda o plano na hora e faz
  `PUT` do valor novo para as cobranças futuras. No downgrade, grava
  `plano_no_proximo_ciclo` e faz `PUT` do valor.
- `POST /conta/cancelar` faz `DELETE` da assinatura no Asaas e põe o prazo no
  fim do período pago.

### Front

- **`/planos`:**
  - para quem está logado, "Assinar" abre o formulário: plano, mensal ou
    anual, e o aceite dos termos;
  - para quem não está, leva ao cadastro e volta;
  - o Exclusive mensal mostra "7 dias grátis".
- **Uma tela "Minha assinatura"** no painel: plano, próximo vencimento,
  trocar e cancelar.

### Configuração

| variável | o quê |
| --- | --- |
| `ASAAS_API_KEY` | chave da API (`$aact_hmlg_...` no sandbox, `$aact_prod_...` em produção) |
| `ASAAS_BASE_URL` | `https://api-sandbox.asaas.com/v3` ou `https://api.asaas.com/v3` |
| `ASAAS_WEBHOOK_TOKEN` | o token configurado no webhook do Asaas (não é a chave da API) |

Sem `ASAAS_API_KEY`, contratar responde 503, e não um erro genérico.

## Testado no sandbox (2026-10-29)

Fluxo ponta a ponta, com o backend de teste exposto por túnel e pagamentos de
teste feitos na página do Asaas:

| caso | resultado |
| --- | --- |
| Essencial mensal, cobrança na hora | plano liberado pelo pagamento; prazo de 1 mês + tolerância |
| Exclusive mensal, 7 dias grátis | `CHECKOUT_PAID` chega só com o cartão validado; primeira cobrança pendente no 8º dia; plano liberado até o fim do teste |
| Upgrade no teste (Exclusive → Premium) | plano trocado na hora; assinatura no Asaas passa a 139,90; a cobrança já gerada fica em 79,90 (decisão 6) |
| Cancelar no teste | assinatura removida no Asaas e a cobrança pendente some; `SUBSCRIPTION_DELETED` chega; acesso até o fim do teste |
| Essencial anual, pagamento único | o pagamento (sem assinatura) libera o plano por 12 meses + tolerância |

O que o sandbox mostrou, e mudou o código:

- **O checkout é o elo.** O pagamento e a assinatura trazem `checkoutSession`
  (o id do checkout criado por nós). O `CHECKOUT_PAID` traz `customer: null` e
  `subscription` com a CONFIGURAÇÃO da assinatura, não o id.
- **A fila chega fora de ordem**, mesmo no envio sequencial: o pagamento e a
  assinatura criada chegaram antes do checkout pago. Por isso, todo aviso que
  traz o checkout anota nele o cliente e a assinatura, e o primeiro que prova
  o pagamento ativa o plano, uma vez só (`checkouts.pago_em`).
- **URLs de retorno com `localhost` são recusadas**; HTTPS público é aceito,
  com ou sem `?checkout=ok`.
- **Sem `customerData`, a página do Asaas coleta os dados** de cobrança. Com
  ele, o Asaas exige endereço completo e telefone.
- **Checkout com Pix exige uma chave Pix** cadastrada na conta Asaas. Vale
  também para a conta de produção.
- **`imageBase64` é obrigatório** em cada item do checkout.
- **O `externalReference` do checkout não chega** ao pagamento nem à
  assinatura (vem nulo neles). Não é usado para nada além de auditoria.

Não testado no sandbox:

- Pagamento do anual por Pix: pagar o QR no sandbox exige uma segunda conta.
  O caminho do código é o mesmo do cartão (pagamento sem assinatura).
- Renovação mensal de verdade (o sandbox não avança o calendário), estorno e
  contestação: cobertos só pelos testes automatizados.
- Inadimplência: o vencimento da tolerância é coberto pelos testes.

## Riscos

- **Render gratuito e webhook.** O Render hiberna, e acordar leva cerca de
  25s. O Asaas conta timeout como falha e pausa a fila depois de 15. Antes do
  primeiro cliente real, o Render pago (cerca de US$ 7/mês) é obrigatório.
- **Fila pausada:** eventos com mais de 14 dias são descartados. O log do
  webhook precisa avisar quando um evento falhar.

## Decisões da revisão (2026-10-29)

- **Recontratar encerra a assinatura antiga no Asaas antes** de abrir o
  checkout novo. Se o Asaas recusar, o checkout não abre. Cancelar não exige
  plano ativo: o inadimplente é quem mais precisa parar a cobrança.
- **Escolher o plano atual com um downgrade agendado desfaz o downgrade.**
- **O payload dos eventos é gravado sem dado pessoal** (CPF/CNPJ, dados do
  cliente, cartão).
- **A RLS das tabelas novas é ligada na própria 0018**, para não haver janela
  aberta entre duas migrations.
- **Datas na tela:** o prazo é a meia-noite em que ele ACABA. "Pago até" e
  "vale até" mostram o dia anterior; "próxima cobrança" mostra o próprio dia.
- **Login devolve a pessoa para onde ela ia** (`?proximo=`). A conferência é
  pela origem do endereço resolvido, e não pelo começo do texto: o navegador
  remove TAB e quebra de linha, e `/<TAB>/golpe.dev` viraria `//golpe.dev`.
- **"Recorrente" na tela não depende do id da assinatura** (mensal pelo Asaas
  e não cancelado): no teste de 7 dias o id ainda não chegou, e o "Cancelar"
  sumiria.
- **Pagamento atrasado de uma assinatura antiga não grava o id dela** na
  assinatura nova (o vencimento dele é anterior ao começo da nova).
- **Quem cancelou ou tinha o anual** sai do painel com "o seu plano terminou",
  e não com "o pagamento não foi confirmado".

## Fora desta spec

- Pix Automático no mensal (fase 2).
- Cobrar a diferença proporcional do upgrade (decisão 6).
- Nota fiscal.
- O link entre login e cadastro não carrega o `?proximo=`: quem troca de uma
  tela para a outra volta ao painel, e não à contratação.
- Atualizar a Política de Privacidade: o Asaas entra como fornecedor e
  recebe os dados de cobrança direto do cliente (`docs/legal/`).
