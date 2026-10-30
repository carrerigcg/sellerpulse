# Registro de acesso à aplicação

Estado: no ar desde 2026-10-30 (#39). Falta conferir uma linha real gravada e o IP atrás do proxy do Render.

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
- **Guarda a cadeia inteira do `X-Forwarded-For`**, como a prova do aceite. Passando de 256
  caracteres, corta o começo, que o cliente controla, e fica o elo do proxy.
- **O navegador tenta a cada 5 minutos**, ao trocar de tela e ao voltar para a aba. O
  backend ignora a repetição; o intervalo curto pega a virada da hora e a troca de IP.
- **A limpeza tem 1 hora de folga**, porque `hora` guarda o começo do período.

## Cobertura

`/dashboard`, `/aceite`, `/assinar`, `/assinar/retorno` e `/planos`, onde chega quem tem o
plano vencido. Em `/planos`, o visitante sem sessão não gera registro. O login é do
Supabase, e o log dele dura 1 dia no plano gratuito.

O domínio próprio precisa entrar em `CORS_ORIGINS`: sem isso, o registro para sem aviso.

## Fora desta spec

- Registrar cada navegação: o art. 15 pede data, hora e IP, não o caminho percorrido.
- Limite contra `X-Forwarded-For` forjado: cada valor gera uma linha, então quem tem conta
  pode inflar a tabela. Aceito enquanto o produto não é divulgado; limitar por hora poderia
  perder um IP legítimo. Rever antes de abrir o cadastro em escala.
