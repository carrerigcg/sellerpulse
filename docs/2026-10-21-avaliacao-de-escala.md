# SellerPulse — avaliação de escala para 100 a 300 vendedores

Data: 2026-10-21
Situação medida: **2 sellers** (1 real, 1 de demonstração), plano gratuito em
Render, Supabase e Vercel.

Tudo aqui foi **medido** contra produção ou lido no código, não estimado. Onde
há projeção, a base da conta está explícita para você refazer com outros
números.

---

## 0. O que já está certo (não mexer)

Começo por aqui porque metade de uma avaliação de escala é não consertar o que
não está quebrado.

- **Isolamento por inquilino está correto.** Os três módulos analíticos filtram
  por `seller_id` em toda consulta (18, 22 e 23 ocorrências). Não há vazamento
  entre vendedores.
- **Índices são adequados.** Toda tabela de tenant é chaveada em
  `(seller_id, …)`, então a consulta de um vendedor usa a chave primária e não
  varre os dados dos outros. Isso continua valendo com 300 vendedores.
- **RLS não é gargalo.** As policies usam `IN (SELECT … auth.uid())`, que o
  Postgres resolve como `hashed SubPlan` com `loops=1`. E nem são avaliadas: a
  aplicação entra como `postgres`, que tem `rolbypassrls`.
- **Visitas não gravam dia zerado.** Crescimento é por visita real, não por
  item × dia.
- **A fila tem cursor e retomada.** Backfill e colheita de visitas retomam de
  onde pararam, o que é pré-requisito para qualquer coisa nesta lista.

---

## 1. O muro: ingestão serial, um worker, dentro da API

É daqui que sai quase todo o resto.

**Medições:**

| o quê | medido | onde |
| --- | --- | --- |
| Backfill de um vendedor | **706 s (~12 min)**, 6 janelas de 30 dias | comentário em `worker/runner.py`, medido na loja real |
| Itens distintos do vendedor real | **985** | `order_items` em produção |
| Colheita de visitas | **1 chamada ao ML por item**, serial | `visitas_pg.colhe_visitas` |
| Worker | **1 job por vez** (`claim_next`), no mesmo processo da API | `worker/runner.loop` |
| Lease | **120 s**, com janela real levando **118 s** | `queue.LEASE_SEGUNDOS` |

**Projeção, usando o vendedor real como amostra (a única que temos):**

| cenário | 100 vendedores | 300 vendedores |
| --- | --- | --- |
| Onboarding (backfill de todos), serial | ~20 h de fila | ~60 h |
| Visitas por dia, **serial** | ~98.500 chamadas → ~5,5 h | ~295.500 → ~16 h |
| Visitas por dia, **concorrência 5** | **~64 min** | **~3,2 h** |

> **CORREÇÃO de 2026-10-21, por medição.** A primeira versão deste documento
> dizia 8 h e 25 h, projetando sobre 0,3 s por chamada **sem nunca ter medido
> concorrência**. Medido contra a API real: 181 ms de latência mediana, 5,0
> req/s em série e **25,8 req/s com concorrência 5, sem nenhum 429**. Uma
> colheita completa do vendedor real (985 itens) leva 3,3 min em série e **36
> segundos** com concorrência 5.
>
> Consequência: o muro é bem mais baixo do que este documento afirmava, e a
> concorrência (item B5) vale muito mais do que eu havia creditado. 300
> vendedores cabem folgados em um dia. O que **não** muda é o item 2 (lease) —
> paralelizar sem consertar o lease é que seria perigoso.

**O agravante que ninguém notou:** a lista de itens a colher é

```sql
SELECT DISTINCT item_id FROM order_items WHERE seller_id = $1
```

sem recorte de data — **todo item que o vendedor já vendeu na vida**. O custo
por sincronização não acompanha a atividade dele, acompanha o histórico
acumulado, e só cresce. 985 itens hoje viram 1.500 no ano que vem, e toda
sincronização paga por todos, inclusive os que não vendem há dois anos.

---

## 2. A armadilha de escalar horizontalmente

`WORKER_IN_PROCESS` tem default `"1"`. **Todo processo web sobe um worker.**
Então a reação natural a "está lento" — subir para 2 ou 3 instâncias — cria 2
ou 3 workers disputando a mesma fila.

E o próprio código já avisa o que acontece:

> "Numa loja um pouco maior o lease vence no meio da janela e o job passa a
> casar com `_CANDIDATO` (`status = 'running' AND leased_until < now()`)
> enquanto ainda está rodando — outro worker reclama o mesmo job e ingere o
> mesmo período em paralelo."

