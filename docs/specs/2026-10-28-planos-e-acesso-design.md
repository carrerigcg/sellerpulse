# Planos e controle de acesso (Essencial primeiro)

Estado: no ar desde 2026-10-29 (#34). Migrations 0016 e 0017 aplicadas antes do merge; a conta real está no Premium (origem manual) e aceita os termos pela tela `/aceite`.

## Por quê

O SellerPulse vai ser vendido em três planos: Essencial, Exclusive (o
recomendado) e Premium. A ideia de marketing é dar exclusividade. O Essencial
resolve a dor principal (quanto sobra de cada venda), e o resto do produto
aparece **com cadeado**, à vista, para o vendedor saber o que está perdendo.

Antes de existir cobrança, o produto precisa saber três coisas: de que plano é
cada vendedor, o que cada plano libera, e que ninguém entra sem plano e sem
contrato. Esta spec cria isso. O gateway de pagamento vem depois, numa spec
própria, e passa a ser quem atribui o plano.

## Decisões travadas (com o Guilherme, 2026-10-28)

1. **Sem plano, só demo.** Quem cria conta e não tem plano pago e contrato
   aceito vê a página de planos e a demonstração. O painel e o "Conectar
   Mercado Livre" ficam fechados. **A trava é no servidor**: sem plano, a API
   recusa os dados do painel, a conexão com o ML e a sincronização, mesmo
   chamada direto.
2. **Contrato = aceite eletrônico dos Termos de Uso.** Uma caixa "li e
   aceito", gravada com a versão dos termos, a data e hora, o IP e o
   navegador. Termos com versão nova exigem aceite de novo.
3. **Enquanto não há gateway, o plano é atribuído à mão**, por escrita no
   banco. A conta real conectada hoje é a loja do Guilherme e vai para o
   Premium.
4. **O que o Essencial libera, exatamente como combinado:**

   | Recurso | Essencial |
   | --- | --- |
   | Resumo, Financeiro (margem, fluxo, frete, cancelamentos), Custos | liberado |
   | Curva ABC | os 10 primeiros produtos; o resto desfocado, com cadeado |
   | Desempenho dos anúncios (visitas e conversão) | cadeado |
   | Clientes (RFM, recompra) | cadeado |
   | Cohort de lançamento | cadeado |
   | Exportar | cadeado |
   | Histórico | 3 meses (90 dias) |
   | Atualização | só a diária agendada; sem a do login e sem o botão |
   | Suporte | e-mail |

5. **Histórico de 3 meses: a ingestão continua trazendo 6.** O Essencial só
   enxerga os 90 dias mais recentes. No upgrade, o resto aparece na hora, sem
   esperar backfill.
6. **Atrás do cadeado: a tela com dados da demonstração, desfocados**, e o
   aviso "Disponível no Exclusive". Nunca o dado real do vendedor: o que o
   plano não cobre não sai do servidor.
7. **O botão do cadeado é "Fazer upgrade"** e leva à página de planos. Até o
   checkout existir, ela oferece WhatsApp e e-mail do Guilherme.
8. **Exclusive e Premium liberam tudo o que existe hoje.** O que vai
   diferenciá-los (MCP com a conta real, alertas, várias contas, histórico de
   12 meses, atualização mais frequente) entra com cada feature, antes do
   lançamento.

## Como

### Banco

- **`assinaturas`**: uma linha por vendedor com `plano`
  (`essencial | exclusive | premium`), `origem` (`manual | gateway`) e
  `desde` (migration 0016). **Não é coluna em `sellers` de propósito**: até a
  0015, a policy `sellers_update_own` (0002) deixava o próprio usuário alterar
  a sua linha em `sellers` com a chave pública do Supabase, e um plano
  guardado ali seria autoconcedido. A 0015 fechou isso, mas o plano fica numa
  tabela que nunca teve escrita pelo cliente. Ela tem RLS só de leitura para o
  dono e nenhuma policy de escrita (0017), então só o backend escreve nela.
- **`aceites_de_termos`**: `seller_id`, `versao`, `aceito_em`, `ip` e
  `user_agent`. Só cresce, nunca é sobrescrita: é a prova do aceite.

### Backend

- **Um lugar só diz o que cada plano libera** (`backend/planos.py`): recursos,
  dias de histórico, quantos produtos da ABC e se o vendedor pode sincronizar
  fora do agendamento. Os routers perguntam a ele; nenhum router tem
  `if plano == ...` próprio.
- **A dependency de acesso** resolve o vendedor, o plano e o aceite:
  - sem plano: **402**;
  - com plano e sem aceite da versão vigente: **403** `termos-pendentes`;
  - recurso fora do plano: **403** `fora-do-plano`.
- **Histórico:**
  - uma janela que entra parcialmente antes do limite é cortada no limite, e a
    resposta diz que cortou;
  - uma janela inteira antes do limite (por exemplo, o período anterior da
    comparação) é recusada com `fora-do-plano`, e **não devolvida vazia**;
  - o limite é contado no dia do vendedor (`FUSO_DO_VENDEDOR`).
- **ABC no Essencial:** o servidor devolve só os 10 primeiros, sem as colunas
  de visita e conversão, e diz quantos ficaram de fora.
- **Sincronização:**
  - o `POST /ml/sync` manual e o do login são recusados no Essencial;
  - o agendado (`sync-todos`) passa a pular quem não tem plano, para não
    gastar cota da API do ML com conta que não paga.
- **A conexão com o ML** (`/ml/connect/start` e o callback) exige plano e
  aceite.
- **A demo não muda:** continua aberta e mostra o produto inteiro.

### Front

- **`/planos`**: os três cartões, com o Exclusive em destaque e o selo
  "recomendado". Ainda não tem preço; o botão abre WhatsApp ou e-mail. Tem
  também o link para a demo.
- **`/aceite`**: os termos e a caixa de aceite. Aparece para quem tem plano e
  não aceitou a versão vigente.
- **O layout do painel** pergunta o acesso ao backend e redireciona: sem plano
  para `/planos`, termos pendentes para `/aceite`.
- **Um componente de cadeado** reutilizável: o bloco com dados da demo
  desfocados, "Disponível no Exclusive" e "Fazer upgrade".
- **Histórico cortado:**
  - um aviso "No Essencial, o histórico é de 3 meses";
  - a comparação com o período anterior mostra `—` com o cadeado, nunca 0.

## Como se prova

- Testes de backend por regra:
  - 402 sem plano;
  - 403 sem aceite e 403 fora do plano em cada recurso travado;
  - corte do histórico no dia do vendedor;
  - ABC com 10 itens e sem visitas;
  - sync manual recusado;
  - `sync-todos` pulando quem não tem plano;
  - um vendedor no Exclusive que continua vendo tudo, como hoje.
- Mutação em cada regra.
- Telas abertas no navegador com três contas de teste: sem plano, Essencial e
  Exclusive.

## Fora desta spec

- Preço dos planos, gateway, checkout, período de teste e plano anual.
- As features que diferenciam o Exclusive e o Premium (decisão 8).
- O texto final dos termos. Eles ainda são rascunho, com dados pendentes e a
  revisão do advogado. A versão em vigor no lançamento vai exigir aceite novo.
- Downgrade e cancelamento: o que acontece com o dado de quem sai de um plano.
  Fica para a spec do gateway. Até lá, nenhum dado é apagado por mudança de
  plano.

## Pendências (da revisão de 2026-10-29)

- **Custos no Essencial mostra a classe A/B/C de todos os produtos**, o que
  enfraquece o cadeado da ABC. Decisão do Guilherme em aberto.
- **Apagar a conta apaga a prova do aceite** (cascade a partir de `sellers`).
  A recomendação é manter, porque atende à exclusão pedida pelo titular, e
  registrar isso na spec de cancelamento.
- **Latência:** `resolve_seller_id` e `le_plano_e_aceite` podem virar uma
  consulta só, e as páginas podem buscar o acesso em paralelo com o que não
  depende dele. O auditor de escala mediu que não é preciso para 100–300
  vendedores; a latência real entre Render e Supabase não foi medida.
- **Front sem o campo novo:** o Conectar lê `sincroniza_sob_demanda` do
  status. O backend precisa estar no ar antes do front, senão o botão
  "Sincronizar agora" some para todos.
- `revoke truncate` em `anon`/`authenticated` vale para o schema inteiro, numa
  mudança à parte.
