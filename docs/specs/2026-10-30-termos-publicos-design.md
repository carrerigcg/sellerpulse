# Termos de Uso e Política de Privacidade publicados

Estado: no ar desde 2026-10-30 (#37); pendências da revisão fechadas em 2026-11-03 (#44). Um teste recusa o texto enquanto houver
`[DADO: ...]`. Publicar não abre as vendas.

## Por quê

O aceite é de um rascunho sobre um resumo, e o texto completo não existe no site. O
Guilherme pediu para implementar os termos reais logo depois de fechar as vendas
(2026-10-30).

## Decisões travadas

1. **O texto mora no front**, em `frontend/content/legal/`, e é renderizado em
   `/termos` e `/privacidade`, páginas públicas.
2. **A versão é uma só.** `VERSAO_DOS_TERMOS` (`backend/planos.py`) aparece nos dois
   textos, e um teste do backend falha se divergirem. Mudar a versão pede novo aceite
   de todos.
3. **Dado pendente bloqueia a publicação.** Um teste do front falha com `[DADO: ...]`
   no texto: nome, documento e endereço nunca são preenchidos com suposição.
4. **O aceite aponta para o texto completo**, em `/aceite` e `/assinar`, e o rodapé da
   vitrine leva às duas páginas.
5. **Publicar não abre as vendas.** Elas só abrem na etapa 14 do plano, depois da
   revisão do advogado e das etapas que tornam o texto verdadeiro.

6. **CPF e endereço do titular não vão para o site nem para o repositório**
   (Guilherme, 2026-10-30). Um teste recusa CPF ou CNPJ no texto e a expressão
   "com endereço em".

## Decisões da revisão

- **Quem não aceitar** cancela na própria tela de aceite, porque o painel fica
  bloqueado e a cobrança continuaria. Esse período não dá acesso: o texto antes
  prometia o contrário.
- **Desconectar sem acesso ao painel, trocar o plano anual e cancelar o anual sem
  aceitar** são feitos pelos canais de contato,
  porque não há tela para isso.
- **"Não guardamos nome do comprador" foi medido em produção** (2026-10-30): em 2.071
  pedidos, `raw_json->'buyer'` só tem `id` e `nickname`.

## Pendências da revisão

Resolvidas em 2026-11-03:

- Em `/aceite`, o cancelamento tem texto próprio (o painel segue fechado sem o aceite) e,
  depois de cancelar, a tela troca o "plano ativo" pelo prazo que sobrou.
- O resumo diz que o acesso até o fim do período pago depende dos termos vigentes aceitos,
  como a seção 14 dos Termos.
- Mensal sem assinatura localizada no Asaas: se o cliente é conhecido e o Asaas não tem
  assinatura ativa, o cancelamento encerra aqui também; sem o cliente, a recusa diz para
  falar com a gente, e nada é marcado como cancelado.
- `sync-todos` só sincroniza quem aceitou a versão vigente, como o callback e o `/ml/sync`.

Continua com o advogado: o destino do valor pago de quem tem plano anual e recusa uma
versão nova.

## Identificação do fornecedor e nota fiscal

- **Advogado (2026-10-30):** leu os textos e aprovou. Sem CPF nem CNPJ no site por
  enquanto; o CNPJ entra quando o faturamento crescer, com endereço comercial. Isso tira
  o Decreto 7.962/2013, art. 2º, da lista do que trava a abertura das vendas.
- **Nota fiscal (2026-10-30):** recibo por e-mail agora, em nome da pessoa física; nota
  automática pelo Asaas quando o CNPJ abrir. O contador confirma a data de 2027 em São
  Paulo. A cláusula 7.8 dos Termos segue genérica ("segue a legislação") até lá.

## Compromissos do texto que o sistema ainda não cumpre sozinho

Valem a partir da abertura das vendas, e por isso são pré-requisito dela:

| compromisso | onde será cumprido |
| --- | --- |
| Premium fora da venda | etapa 2 do plano |
| Exclusão em até 30 dias, guardando a prova do aceite | etapas 4 e 7 |
| Token apagado 30 dias depois do fim do plano; dados em 12 meses | etapa 8 |
| Registros de acesso por 6 meses | etapa 3 mede; ajustar se faltar |
| Lembretes de cobrança, se o advogado exigir | etapa 9 |

## Fora desta spec

- A revisão jurídica, que pode mudar o texto e gerar uma versão nova.
