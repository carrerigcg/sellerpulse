# Telefone no cadastro e verificação em duas etapas

Estado: em implementação na branch `feat/telefone-e-duas-etapas`.

## O pedido

O Guilherme quer, em 2026-11-04:

- o telefone do vendedor, para um contato por WhatsApp quando precisar;
- uma segunda verificação ao entrar, para que uma senha roubada não baste.

Escolheu as opções 1.1 + 2.1, opcionais:

- telefone opcional no cadastro, com aceite separado para o WhatsApp;
- código de um app autenticador (TOTP).

O SMS ficou de fora: custa por envio, exige plano pago no Supabase (a
organização está no free) e cai no golpe do chip clonado.

## Decisões travadas

### Telefone

1. **Opcional.** O cadastro não trava sem ele.
2. **Guardado nos metadados do usuário no Supabase Auth** (`telefone`,
   `whatsapp_aceito_em`), sem tabela nova.
   - O cadastro tem confirmação por e-mail, então não há sessão na hora de
     criar a conta para chamar o backend. O `signUp` grava os metadados junto.
   - Excluir a conta apaga o usuário e o telefone vai junto.
   - Custo aceito: os metadados viajam no token de sessão, como o e-mail já
     viaja.
3. **Formato:** só dígitos, DDD + número, 10 ou 11 dígitos, sem o 55. O campo
   aceita máscara e espaços. O que não fecha 10 ou 11 dígitos é recusado na
   tela, com o motivo.
4. **WhatsApp só com aceite próprio.**
   - É uma caixa separada, desmarcada por padrão, que só fica disponível com
     telefone preenchido.
   - Grava a data e hora do aceite (`whatsapp_aceito_em`), que é a prova.
     Sem aceite, o campo fica vazio.
   - Pela LGPD e pelas regras do WhatsApp Business, pedir o número não
     autoriza mandar mensagem.
5. **Editar depois:** em "Conta e segurança" (`/dashboard/seguranca`), o
   vendedor muda ou apaga o telefone e retira o aceite.

### Verificação em duas etapas

6. **App autenticador (TOTP) do Supabase Auth**, grátis no plano free.
   **Opcional:** o vendedor ativa em "Conta e segurança".
7. **Ativar:**
   - a tela mostra o QR code e a chave para digitar à mão;
   - pede o primeiro código e só considera ativo depois que ele confere.
   - Um fator criado e não confirmado (a pessoa fechou a tela) é apagado na
     próxima tentativa, para não acumular.
8. **Desativar:** exige a sessão já verificada com o código (`aal2`), regra
   do próprio Supabase. A tela pede o código antes.
9. **Ao entrar:**
   - Depois da senha, quem tem o fator ativo vai para `/verificar`, que pede
     o código de 6 dígitos.
   - O `proxy.ts` manda para `/verificar` toda sessão de quem tem o fator e
     ainda não passou pelo código. Assim, fechar a aba depois da senha não
     abre o painel.
10. **O backend também exige.**
    - Token sem `aal2` de um usuário com fator verificado em
      `auth.mfa_factors` recebe 401 `segundo-fator`.
    - Sem isso, quem tem só a senha pegaria um token `aal1` e chamaria a API
      direto, e a verificação seria só de tela.
    - O custo é uma consulta por requisição autenticada, pelo índice de
      `user_id`.
11. **Perdeu o celular:** o vendedor fala com o suporte por e-mail.
    - O suporte remove o fator, depois de confirmar a identidade pelo e-mail
      da conta.
    - Códigos de recuperação ficam de fora (ver abaixo).
    - O passo a passo vai para `docs/operacao.md`.

### Textos legais

12. **Política de privacidade, seção 3.1:**
    - passa a citar o telefone opcional, para que serve e o aceite separado do
      WhatsApp;
    - passa a citar o segredo do app autenticador, guardado pelo provedor de
      autenticação;
    - a frase "não guardamos telefone" da seção 3.2 fica restrita ao telefone
      **de cobrança**.
    - A data muda e a versão (`VERSAO_DOS_TERMOS`) fica: a mudança acrescenta
      um dado opcional com aceite próprio, e não pede novo aceite de todos.
      Vai junto para a revisão do advogado.

## O que ficou de fora

- SMS e mensagem por WhatsApp de verdade. Aqui só se coleta o número e o
  aceite.
- Códigos de recuperação do segundo fator. O Supabase não os oferece prontos.
- Tornar a verificação obrigatória, ou obrigatória para algum plano.
- Confirmar o telefone (provar que o número é da pessoa). Sem SMS, não há como.
