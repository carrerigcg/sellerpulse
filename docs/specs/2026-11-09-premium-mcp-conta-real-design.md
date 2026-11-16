# Premium: MCP com a conta real

Estado: no ar desde 2026-11-16 (PR #60, `7349dac`; migration 0026 aplicada).
Falta a prova com o token real, conectado no Claude (ver "Prova esperada").
O Premium segue fora da vitrine até o PR seguinte. Função 4 do Premium
(`docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`, etapa 11).

## O pedido

Hoje o MCP (`/mcp`, `docs/specs/2026-10-13-mcp-server-design.md`) responde só
sobre a loja de demonstração, sem login. O Premium promete que o vendedor
pergunte ao Claude (ou a outro cliente de IA) sobre a própria loja: quanto
faturou, a margem, os produtos que sustentam a loja, quem parou de comprar.

O adiamento de 2026-10-13 tinha três motivos: não ajudava quem avalia, não
havia usuários e a URL de autorização é registro fixo. Os dois primeiros
caíram quando virou função paga; o terceiro caiu com o domínio próprio
(2026-11-16).

## Decisões travadas

1. **Login pelo servidor OAuth 2.1 do Supabase** (decisão 1.1 do Guilherme,
   2026-11-16). Conferido em 2026-11-16: está em beta e é grátis em todos os
   planos, inclusive o Free. Ele faz o registro dinâmico de cliente que o
   Claude pede, guarda o login, o app autenticador e a renovação de token.
   Nosso código só tem a tela de consentimento e a validação do token. O
   risco aceito é o beta: se ele mudar, o MCP da conta para, e a demo e o
   painel não são afetados.
2. **Endereço próprio:** `https://api.usesellerpulse.com/mcp/conta`. O `/mcp`
   da demo continua público e igual: quem já conectou a demo não perde nada.
   O metadado do recurso protegido (RFC 9728) fica em
   `/.well-known/oauth-protected-resource/mcp/conta` e aponta para
   `https://<projeto>.supabase.co/auth/v1`; sem token, a resposta é 401 com
   `WWW-Authenticate`, que é o que faz o Claude abrir o login.
3. **Só leitura, sempre.** As mesmas seis ferramentas da demo, sobre o dado
   do vendedor. Nada de escrever custo, sincronizar ou mexer no anúncio.
4. **O token da IA só vale no MCP.** O token OAuth do Supabase é um JWT
   igual ao da sessão do site, com a claim `client_id` a mais. Sem trava, ele
   chamaria a API inteira: gravar custo, sincronizar, cancelar a assinatura.
   A API REST recusa token com `client_id` (401), e o `/mcp/conta` recusa
   token **sem** `client_id`: a sessão do site também não serve lá. A API de
   dados do próprio Supabase (PostgREST) também aceitaria o token, com as
   policies `for all` das tabelas da loja: a migration 0026 fecha todas as
   tabelas de tenant para token com `client_id` (`as restrictive`, sem mexer
   na sessão do site). O front não usa a API de dados.
5. **Desconectar corta na hora.** O `revokeGrant` do Supabase apaga a sessão
   e o token de renovação, mas o token de acesso já emitido valeria até
   vencer (1 hora). A cada chamada, o servidor confere que a `session_id` do
   token ainda existe em `auth.sessions`; desconectada, a chamada seguinte já
   é recusada.
6. **Só Premium** (`Recurso.MCP_CONTA`). Fora do Premium a tela de
   consentimento não oferece Autorizar (decisão 14). Quem conectou e depois
   saiu do Premium continua conectado, mas cada ferramenta responde que a
   função é do Premium e aponta para a Assinatura, em vez de um erro técnico. O plano é lido a cada chamada: rebaixar corta
   na chamada seguinte, e subir libera sem reconectar. Termos não aceitos
   recebem o mesmo tipo de resposta, apontando para o aceite.
7. **Segundo fator:** quem ativou o app autenticador só conecta a IA
   passando por ele. O token OAuth do Supabase nasce `aal1` mesmo quando a
   aprovação veio de uma sessão `aal2` (medido na primeira conexão real,
   2026-11-16), e a rota de aprovação do Supabase só exige login, não o
   segundo fator (`internal/api/api.go` do `supabase/auth`): exigir `aal2`
   no token barrava todo mundo, e aceitar `aal1` deixava quem tem só a senha
   aprovar direto pela API. Por isso a aprovação passa pelo nosso backend
   (decisão do Guilherme, opção 1, 2026-11-16): antes de aprovar, a tela
   chama `POST /conta/conexoes-ia/aprovacao` com o pedido de autorização;
   o backend exige `aal2` como o painel, lê o cliente do próprio pedido no
   Supabase (`auth.oauth_authorizations`, vivo e do mesmo login, e não o que
   o navegador manda) e grava a aprovação em `aprovacoes_de_ia` (migration
   0027). Quem já tinha autorizado antes é aprovado sozinho pelo Supabase,
   sem passar pelos botões: a tela grava a aprovação também nesse caminho,
   antes de redirecionar. O MCP aceita o token de quem tem autenticador se
   ele for `aal2` ou se houver aprovação do mesmo login e do mesmo cliente
   feita até 15 minutos antes de a sessão do token nascer (com 1 minuto de
   folga de relógio entre o Postgres e o servidor de login). Aprovação
   antiga não serve para conexão nova: cada conexão precisa da sua. Risco
   aceito: dentro desses 15 minutos, a aprovação não é consumida; abrir uma
   segunda sessão do mesmo cliente nesse intervalo ainda exigiria a senha e
   o retorno do próprio cliente.
8. **Várias contas:** cada ferramenta ganha o parâmetro opcional `conta`: o
   apelido da loja no Mercado Livre, ou `todas` para a soma. Sem ele, é a
   principal. A regra de quem abre e de quem soma é a do painel
   (`conta_abre`, `soma_abre`).
9. **As mesmas regras de número do painel:** as mesmas funções de
   `backend/analytics/`, o corte do histórico do plano
   (`limita_ao_historico`), ausência como ausência. Janela cortada vem dita
   na resposta (`historico_desde`), e não como venda zero.
10. **Toda resposta diz de qual conta e de qual período é o dado**, no lugar
    do aviso de demonstração.
11. **Registro de acesso:** cada chamada grava em `registros_de_acesso`, como
    o painel (uma linha por hora e IP). O IP é o do servidor do cliente de
    IA, que é quem acessa.
12. **Limite de uso:** 300 chamadas por hora por login (decisão 3). Fica em
    memória, numa instância só: zera a cada deploy, e isso é aceito, porque
    a função é proteger o serviço, não cobrar.
13. **Conexões de IA na tela Segurança** (decisão 2), para todos os planos:
    a lista do que foi autorizado (nome do cliente e data) e o botão
    Desconectar. Quem rebaixou o plano também precisa poder desconectar.
14. **Tela de consentimento** em `/oauth/consent`: exige login (o proxy manda
    para o login e volta), mostra o nome do cliente e o que ele vai poder
    fazer ("ler os números da sua loja, sem alterar nada"), com Autorizar e
    Recusar. Fora do Premium, a tela diz isso e só oferece Recusar e o link
    da Assinatura. Sem resposta do servidor, a tela não diz "fora do plano":
    pede para recarregar, sem recusar.
15. **A tela mostra para onde o acesso vai.** O registro de cliente é aberto,
    e quem registra escolhe o nome: qualquer um registra um "Claude" com
    retorno no próprio domínio e manda o link ao vendedor. A tela mostra o
    host do endereço de retorno e o e-mail do login, e avisa quando o retorno
    não é do Claude, do ChatGPT ou do próprio computador (localhost).

## O que o Guilherme configura (produção, com o ok dele)

No Supabase, Authentication > OAuth Server:

- ligar o servidor OAuth 2.1;
- Authorization Path: `/oauth/consent` (o Site URL já é
  `https://usesellerpulse.com`);
- ligar o registro dinâmico de cliente.

## Prova esperada

- Teste com dois logins: o token de um nunca devolve dado do outro, nem na
  soma, nem passando o apelido da conta do outro.
- Token sem `client_id` recusado no MCP; token com `client_id` recusado na
  API REST.
- Sessão apagada: a chamada seguinte recusa.
- Plano rebaixado: a chamada seguinte responde "só no Premium".
- Limite: a 301ª chamada da hora é recusada.
- No token real do Supabase: que ele traz `client_id`, `session_id` e
  `aud: authenticated`, e se herda o `aal2` de quem tem app autenticador.
  Os testes montam o token à mão com essas claims; só a conexão real prova.
- Na API de dados, depois da 0026: com `client_id`, zero linhas e escrita
  recusada; sem ele, a sessão do site como antes. **Provado em produção em
  2026-11-16** (transação desfeita, papel `authenticated`): antes da 0026, o
  token com `client_id` lia 1.759 pedidos; depois, 0 pedidos, 0 custos, 0
  lojas, update em 0 linhas e insert em `product_costs` recusado pela RLS; a
  sessão sem `client_id` continuou com 1.759 pedidos e 1 loja.
- Conectado de verdade no Claude do Guilherme, com os números conferidos
  contra o painel no mesmo período.

## Fora desta entrega

- A volta do Premium à vitrine e ao checkout, com o atendimento e os Termos
  (próximo PR).
- Ferramentas novas (alertas, custos, conversão): primeiro as seis, com dado
  real.
- ChatGPT e outros clientes: entram se o fluxo padrão funcionar neles, sem
  código específico.
- Limite de uso persistente (no banco): só se o limite em memória se mostrar
  insuficiente.
