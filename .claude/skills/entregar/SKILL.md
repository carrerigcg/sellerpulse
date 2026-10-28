---
name: entregar
description: Use para levar uma mudança do SellerPulse do pedido até a produção — feature, correção ou mudança de banco. Organiza spec, branch, implementação com teste de mutação, verificação, revisão por agentes de contexto limpo, merge pelo fluxo certo e conferência do deploy. Acione quando o Guilherme pedir para implementar, corrigir ou "seguir com" um item; não para pergunta, investigação ou varredura.
---

# Entregar uma mudança no SellerPulse

Este é o orquestrador do projeto. Ele não substitui o `AGENTS.md` (regras) nem
o `docs/operacao.md` (como fazer cada passo): ele diz **em que ordem** e **o que
precisa estar provado** antes de passar para o passo seguinte.

Quem escreve é a sessão principal, uma tarefa por vez. Os agentes de
`.claude/agents/` só leem e julgam: quem gera não julga.

## 0. Antes de começar

- **Confirme o escopo em uma frase**, e o que fica de fora. Se o pedido
  esconder uma decisão de negócio (qual número entra na conta, o que a tela
  afirma), pergunte com opções numeradas e a sua recomendação. Não decida
  sozinho.
- **Leia o que a mudança vai tocar** antes de propor. O código é a verdade;
  spec e memória podem estar velhas.
- **Precisa de dado de produção?** Leitura (SQL de leitura, consulta GET) é
  livre. Escrita, ou uso do token do ML, pede o ok dele (`docs/operacao.md`,
  seção 6).

## 1. Spec (feature ou mudança de regra)

Correção pequena e óbvia dispensa spec. Feature, regra de número nova ou
mudança de banco não dispensa: escreva `docs/specs/AAAA-MM-DD-<nome>-design.md`
com as decisões travadas e o porquê, a linha `Estado:` no topo e uma seção do
que ficou de fora. Se a decisão saiu de uma medição, a medição vai na spec.

## 2. Branch

- Só front-end: pode ir direto na `main`, depois de lint e build locais.
- Back-end, `src/`, workflows, migrations ou harness: branch e PR.
- Nunca comece em cima de árvore suja que não é sua. Confira `git status`.

## 3. Implementação, com teste que cai

Para cada regra nova:

1. Escreva o teste e veja ele **falhar pelo motivo certo**.
2. Implemente.
3. **Mutação:** copie o arquivo para fora do repo, quebre a regra, confirme
   com `diff --strip-trailing-cr` que a quebra foi aplicada, veja o teste
   cair, e restaure **da cópia** (`docs/operacao.md`, seção 3). O guarda nega
   `git checkout --` em arquivo sujo; não contorne.

Teste escrito depois do código passa de primeira e não prova nada até a
mutação ser feita.

## 4. Verificação

```bash
backend/.venv/Scripts/python.exe scripts/verifica.py
```

Tem que terminar em "tudo verde". Se ele avisar que nenhum teste cita o `.py`
que mudou, isso é um buraco: escreva o teste ou explique por que não cabe.

**Mudou algo que aparece numa tela?** Abra a página: `backend-teste` +
`frontend`, em aba própria, com o cache de fetch do Next limpo
(`docs/operacao.md`, seção 2). Lint e build não renderizam as rotas
dinâmicas. Confira o número na tela contra a conta feita à mão.

## 5. Revisão por contexto limpo

Escolha os revisores pelos caminhos que o diff toca, e dispare os que se
aplicarem **em paralelo**, passando a branch, o objetivo em uma frase e a
spec, se houver:

| o diff toca | agente |
| --- | --- |
| qualquer código | `revisor-de-codigo` (sempre) |
| `backend/migrations/`, tabela, índice, policy | `guarda-de-banco` |
| `backend/ml/`, `backend/worker/`, `backend/jobs/`, consulta por vendedor | `auditor-de-escala` |
| `frontend/app/`, `frontend/components/`, vitrine | `revisor-de-interface` |

Cada um termina com `**Veredito:** bloqueia o merge` ou `não bloqueia`.

- **Bloqueia:** confira o achado, porque o revisor também erra. Se for real,
  corrija, volte ao passo 4 e revise de novo só o que mudou. Se não for,
  registre no PR por que não é.
- **Opcional:** não entra nesta entrega. Se valer a pena, vira pendência na
  spec.

## 6. PR e merge

- O PR diz o porquê, o quê, e **o que foi provado e como**, incluindo o que
  não foi provado. O título e o commit vão em português, no estilo
  conventional.
- **Migration:** a ordem do `docs/operacao.md`, seção 4. Com o ok do
  Guilherme, aplique em produção, registre no `APLICADAS.tsv` e só então o CI
  fica verde.
- **Merge só com CI verde e com o ok dele.** Use squash.

## 7. Depois do merge

Dispare o `verificador-de-entrega`, ou confira você mesmo: o commit `live` no
Render e um marcador que só a versão nova tem, na Vercel
(`docs/operacao.md`, seção 5). Atualize a linha `Estado:` da spec.

## 8. Relato

Para o Guilherme, em português, curto:

- o que mudou para o vendedor;
- o que foi provado, e como;
- o que **não** foi provado;
- o que ficou pendente.

Se algo deu errado no caminho, diga o que foi e como foi corrigido. Se for
uma armadilha nova, ela vai para o `AGENTS.md` ou para o `docs/operacao.md`,
e não para a memória.
