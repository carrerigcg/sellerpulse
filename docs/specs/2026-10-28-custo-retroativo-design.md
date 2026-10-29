# Custo de produto retroativo

Estado: em implementação (branch `feat/custo-retroativo`).

## Por quê

O custo de produto é o que transforma "venda" em "quanto sobra", e é a
promessa central da landing ("saber qual produto dá lucro"). Desde a spec de
2026-10-13, o custo informado vale **a partir de hoje**: as vendas anteriores
ficam "sem custo" para sempre.

Na avaliação de prontidão para vender (2026-10-28), isso apareceu como a
primeira experiência que frustra o vendedor. Ele chega, conecta a conta, vê
seis meses de histórico, informa os custos — e o histórico continua sem custo.
A promessa só aparece semanas depois, com as vendas novas. A conta real, um
mês depois de conectada, tem **zero** custos informados.

## Decisões travadas (com o Guilherme, 2026-10-28)

1. **Uma opção no topo da tela de Custos, ligada por padrão:** "Aplicar também
   às vendas anteriores sem custo". Ela vale para cada custo salvo enquanto
   estiver ligada. Uma caixinha por produto não serve para quem tem centenas
   de produtos.
2. **O retroativo só preenche o que está sem custo.** Um período com custo
   informado nunca é reescrito. Isso preserva a decisão 4 da spec de
   2026-10-13: corrigir o custo de hoje não pode mudar em silêncio a margem
   de um mês que já tinha custo.
3. **Como funciona no banco:** cada venda usa a última vigência que começou até
   a data dela, então "retroativo" é gravar também uma vigência no **início do
   histórico** (`VIGENCIA_DO_HISTORICO`, 01/01/2000). Ela cobre exatamente o
   que está antes do primeiro custo datado, e nada depois dele. Não há tabela
   nova nem migration.
4. **O início do histórico é preenchido uma vez só.** Depois, aquele período
   tem custo, e a decisão 2 vale para ele também. Por isso a opção pode ficar
   ligada para sempre: quando o fornecedor sobe o preço, o histórico não muda.
5. **A exceção é o mesmo dia.** Salvar de novo no mesmo dia atualiza o início
   do histórico gravado hoje, e esvaziar o campo desfaz tudo o que foi gravado
   hoje para aquele produto, inclusive o retroativo. A data de criação de cada
   linha (`criado_em`) diz o que foi gravado hoje. Assim, um erro de digitação
   com a opção ligada não fica preso no histórico.
6. **Sem a opção ligada, o comportamento é o de antes:** vale a partir de hoje.

## Limitação aceita

Um retroativo errado só é corrigível pela tela **no mesmo dia**. Depois disso,
corrigir exige a edição de histórico, que continua fora (ver abaixo). A tela
diz, no momento de salvar, que o custo foi aplicado também às vendas
anteriores, para o erro aparecer enquanto ainda dá para desfazer.

## Fora desta spec

- Editar o custo período por período (um valor para setembro, outro para
  outubro).
- Importar custos por planilha.