Com um worker isso é inofensivo. Com dois, é **ingestão duplicada**, e a
margem medida é de 2 segundos em 120.

Ou seja: a saída óbvia para o item 1 ativa um bug latente. As duas coisas
precisam ser resolvidas na mesma mudança.

---

## 3. Capacidade de atendimento: o pool de 5

`backend/db.py` cria o pool com `max_size=5`.

Cada tela do painel dispara 2 a 3 chamadas ao backend (`/metrics/…`,
`/segmentation/abc`, `/segmentation/cohort`), e cada chamada toma uma conexão.
**Dois ou três vendedores navegando ao mesmo tempo saturam o pool** — e isso
antes de contar o worker, que também tira conexões dali.

Com 100 a 300 vendedores, mesmo com 2% deles online simultaneamente, são 2 a 6
pessoas concorrendo por 5 conexões e 0,1 de CPU.

---

## 4. Armazenamento sem retenção

Nada é apagado, nunca. E `orders` guarda o `raw_json` inteiro do Mercado Livre.

| medição | valor |
| --- | --- |
| Peso por pedido | **~2,4 KB** (dominado por `raw_json`) |
| Pedidos do vendedor real | ~1.200 em 6 meses |
| Linhas de visita por dia por vendedor | **54** (medido sobre 156 dias) |

**Projeção a 300 vendedores:** ~1,7 GB/ano de pedidos + ~1,2 GB/ano de visitas
≈ **3 GB/ano, crescendo para sempre**. O plano gratuito do Supabase são 500 MB
— estoura entre 30 e 50 vendedores, muito antes dos 100.

---

## 5. Limite de taxa do Mercado Livre — MEDIDO em 2026-10-21

A spec de visitas mandava, em negrito, "confirmar os dois limites com token
real antes de implementar", e isso nunca tinha sido feito. Foi feito agora.

**A documentação é um beco sem saída:** tanto
`developers.mercadolibre.com.ar/en_us/visits-resource` quanto o devsite de
Global Selling respondem **403** a acesso automatizado. O limite só se descobre
medindo.

**O que a API diz, perguntada diretamente:**

| pergunta | resposta medida |
| --- | --- |
| Anuncia orçamento em cabeçalho? | **Não.** Nenhum `X-RateLimit-*`, `RateLimit-*` ou equivalente. |
| Latência por chamada | 181 ms mediana, 250 ms p95 |
| Taxa em série | 5,0 req/s |
| Taxa com concorrência 5 | **25,8 req/s, sem nenhum 429** |
| Teto real | **acima de 25,8 req/s** — não foi alcançado, e não insisti |

**Não existe endpoint de visitas por item em lote.** Isto foi testado a fundo,
porque seria a correção mais valiosa possível:

- `/visits/items?ids=A,B,C` → 400, **"maximum amount of items to query is 1"**
- `/items/visits?ids=…` → mesmo erro, mesmo com a data no formato certo
- `/users/{id}/items_visits?date_from=&date_to=` → **200**, mas devolve só o
  TOTAL da loja (`total_visits`, `visits_detail` por *company*), sem quebra por
  item. Serve para um indicador de visitas da loja, não para o funil.

O formato de data que esses endpoints aceitam é **só a data** (`2026-10-14`).
`Z`, offset com e sem dois-pontos, e ISO sem fuso são todos recusados com
"unknown date format".

**Conclusão:** uma chamada por item é inevitável com a API atual. Mas a 25,8
req/s isso deixa de ser o gargalo que este documento imaginava.

---

## 6. Porta aberta: demo pública sem limite

Seis endpoints `GET` em `/demo/*` sem autenticação nenhuma, e **nenhuma
limitação de taxa em lugar nenhum da API** (sem `slowapi`, sem middleware).

Numa instância gratuita de 0,1 CPU, qualquer pessoa com `curl` derruba a
operação inteira — inclusive o painel dos vendedores pagantes, porque é o mesmo
processo.

---

## 7. Operação às cegas

- **Sem rastreamento de erro.** Nenhum Sentry ou equivalente. Com 300
  vendedores, você descobre que quebrou porque alguém reclama.
- **Sem health check no Render.** O serviço tem `/health` no código, mas o
  campo `healthCheckPath` do serviço está **vazio** — o Render não monitora
  nada, e uma instância travada fica "no ar" indefinidamente.
