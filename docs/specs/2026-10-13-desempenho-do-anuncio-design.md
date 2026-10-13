# SellerPulse — Desempenho do anúncio: visitas e conversão

**Data:** 2026-10-13
**Status:** Design aprovado — implementação pendente.

---

## 1. Contexto

O SellerPulse responde hoje **quanto** cada produto vendeu. Não responde **por que** não vendeu mais.

São dois produtos com a mesma receita e histórias opostas: um com mil visitas e dez vendas, outro com trinta visitas e dez vendas. O primeiro tem um problema de anúncio — preço, foto, título. O segundo tem um problema de tráfego. A curva ABC os classifica igual, porque só enxerga o fim do funil.

Visitas fecham o funil: **visitas → vendas = conversão.** É a métrica que transforma "este produto vendeu pouco" em "este produto não é visto" ou "este produto é visto e rejeitado" — duas ações completamente diferentes.

Os dois concorrentes têm. A AvantPro lista *"Métricas do anúncio com gráfico de visitas e conversão"*; a JoomPulse vende funil de oferta no plano de R$ 332.

## 2. A restrição que define o desenho

**Visita é dado perecível.** Esta é a diferença estrutural em relação a tudo que o sistema ingere hoje.

Pedido o Mercado Livre guarda para sempre: dá para pedir o histórico de seis meses a qualquer momento, e é o que o backfill faz. Visita, não:

| | Pedido | Visita |
|---|---|---|
| Janela consultável | ilimitada | **150 dias** |
| Atraso | nenhum | **~48 h** |
| Granularidade | evento | único por dia, por item |

