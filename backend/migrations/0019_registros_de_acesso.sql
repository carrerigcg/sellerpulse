-- backend/migrations/0019_registros_de_acesso.sql
-- DDL portatil: roda no Supabase E no banco de teste.
--
-- Desenho em docs/specs/2026-10-30-registro-de-acesso-design.md.

-- Marco Civil, art. 15: data, hora e IP de uso da aplicacao, por 6 meses. Sem
-- chave estrangeira de proposito: o registro precisa sobreviver a exclusao da
-- conta, e o cascade o levaria junto. Uma linha por usuario, IP e hora.
create table registros_de_acesso (
    user_id uuid        not null,
    ip      text        not null,
    hora    timestamptz not null,
    primary key (user_id, ip, hora)
);

-- A limpeza dos vencidos filtra por data.
create index idx_registros_de_acesso_hora on registros_de_acesso (hora);

-- Nasce fechada, como a 0018: tabela nova em public vem aberta para a chave
-- publica, e aqui o que se forjaria tem valor de prova.
alter table registros_de_acesso enable row level security;