- **Sem alerta de job falhado.** `sync_jobs` registra `status = 'error'` e
  ninguém olha. Hoje são 0; com 300 vendedores haverá falhas diárias normais
  (token expirado, 429, item removido).
- **Migrations no sistema de honra.** `APLICADAS.tsv` é escrito à mão, e o
  próprio arquivo admite: "não garante que ninguém minta".

---

## 8. Conexão com o Mercado Livre expira em silêncio

O token é renovado sob demanda, quando um job roda. Vendedor que fique tempo
suficiente sem sincronizar tem o refresh token expirado, e a conexão morre —
**sem nada avisar nem ele nem você**. Com 300 vendedores, uma fatia deles estará
permanentemente desconectada sem saber.

Relacionado: sem sincronização agendada, dado só atualiza quando alguém abre o
painel, e a tela mostra o estado antigo enquanto o job roda, sem dizer que está
rodando.

---

# Backlog para operar em escala

Ordenado por **o que destrava o resto**, não por esforço.

## Bloco A — descobrir o teto (antes de construir qualquer coisa)

1. **Medir o limite real da API do ML com token de produção.** Quantas
   chamadas por minuto e por dia a aplicação aguenta. Tudo no bloco B depende
   deste número, e ele pode mudar o produto (ex.: visitas viram semanais em vez
   de diárias). É o item mais barato e o de maior consequência.

## Bloco B — tirar a ingestão de dentro da API

2. **Worker em serviço próprio**, com `WORKER_IN_PROCESS=0` na API. Separa a
   competição por CPU e permite escalar os dois de forma independente.
3. **Consertar o lease antes de ter mais de um worker.** Lease proporcional ao
   trabalho restante, ou renovação por item em vez de por janela. Sem isto,
   dois workers ingerem o mesmo período em paralelo.
4. **Colheita de visitas por prioridade, não catálogo inteiro.** Item sem venda
   recente não precisa de colheita diária. Só isto corta as ~295.500
   chamadas/dia para uma fração, e adia tudo que vem depois.
5. **Concorrência com orçamento de taxa.** Chamadas em paralelo com semáforo
   dimensionado pelo número do item 1.
6. **Distribuir os vendedores ao longo do dia** em vez de uma rajada única —
   suaviza o limite de taxa e o uso de CPU.

## Bloco C — aguentar o atendimento

7. **Subir `max_size` do pool** e dimensionar com o plano do Postgres. Hoje são
   5 para tudo.
8. **Limitar taxa na API**, com teto mais apertado nos endpoints públicos de
   `/demo/*`.
9. **Cache nas respostas analíticas.** O dado muda uma vez por sincronização;
   hoje toda visita à tela recalcula tudo no banco.

## Bloco D — parar de crescer sem limite

10. **Política de retenção.** Definir por quanto tempo `raw_json` precisa
    existir — ele é o grosso dos 2,4 KB por pedido. Provavelmente dá para
    descartar após a ingestão, ou mover para armazenamento frio.
11. **Plano pago no Supabase** antes dos ~30 vendedores, que é onde os 500 MB
    gratuitos acabam.

## Bloco E — enxergar o que acontece

12. **Rastreamento de erro** (Sentry ou similar) no backend e no front.
13. **Configurar `healthCheckPath` para `/health`** no Render. É um campo de
    formulário, e hoje está vazio.
14. **Alerta de job em erro** e de vendedor com token expirado.
15. **Avisar o vendedor quando a conexão com o ML cair**, em vez de deixar a
    conta silenciosamente parada.

## Bloco F — produto

16. **Sincronização agendada** (ver avaliação separada). Com worker próprio,
    vira agendamento interno e não precisa de gatilho externo.
17. **Mostrar o estado da sincronização na tela**, em vez de renderizar dado
    velho sem avisar.

---

## O que eu faria primeiro, se fosse um item só

**O item 1.** Não é código, é uma tarde de medição com token real — e define se
o bloco B é "ajustar concorrência" ou "repensar a frequência das visitas".
Construir o bloco B sem esse número é escolher a arquitetura no escuro.

## Sobre urgência

Nada nesta lista está sangrando hoje. Com 2 vendedores, o sistema está
dimensionado com folga, e o maior risco real é o do **bloco E**: você já opera
sem enxergar, e isso custa barato para consertar agora.

Os blocos A e D são os que têm prazo: o limite do ML pode inviabilizar o
desenho atual, e os 500 MB do Supabase acabam por volta do trigésimo vendedor.
