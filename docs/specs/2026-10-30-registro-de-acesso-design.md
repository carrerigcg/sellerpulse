# Registro de acesso à aplicação

Estado: em revisão. Sai de `docs/legal/retencao-dos-fornecedores.md`, conflito 1.

## Por quê

O Marco Civil (art. 15) obriga a guardar data, hora e IP de uso por 6 meses, e a
Política promete isso. Nada guardava: o backend não grava acesso, e os logs dos planos
contratados duram de 1 hora a 7 dias.

## Decisões

- **Tabela própria**, sem custo novo (Guilherme, 2026-10-30).
- **Sai do navegador.** As telas chamam a API pelo servidor do front, e por lá o IP
  gravado seria o da Vercel.
- **Uma linha por usuário, IP e hora.** Basta para responder a uma ordem judicial, e o
  volume fica previsível.
- **Sem chave estrangeira:** o registro precisa sobreviver à exclusão da conta. Fica só
  o `user_id`, e sai aos 6 meses.
- **A limpeza roda ao gravar**, para não depender de agendador.
- **Guarda a cadeia inteira do `X-Forwarded-For`**, como a prova do aceite.

## Cobertura

`/dashboard`, `/aceite` e `/assinar`, as telas com sessão. O login é do Supabase, e o log
dele dura 1 dia no plano gratuito.

## Fora desta spec

- Registrar cada navegação: o art. 15 pede data, hora e IP, não o caminho percorrido.
