-- backend/migrations/0018_cobranca.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- Desenho em docs/specs/2026-10-29-cobranca-asaas-design.md.

-- O acesso passa a ter prazo. Cada pagamento confirmado empurra `acesso_ate`
-- para o fim do periodo pago mais a tolerancia; sem pagamento, o prazo vence
-- sozinho, e nenhum agendador precisa desligar ninguem. Nulo = sem prazo: os
-- planos dados a mao (origem `manual`) continuam assim.
alter table assinaturas
    add column acesso_ate             timestamptz,
    -- Fim do periodo ja pago, SEM a tolerancia. E ate onde vale o acesso de
    -- quem cancela (decisao 5 da spec).
    add column pago_ate               timestamptz,
    add column ciclo                  text check (ciclo in ('mensal', 'anual')),
    add column asaas_cliente          text,
    add column asaas_assinatura       text unique,
    -- Cancelou: a recorrencia acabou, e o acesso vai ate `pago_ate`, sem a
    -- tolerancia. Um pagamento atrasado de periodo antigo que chegue depois
    -- nao devolve a tolerancia a quem cancelou.
    add column cancelada_em           timestamptz,
    -- Downgrade vale no proximo ciclo: guardado aqui ate o proximo pagamento.
    add column plano_no_proximo_ciclo text
        check (plano_no_proximo_ciclo in ('essencial', 'exclusive', 'premium')),
    -- O checkout que ativou a assinatura ATUAL. E o elo com o Asaas: o
    -- pagamento e a assinatura trazem `checkoutSession` (medido no sandbox),
    -- e um evento de um checkout ANTIGO (de quem cancelou e recontratou) nao
    -- toca a linha da assinatura nova.
    add column checkout_id            text unique;

-- Cada checkout criado, e de quem ele e. O webhook do Asaas fala de checkout,
-- cobranca e assinatura; e por esta tabela que um checkout pago vira o plano
-- de um vendedor.
create table checkouts (
    id         text primary key,
    seller_id  uuid not null references sellers(id) on delete cascade,
    plano      text not null check (plano in ('essencial', 'exclusive', 'premium')),
    ciclo      text not null check (ciclo in ('mensal', 'anual')),
    criado_em  timestamptz not null default now(),
    -- Quando o plano foi ativado por este checkout. Uma vez so: e o que
    -- impede um aviso repetido, ou a renovacao, de reativar e desfazer um
    -- downgrade ou um cancelamento.
    pago_em    timestamptz,
    -- Os ids do Asaas, anotados por qualquer aviso que traga este checkout,
    -- na ordem em que chegarem (a fila do Asaas nao garante ordem).
    asaas_cliente     text,
    asaas_assinatura  text
);
create index idx_checkouts_seller on checkouts (seller_id);

-- Idempotencia do webhook. O Asaas entrega "pelo menos uma vez": o mesmo
-- evento pode chegar de novo, e um pagamento contado duas vezes empurraria o
-- prazo um periodo a mais. O payload fica para auditar depois.
create table eventos_do_gateway (
    id           text primary key,
    tipo         text not null,
    payload      jsonb not null,
    recebido_em  timestamptz not null default now()
);

-- RLS ligada AQUI, e nao numa migration separada como as outras: tabela nova
-- em `public` nasce com todos os privilegios para `anon` e `authenticated`, e
-- entre duas migrations as duas tabelas ficariam abertas pela chave publica.
-- Ligar a RLS sem policy roda tambem no banco de teste (so policy depende de
-- `auth.uid()`). Nenhuma policy: so o backend, que conecta como dono, le e
-- escreve. As colunas novas de `assinaturas` ja estao sob a policy de leitura
-- da 0017.
alter table checkouts enable row level security;
alter table eventos_do_gateway enable row level security;
