# Cobrança pelo Asaas

Estado: spec aprovada, em implementação. Merge só depois do teste ponta a ponta
no sandbox do Asaas.

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
| Essencial | R$ 49,92 | R$ 499,20 |
| Exclusive | R$ 79,97 | R$ 799,70 |
| Premium | R$ 139,95 | R$ 1.399,50 |

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

`POST /conta/checkout` recebe `{plano, ciclo, versao_dos_termos, nome, cpf_cnpj, email}`:

1. Confere a versão dos termos e grava o aceite (a mesma prova de hoje).
2. Monta o checkout do Asaas com o valor de `backend/planos.py`:
   - no mensal, `chargeTypes: RECURRENT` e cartão;
   - no Exclusive mensal, a primeira cobrança vai para daqui a 7 dias;
   - no anual, `DETACHED`, com Pix e cartão.
3. Guarda em `checkouts` (id do checkout, vendedor, plano, ciclo), porque é por
   ele que o webhook descobre de quem é o pagamento.
4. Devolve o link, e o front redireciona.

**O CPF/CNPJ vai para o Asaas e não é guardado aqui.** O Asaas exige o dado
para cobrar; nós não precisamos dele depois (minimização, LGPD art. 6º, III).

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
  - para quem está logado, "Assinar" abre o formulário: mensal ou anual, nome,
    CPF/CNPJ, e-mail e o aceite dos termos;
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

## A confirmar no sandbox, antes do merge

A documentação não responde estes pontos, e o código só se fecha depois de
vê-los num evento de verdade:

- Como o `CHECKOUT_PAID` se liga à assinatura e ao cliente criados, e se o
  `externalReference` do checkout chega até eles.
- Se o checkout com teste (primeira cobrança no 8º dia) dispara
  `CHECKOUT_PAID` quando o cartão é validado, sem cobrança.
- Se o checkout coleta o CPF sozinho quando `customerData` não vai.

## Riscos

- **Render gratuito e webhook.** O Render hiberna, e acordar leva cerca de
  25s. O Asaas conta timeout como falha e pausa a fila depois de 15. Antes do
  primeiro cliente real, o Render pago (cerca de US$ 7/mês) é obrigatório.
- **Fila pausada:** eventos com mais de 14 dias são descartados. O log do
  webhook precisa avisar quando um evento falhar.

## Fora desta spec

- Pix Automático no mensal (fase 2).
- Cobrar a diferença proporcional do upgrade (decisão 6).
- Nota fiscal.
- Atualizar a Política de Privacidade: o CPF/CNPJ passa pelo SellerPulse a
  caminho do Asaas, e o Asaas entra como fornecedor (`docs/legal/`).