Fonte: [documentação de visitas do Mercado Livre](https://developers.mercadolibre.com.ar/en_us/visits-resource) e [Global Selling](https://global-selling.mercadolibre.com/devsite/visits). **Confirmar os dois limites com token real antes de implementar** — as páginas são antigas e o portal muda.

Três consequências, e elas mandam no resto da spec:

1. **Não existe backfill de verdade.** Dá para pegar 150 dias no primeiro sync, e é só isso que vai existir para sempre daquele período.
2. **Se não colher, perde.** Quem conectar a conta hoje e sincronizar daqui a seis meses perdeu os primeiros quatro.
3. **Os últimos dois dias são sempre incompletos.** Conversão de ontem é mentira; a tela precisa saber disso.

## 3. Goals & non-goals

### Goals

- Tabela `item_visits`: visitas por `(seller_id, item_id, dia)`.
- Job `visitas` na fila, com retomada por cursor como o backfill já faz.
- Primeiro sync captura os **150 dias** disponíveis; os seguintes capturam o delta.
- A tela **Produtos** ganha visitas e conversão por produto.
- **Os dois dias incompletos ficam visíveis**, nunca apresentados como fechados.

### Non-goals

- **Perguntas dos compradores.** São parte do funil e merecem ser ingeridas, mas são outra API, outro volume e outra tela.
- **Visitas por origem** (busca, categoria, anúncio pago). O ML separa por `company`; não nesta versão.
- **Investimento em Ads e ROI.** Outra API, com autorização própria. É a terceira da varredura, não esta.
- **Alerta de queda de conversão.** Depende desta feature e é a próxima.
- **Conversão na demonstração baseada em dado real.** A demo é sintética; ver seção 8.

## 4. Decisões travadas

1. **Job próprio, não encaixado no delta de pedidos.** Visitas têm cadência, limite e modo de falha diferentes. Um 429 no endpoint de visitas não pode atrasar a ingestão de pedidos, que é o dado que sustenta todas as telas.
2. **Granularidade diária por item.** É o que a API entrega e o que a tela precisa.
3. **Guardar o que veio, não recalcular.** A tabela guarda visitas; conversão é derivada na consulta. Conversão gravada ficaria velha quando um pedido chegasse atrasado.

## 5. Modelo de dados

```sql
-- backend/migrations/0009_visitas_do_anuncio.sql
create table item_visits (
    seller_id  uuid not null references sellers(id) on delete cascade,
    item_id    text not null,
    dia        date not null,
    visitas    integer not null check (visitas >= 0),
    colhido_em timestamptz not null default now(),
    primary key (seller_id, item_id, dia)
);

create index on item_visits (seller_id, dia);

alter table sync_jobs drop constraint sync_jobs_kind_check;
alter table sync_jobs add constraint sync_jobs_kind_check
    check (kind in ('backfill','delta','visitas'));
```

> **O nome da constraint não está no código.** Em `0004_ml_tokens_e_fila.sql` ela é declarada em linha (`kind text not null check (...)`), então quem nomeia é o Postgres: `tabela_coluna_check`, ou seja, `sync_jobs_kind_check`. A regra vale enquanto houver um único check naquela coluna — com dois, o segundo vira `..._check1`. Confirmar com `\d sync_jobs` antes de rodar; um `drop constraint` com nome errado derruba a migration no deploy, não no teste.

**`colhido_em` não é enfeite.** Um dia colhido dentro da janela de 48 h pode estar subcontado. Guardando quando foi colhido, dá para recolher os dias cujo `colhido_em` é próximo demais do `dia` — sem ele, não há como distinguir "teve 3 visitas" de "colhi cedo demais".

**Upsert por `(seller_id, item_id, dia)`:** recolher um dia **substitui**. Visita é contagem fechada, não evento acumulável; somar duplicaria.

**Dia sem linha significa zero visitas**, e não há linha com `visitas = 0` por item por dia — seriam dezenas de milhares de linhas sem informação. Quem consulta trata a ausência como zero.

## 6. A ingestão

Endpoint por item: `GET /items/{item_id}/visits/time_window?last=N&unit=day&ending=YYYY-MM-DD`, via o `MLClient` que já existe (`src/ml_client.py`), com o mesmo tratamento de 429 e backoff.

**Uma chamada por item.** É o custo real desta feature: um vendedor com 50 produtos ativos são 50 chamadas por sincronização. Por isso o job é próprio e tem cursor.

```
Job `visitas`:
  itens = select distinct item_id from order_items where seller_id = $1
  para cada item (retomando do cursor):
      janela = 150 dias no primeiro sync, ou (último dia colhido − 2) até hoje
      resposta = ML /items/{item}/visits/time_window
      upsert em item_visits
      grava o cursor a cada item
```

**Por que `último dia colhido − 2`:** reconsultar os dois últimos dias é o que corrige o subcontagem da janela de 48 h. O upsert torna isso seguro — é substituição, não soma.

**Por que a lista de itens vem de `order_items` e não do catálogo do ML:** porque o produto que nunca vendeu não tem conversão para calcular, e buscar o catálogo inteiro multiplicaria as chamadas sem responder nenhuma pergunta da tela. **Consequência aceita e registrada:** um produto com muitas visitas e **zero** vendas não aparece — e esse é justamente um caso interessante ("é visto e ninguém compra"). Fica para a versão que cruzar com o catálogo; está na seção 10.

**Agendamento.** O job é enfileirado junto com o `delta`, porque o Render hiberna e não existe cron. A sincronização que já acontece é o único momento garantido. Enfileirado, não executado inline: o worker drena a fila.

## 7. O que a tela mostra

A tela **Produtos** ganha duas colunas na tabela ABC:

| Classe | Produto | Receita | Unidades | Visitas | Conversão |
|---|---|---|---|---|---|
| A | Luminária LED 50W | R$ 138.747 | 412 | 8.930 | 4,6% |
| B | Capacete X | R$ 61.487 | 203 | 11.402 | 1,8% |

`conversão = unidades vendidas ÷ visitas` no mesmo período.

**É uma aproximação, e a tela diz isso.** Um pedido com três unidades do mesmo item é uma visita que converteu, não três. A métrica honesta seria pedidos ÷ visitas; a útil para quem decide estoque é unidades. **Decisão: mostrar unidades ÷ visitas, com o rótulo "conversão (unidades)"** e o detalhe no tooltip. Inventar um número sem dizer qual é seria repetir o erro do custo estimado.

**Os dois dias incompletos.** Toda janela que inclui ontem ou anteontem mostra:

> *Visitas dos últimos 2 dias ainda estão sendo consolidadas pelo Mercado Livre.*

**Produto sem visita colhida** mostra "—", nunca 0%. Zero por cento é uma afirmação; traço é a ausência dela. É a mesma regra do custo de produto.

## 8. A demonstração

O gerador sintético não produz visitas. Sem elas, a vitrine mostraria uma coluna vazia e a feature pareceria quebrada — foi exatamente o que aconteceu com os cartões em R$ 0 em outubro.

`src/demo_data.py` passa a gerar visitas por item e por dia, com conversão plausível por classe ABC (classe A converte mais que C, que é o que acontece de verdade). Isso obriga a regerar `data/demo.db`, o golden do PDF e o sentinela de tamanho — como sempre que o gerador muda.

## 9. Testes

- **A janela de 48 h:** um dia colhido dentro dela é recolhido na sincronização seguinte e o valor é **substituído**, não somado. Mutação: trocar o upsert por insert e ver o teste quebrar.
- **Ausência não é zero:** item sem linha no dia aparece como "—" na tela e não entra como zero no cálculo de conversão.
- **Cursor:** job interrompido no meio retoma do item seguinte, não do começo.
- **Isolamento:** visitas de outro vendedor nunca entram.
- **Teto de 150 dias:** a janela pedida ao ML nunca excede o limite, mesmo quando a conta tem um ano de pedidos.
- **Paridade:** sem nenhuma visita colhida, a tela Produtos devolve exatamente os números de hoje.

## 10. Próximas, nesta ordem

1. **Produtos com visita e zero venda** — cruzar com o catálogo do ML.
2. **Perguntas dos compradores**, completando o funil.
3. **Alerta de queda de conversão**, que depende desta.
4. **Visitas por origem**, se alguém pedir.
