# Agentes do SellerPulse

Seis agentes, versionados no repositório (`.claude/agents/`, não
`~/.claude/agents/`), porque eles carregam as convenções deste projeto e devem
viajar junto com o código.

| agente | quando usar |
| --- | --- |
| `revisor-de-codigo` | revisar diff ou feature: bugs, duplicação, simplificação |
| `auditor-de-escala` | mexeu em ingestão, fila, worker ou consulta por vendedor |
| `revisor-de-interface` | criou ou alterou tela, componente ou vitrine |
| `guarda-de-banco` | migration, tabela, índice ou policy de RLS |
| `verificador-de-entrega` | depois de mergear ou aplicar algo que precisa chegar em produção |
| `cacador-de-duplicacao` | varredura ampla de código morto e duplicado |

**Agente novo só é registrado ao reiniciar a sessão.** Criar o arquivo não
basta.

## Como eles entram no trabalho

Quem chama os agentes é a skill **`/entregar`** (`.claude/skills/entregar/`),
no passo de revisão, escolhendo pelos caminhos que o diff toca. Os agentes só
leem e julgam; quem escreve é a sessão principal. Quem gera não julga.

Os quatro revisores (`revisor-de-codigo`, `revisor-de-interface`,
`guarda-de-banco`, `auditor-de-escala`) terminam todo relato com
`**Veredito:** bloqueia o merge` ou `não bloqueia`. Só bloqueia o que afeta
correção ou requisito; preferência vai em "Opcional".

**Modelo por papel:** a varredura (`cacador-de-duplicacao`) e a conferência de
deploy (`verificador-de-entrega`) rodam em `sonnet`, porque o trabalho delas é
procurar e comparar. Os revisores herdam o modelo da sessão, porque é neles que
o julgamento pesa.

## Por que estes, e não os 318 do `agency-agents`

A origem foi o repositório [`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents)
(MIT, 423 commits, ativo). Ele foi avaliado em 2026-10-22 e **não** foi
instalado como vem. Três razões, todas medidas:

**O formato não é o do Claude Code, apesar de o README afirmar que é.** De 287
agentes com campo `name`, **exatamente 1** tem nome válido em kebab-case: 279
têm espaço e 285 têm maiúscula. O `name` é o que vira `subagent_type`. O
frontmatter também traz `color`, `emoji` e `vibe`, que o Claude Code ignora, e
a `description` é escrita como personalidade ("Reviews code like a mentor") em
vez de instrução de roteamento ("Use este agente quando…") — que é o que
determina quando o agente é acionado.

**94% não restringem ferramentas.** Só 17 de 318 declaram `tools:`. Os demais
herdam o conjunto completo, incluindo `Write`, `Edit` e `Bash`. Um agente
chamado "code reviewer" com permissão de reescrever o repositório é um risco
que não se paga. Os agentes daqui declaram `tools` explicitamente, e os de
revisão não escrevem arquivo.

**Instalar todos seria pior que não instalar nenhum.** A `description` de cada
agente é carregada para decidir roteamento. 318 descrições — de GIS, saúde,
desenvolvimento de jogos, marketing acadêmico — custam contexto em toda sessão
e pioram a escolha do agente certo. Mais agente não é melhor; agente que não
corresponde à operação é ruído com custo fixo.

**E o conteúdo é genérico por natureza.** O valor deste projeto está no que foi
aprendido doendo: nunca inventar número, ausência não é zero, função não
atravessa a fronteira RSC, o banco de teste nasce completo e produção não,
medir onde vai rodar e não onde é conveniente. Um agente genérico não sabe
nada disso — e, pior, contradiz parte.

O que foi aproveitado de lá foi a **estrutura** do `design-ui-finish-gate-reviewer`
(contrato de design, checklist de estados, "evidência antes de opinião"), que
tem substância real. O `design-ux-architect`, de 482 linhas, é boilerplate com
placeholders (`--primary-color: [spec-primary]`) e não entrou.

## Para adicionar um agente novo

1. `name` em kebab-case — é o identificador, não o rótulo.
2. `description` dizendo **quando** acionar, com um ou dois exemplos.
3. `tools` explícito. Agente de revisão não precisa de `Write` nem `Edit`.
4. Corpo específico deste projeto. Se o texto serviria em qualquer repositório,
   ele não vale o contexto que custa.
