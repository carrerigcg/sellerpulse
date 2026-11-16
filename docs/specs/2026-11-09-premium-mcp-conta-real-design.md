# Premium: MCP com a conta real

Estado: decidido em 2026-11-16 (opções 1.1, 2 e 3 abaixo); em implementação
na branch `feat/premium-mcp-conta`. Função 4 do Premium
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
   token **sem** `client_id`: a sessão do site também não serve lá.
5. **Desconectar corta na hora.** O `revokeGrant` do Supabase apaga a sessão
   e o token de renovação, mas o token de acesso já emitido valeria até
   vencer (1 hora). A cada chamada, o servidor confere que a `session_id` do
   token ainda existe em `auth.sessions`; desconectada, a chamada seguinte já
   é recusada.
6. **Só Premium** (`Recurso.MCP_CONTA`). Outro plano conecta, mas cada
   ferramenta responde que a função é do Premium e aponta para a Assinatura,
   em vez de um erro técnico. O plano é lido a cada chamada: rebaixar corta
   na chamada seguinte, e subir libera sem reconectar. Termos não aceitos
   recebem o mesmo tipo de resposta, apontando para o aceite.
7. **Segundo fator:** quem ativou o app autenticador precisa de token `aal2`,
   a mesma regra do painel (`_claims_verificadas`).
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
    da Assinatura.

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
