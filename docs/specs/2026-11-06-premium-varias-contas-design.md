# Premium: até 3 contas do Mercado Livre

Estado: parte A (várias contas, com seletor) no ar desde 2026-11-09 (#55,
`a0a7568`, migration 0023). Parte B (visão somada) no ar desde 2026-11-09
(#56, `78d6155`). Não provado: o painel real logado com duas contas na soma.
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

## Parte B: visão somada

1. **`X-Conta: todas`**, guardado no mesmo cookie. Só vale com um plano de
   várias contas e pelo menos duas contas; fora disso é `conta-invalida`, e o
   front volta à principal. Com uma conta só não há seletor no topo, e aceitar
   a soma deixaria o vendedor preso nela (`revisor-de-interface`). Remover uma
   conta durante a soma também apaga a escolha.
2. **Entram todas as contas que abrem no plano**, conectadas ou não. O dado
   de uma conta desconectada é real até o dia em que ela parou; o rodapé de
   "atualizado em" fica com a sincronização mais antiga, que é o que avisa.
3. **Cada rota opta pela soma; o padrão recusa.** `get_acesso` e
   `get_contas` respondem **409 `visao-somada`** para `todas`. Só as
   leituras somam: fluxo, cancelamentos, top produtos, alertas, ABC, RFM,
   cohort, a lista de custos (o Resumo a usa para a cobertura) e
   `/conta/acesso`. Gravar custo, conectar, desconectar e o status da
   sincronização continuam por conta. Adicionar e remover conta e trocar de
   plano agem sobre o login, e não sobre a conta aberta: aceitam a visão
   somada (a lista de contas continua em Conectar, e a Assinatura não depende
   de conta). Cancelar, desistir e pagar já iam direto à principal.
   - Na visão somada, `Acesso.seller_id` levanta erro: rota que optou pela
     soma e leu uma conta só mostraria a principal com o rótulo de todas.
   - Por quê: uma rota nova que esquecesse da soma, com o padrão invertido,
     gravaria na conta errada ou mostraria uma conta só com o rótulo de
     todas.
4. **Sincronizar ao entrar, na visão somada, não enfileira** (responde
   `visao-somada`), e o botão manual recusa. O Premium já sincroniza cada
   conta a cada 6 horas pela rodada agendada.
5. **Histórico: o menor entre as contas.** Com uma conta já em 12 meses e
   outra ainda em 6, mostrar 12 exibiria os 6 antigos da segunda como venda
   zero. Ausência não é zero.
6. **Consultas:** `seller_id = ANY($1::uuid[])`, e todo JOIN continua casando
   pelo `seller_id` da própria linha. Com uma conta, a lista tem um elemento
   e o resultado é o mesmo de antes (paridade com `src/` intacta).
   - **Frete:** o envio é por conta: `envios` agrupa por (conta, envio).
   - **Conversão:** o início da colheita de visitas é o de cada conta. Com o
     da loja mais antiga, a venda de uma conta antes da colheita dela entraria
     no numerador sem visita medida.
7. **Alertas:** a margem negativa olha todas as contas juntas. O parado é
   medido conta por conta, cada uma contra a própria última sincronização (com
   a referência de outra conta, um produto pareceria parado sem estar), e as
   listas se juntam na mesma ordem. A data mostrada é a mais antiga.
8. **Clientes:** o id do comprador no ML é o mesmo nas duas contas, então
   ele conta uma vez (decisão 1.1). Carrinho (`pack_id`) é de uma conta só.
9. **Produtos:** o mesmo produto anunciado em duas contas são dois anúncios,
   duas linhas. É o que o ML tem: o SellerPulse não sabe que são o mesmo.
10. **Front:**
    - o seletor ganha "Todas as contas (soma)";
    - Custos e Conectar mostram "escolha uma conta" em vez da tela, e
      Conectar mantém a lista de contas do login.

## Fora desta entrega

- Trocar a conta principal por outra.
- Visão somada: dizer de qual conta é cada produto ou alerta, e as tarefas
  do Resumo que levam a Custos (lá é preciso escolher a conta).
- Preço por conta: o Premium inclui as 3.
- Volume (`auditor-de-escala`, medido em 2026-11-06 na loja real):
  - **Fila:** uma conta Premium ocupa ~11,5 min por dia do worker único
    (visitas ~570 s, 4 deltas, 4 fretes). O teto fica perto de 125 a 145
    contas do tamanho da loja real; a referência passa a ser **contas**, não
    vendedores. Cada conta nova entra com ~40 min de fila (projeção: o
    backfill de 12 meses ainda não rodou em produção).
  - **Espaço:** ~12 a 14 MB por conta Premium em 12 meses; um cliente de 3
    contas ocupa ~40 MB dos 500 MB do Supabase gratuito.
  - **A API do ML não é o limite:** o worker serial não passa de ~2 pedidos
    por segundo.
  - Feito (migration 0024), antes de vender o Premium: o índice em `sync_jobs` para o
    `dias_ja_buscados` (já anotado na spec do histórico de 12 meses), que as
    contas extras fazem crescer mais rápido.
- Trocar de conta recarrega a página inteira, e não só os dados: o
  `router.refresh()` guardaria o estado das telas interativas (custos,
  conexão) com a conta anterior (`revisor-de-interface`).
