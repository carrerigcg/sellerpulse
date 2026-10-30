# Termos de Uso e Política de Privacidade publicados

Estado: em revisão. Um teste recusa o texto enquanto houver `[DADO: ...]`. Publicar
não abre as vendas.

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

## O que trava a abertura das vendas

O Decreto 7.962/2013, art. 2º, pede a identificação do fornecedor no site de comércio
eletrônico, com CPF ou CNPJ e endereço. Só com o nome, o texto pode não atender a essa
regra, e o advogado precisa dizer o que fazer. O caminho provável é um CNPJ com
endereço comercial, que entra aqui sem expor dados pessoais. A nota fiscal também está
sem definição do contador: o texto só diz que segue a legislação.

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
