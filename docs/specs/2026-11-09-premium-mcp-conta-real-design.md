# Premium: MCP com a conta real

Estado: rascunho, à espera do domínio e de três decisões do Guilherme
(seção "Para decidir"). Nada implementado. Função 4 do Premium
(`docs/plans/2026-10-30-pendencias-juridicas-do-produto.md`, etapa 11).

## O pedido

Hoje o MCP (`/mcp`, `docs/specs/2026-10-13-mcp-server-design.md`) responde só
sobre a loja de demonstração, sem login. O Premium promete que o vendedor
pergunte ao Claude (ou a outro cliente de IA) sobre a própria loja: quanto
faturou, a margem, os produtos que sustentam a loja, quem parou de comprar.

## Por que espera o domínio

Os três motivos do adiamento de 2026-10-13 eram: não ajuda quem avalia,
não havia usuários e a URL de autorização é registro fixo. Os dois primeiros
caíram, porque virou função paga do Premium. O terceiro continua: o cliente
de IA guarda a URL do servidor e a do login. Construir contra
`sellerpulse-049j.onrender.com` obrigaria todo cliente a reconectar quando o
domínio entrar.

## Decisões propostas

1. **Só leitura, sempre.** As mesmas seis ferramentas da fase 1, sobre o dado
   do vendedor. Nada de escrever custo, sincronizar ou mexer no anúncio.
2. **Só Premium.** Outro plano recebe uma resposta que diz isso e aponta para
   a Assinatura, e não um erro técnico. Rebaixar o plano corta o acesso na
   chamada seguinte, porque o plano é lido a cada chamada, como no painel.
3. **A demonstração continua onde está.** `/mcp` segue público e sem login
   (é o que a vitrine mostra), e o da conta real fica num endereço próprio,
   `https://api.dominio.com.br/mcp/conta`. Quem já conectou a demo não perde
   nada.
4. **Várias contas:** cada ferramenta ganha um parâmetro opcional `conta`
   (o apelido da loja, ou `todas` para a soma). Sem ele, é a principal. A
   regra de quem soma é a mesma do painel (`get_acesso_somavel`).
5. **As mesmas regras de número do painel:** fuso do vendedor, ausência como
   ausência (custo não informado não vira zero), histórico do plano.
6. **Registro de acesso:** cada chamada entra em `registros_de_acesso`, como
   no painel, para cumprir a mesma obrigação.
7. **Toda resposta diz de qual conta e de qual período é o dado**, como hoje
   diz que é demonstração.

## Para decidir

1. **Quem emite o login do cliente de IA (OAuth 2.1).** O Claude pede um
   servidor de autorização com registro dinâmico de cliente.
   - 1.1 (recomendo, a confirmar no dia): o servidor OAuth do próprio
     Supabase, que já guarda o login, o app autenticador e a sessão. Menos
     código nosso cuidando de token. Conferir antes se o recurso saiu do beta
     e se o plano gratuito tem.
   - 1.2: um servidor de autorização mínimo dentro do FastAPI. Funciona em
     qualquer plano, mas é código de segurança nosso para manter.
2. **Revogar pela tela:** uma lista "Conexões de IA" em Minha conta, com
   botão de desconectar. Recomendo entrar já na primeira entrega: sem ela, o
   vendedor que perde o controle do Claude não tem como cortar o acesso.
3. **Limite de uso:** recomendo um teto por login (por exemplo, 300 chamadas
   por hora) só para proteger o serviço. Cada chamada roda as mesmas
   consultas do painel.

## Prova esperada

- Teste por ferramenta com dois logins: o token de um nunca devolve dado do
  outro, nem na soma.
- Plano rebaixado: a chamada seguinte já recusa.
- Conectado de verdade no Claude do Guilherme, com os números conferidos
  contra o painel no mesmo período.

## Fora desta entrega

- Ferramentas novas (alertas, custos, conversão): primeiro as seis, com dado
  real.
- ChatGPT e outros clientes: entram se o fluxo padrão funcionar neles, sem
  código específico.
