-- backend/migrations/0026_token_de_ia_fora_da_api_de_dados.sql
-- SÓ no Supabase: depende de `auth.jwt()`, como a 0002. Não entra no banco de
-- teste (ver `backend/scripts/setup_test_db.py`).
--
-- Spec: docs/specs/2026-11-09-premium-mcp-conta-real-design.md, decisão 4.
--
-- O token que o servidor OAuth do Supabase emite para um cliente de IA é um
-- JWT com `role: authenticated`, igual ao da sessão do site, mais a claim
-- `client_id`. As policies `own` destas tabelas são `for all`: sem esta
-- migration, o cliente de IA (ou quem pegasse o token dele) gravaria e
-- apagaria pedidos e custos pela API de dados do Supabase (PostgREST), e a
-- tela de consentimento promete que ele só lê. O front não usa a API de
-- dados; quem lê para a IA é o backend, pelo MCP, que não passa por RLS.
--
-- `as restrictive`: soma às policies que já existem como um E, então a
-- sessão do site (sem `client_id`) continua exatamente como antes.

create policy sem_token_de_ia on orders as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null)
    with check ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on order_items as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null)
    with check ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on items_cache as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null)
    with check ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on categories_cache as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null)
    with check ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on claims as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null)
    with check ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on product_costs as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null)
    with check ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on item_visits as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null)
    with check ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on shipment_costs as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null)
    with check ((auth.jwt() ->> 'client_id') is null);

-- As de leitura também: o que a IA lê passa pelo MCP, com plano, histórico e
-- registro de acesso. Pela API de dados ela leria sem nenhum dos três.
create policy sem_token_de_ia on sellers as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on sync_jobs as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on assinaturas as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on aceites_de_termos as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null);
create policy sem_token_de_ia on registros_de_acesso as restrictive for all
    using ((auth.jwt() ->> 'client_id') is null);
