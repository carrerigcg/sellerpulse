# Vendas fechadas até o texto final

Estado: em revisão (PR aberto). Sem efeito para quem já assina.

## Por quê

O checkout cobra de verdade, e o aceite é de uma versão "rascunho", sobre um
resumo, sem o texto completo publicado. Não há divulgação, mas qualquer pessoa pode
chegar à página. Até os termos finais existirem, ninguém deve conseguir contratar.

## Decisões travadas (Guilherme, 2026-10-30)

1. **Interruptor `VENDAS_ABERTAS`:** só `"1"` abre. Ausente = fechado, a mesma falha
   fechada dos segredos do projeto. Assim, o merge já fecha as vendas, sem precisar
   mudar nada no Render.
2. **A trava é no servidor**, em `POST /conta/checkout`, antes de gravar o aceite:
   ninguém aceita um texto para contratar algo que não vai acontecer.
3. **Só a contratação nova é fechada.** Cancelar, trocar de plano e o webhook
   continuam, porque quem assina não pode ficar preso numa cobrança.
4. **Duas leituras da mesma variável:**
   - no backend, ela decide. `GET /conta/acesso` informa o estado, e `/assinar` usa
     isso. Ligar só no Render permite uma compra de teste pelo endereço direto, sem
     mudar a vitrine;
   - na Vercel, ela só decide o que a vitrine mostra, para não mandar ninguém criar
     conta para algo fechado, e a landing não depender do backend para desenhar.
5. **Vitrine fechada:** os preços continuam visíveis, com "As vendas abrem em breve"
   e o botão "Quero saber quando abrir", que leva ao WhatsApp.

## Abrir as vendas

`VENDAS_ABERTAS=1` no Render e na Vercel, nessa ordem, depois da etapa de publicação
dos termos. Na Vercel, a variável nova só vale depois de publicar de novo.

## Fora desta spec

- Tirar o Premium da venda, que entra junto com o corte de histórico do Exclusive.
- Publicar os termos.
