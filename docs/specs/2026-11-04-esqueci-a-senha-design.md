# Esqueci a senha

Estado: em PR na branch `feat/esqueci-a-senha`. Falta trocar o modelo do e-mail no Supabase e o teste com um link de verdade.

## O pedido

O Guilherme pediu, em 2026-11-04, que quem esqueceu a senha consiga
recuperá-la sozinho. Hoje não há caminho nenhum: nem link no login, nem tela.

Escolheu a opção 1: construir agora com o remetente padrão do Supabase e ligar
o envio de verdade (Resend) quando o domínio sair.

## O que se sabia antes (lido em produção, 2026-11-04)

- `auth.users` tem 3 contas, e nenhuma tem `confirmation_sent_at` nem
  `recovery_sent_at`: o projeto nunca mandou um e-mail.
- Sem SMTP próprio, o Supabase só entrega para e-mails da equipe da
  organização. Para os outros endereços, o envio devolve o erro
  `email_address_not_authorized`.

## Decisões travadas

1. **Tudo pelo Supabase Auth, sem backend nem tabela nova.** A senha nova vira
   hash dentro do `auth.users`, gravado pelo próprio Supabase. Ninguém vê a
   senha.
2. **`/esqueci-senha`:** a pessoa digita o e-mail e a tela chama
   `resetPasswordForEmail`.
   - A resposta é a mesma com conta e sem conta ("se houver conta com esse
     e-mail, enviamos o link"), para não revelar quem é cliente. O próprio
     Supabase não envia nada quando o e-mail não tem conta.
   - **Exceção provisória:** `email_address_not_authorized` mostra que o envio
     ainda não está disponível e oferece o contato por e-mail. Dizer "enviamos"
     para quem nunca vai receber deixaria a pessoa esperando um e-mail que não
     chega. Custo aceito: até o Resend, esse erro só aparece quando a conta
     existe, o que revela a existência dela. São 3 contas e não há divulgação.
3. **O link do e-mail traz o código (`token_hash`) direto para o site**,
   `{{ .SiteURL }}/redefinir-senha?token_hash=...&type=recovery`, e a tela chama
   `verifyOtp`.
   - O link padrão do Supabase usa PKCE: só funciona no mesmo navegador que
     pediu. Quem pede no computador e abre o e-mail no celular cairia em erro.
   - Isso pede trocar o modelo do e-mail "Reset Password" no painel do
     Supabase. Configuração de produção: só com o ok do Guilherme.
   - O link usa o `SiteURL`, e não o `redirectTo`. Se o `redirectTo` não
     estiver na lista liberada, o Supabase troca em silêncio pelo `SiteURL` e
     o link quebraria. Com o `SiteURL`, a lista liberada não muda.
4. **`/redefinir-senha`:**
   - Sem `token_hash` com `type=recovery` na URL, mostra que o link não vale
     e oferece pedir outro. Não aceita trocar a senha só com uma sessão
     aberta: alguém num computador destravado trocaria a senha do dono.
   - O código vale uma vez. A tela confere uma única vez (o `useEffect` roda
     duas vezes em desenvolvimento) e tira o código da barra de endereço.
   - Link vencido ou já usado: diz isso e oferece pedir outro.
5. **Quem ativou o app autenticador passa pelo código antes da senha nova.**
   O link do e-mail abre uma sessão `aal1`, e o Supabase recusa trocar a senha
   nessa sessão (`insufficient_aal`). Sem isso, quem invadiu o e-mail também
   levaria a conta.
6. **Senha nova:** mínimo de 6 caracteres, o mesmo do cadastro. Repetir a
   senha atual (`same_password`) tem mensagem própria. Depois de salvar, vai
   para o painel.
7. **Link "Esqueceu a senha?" no login**, ao lado do campo de senha.

## Modelo do e-mail (painel do Supabase, Authentication > Emails > Reset Password)

Assunto: `Redefinir a senha do SellerPulse`

```html
<h2>Redefinir a senha</h2>
<p>Recebemos um pedido para trocar a senha da sua conta no SellerPulse.</p>
<p><a href="{{ .SiteURL }}/redefinir-senha?token_hash={{ .TokenHash }}&type=recovery">Criar uma senha nova</a></p>
<p>O link só funciona uma vez e vence em pouco tempo. Se não foi você quem pediu, ignore este e-mail: a sua senha continua a mesma.</p>
```

Antes de trocar o modelo, confirmar que o `Site URL` (Authentication > URL
Configuration) é o endereço de produção da Vercel.

## Fora desta entrega

- **Resend com domínio próprio.** Depende do domínio. Quando sair, é só
  configuração no Supabase; o código não muda.
- **Códigos de recuperação do app autenticador.** Quem perdeu o celular
  continua no passo a passo de `docs/operacao.md`.
- **Encerrar as outras sessões ao trocar a senha.**
- Opcionais da revisão de interface: dar peso de botão a "Pedir um link novo",
  trazer o e-mail digitado no login para `/esqueci-senha`, e uniformizar
  "Email" e "e-mail" nos rótulos das telas de entrada.
