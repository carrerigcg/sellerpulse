/**
 * Recuperar a senha esquecida, pelo Supabase Auth (spec
 * `docs/specs/2026-11-04-esqueci-a-senha-design.md`).
 *
 * O link do e-mail traz o código (`token_hash`) direto para `/redefinir-senha`,
 * e não pelo fluxo PKCE padrão: o PKCE só funciona no navegador que pediu, e
 * quem pede no computador costuma abrir o e-mail no celular.
 */

export const MIN_SENHA = 6;

/** O que importa de um erro do Supabase Auth. */
export type ErroDeAuth = { code?: string; status?: number; name?: string; message: string };

/** O código do link do e-mail, só se o link for de recuperação de senha. */
export function tokenDeRecuperacao(search: string): string | null {
  const params = new URLSearchParams(search);
  if (params.get("type") !== "recovery") return null;
  return params.get("token_hash") || null;
}

/** O pedido nem chegou ao Supabase: nada foi gasto nem decidido do lado de lá. */
function falhaDeRede(erro: ErroDeAuth): boolean {
  const texto = erro.message.toLowerCase();
  return (
    erro.name === "AuthRetryableFetchError" ||
    erro.name === "TypeError" ||
    texto.includes("failed to fetch") ||
    texto.includes("networkerror") ||
    texto.includes("load failed")
  );
}

export type MensagemDoEnvio = { tom: "ok" | "erro"; texto: string; contato?: boolean };

/**
 * A resposta de "enviar o link". Sem erro, a mesma frase com conta e sem
 * conta: dizer "esse e-mail não tem conta" mostraria quem é cliente.
 */
export function mensagemDoEnvio(erro: ErroDeAuth | null): MensagemDoEnvio {
  if (!erro) {
    return {
      tom: "ok",
      texto:
        "Se houver uma conta com esse e-mail, enviamos um link para criar uma senha nova. Confira a caixa de entrada e o spam.",
    };
  }
  // Remetente padrão do Supabase, sem SMTP próprio: só entrega para a equipe.
  // Dizer "enviamos" deixaria a pessoa esperando um e-mail que não chega.
  if (erro.code === "email_address_not_authorized") {
    return {
      tom: "erro",
      texto: "O envio do link por e-mail ainda não está disponível. Fale com a gente e resolvemos por lá.",
      contato: true,
    };
  }
  const texto = erro.message.toLowerCase();
  if (
    erro.code === "over_email_send_rate_limit" ||
    erro.code === "over_request_rate_limit" ||
    erro.status === 429 ||
    texto.includes("rate limit")
  ) {
    return { tom: "erro", texto: "Muitos pedidos seguidos. Espere um minuto e tente de novo." };
  }
  if (falhaDeRede(erro)) {
    return {
      tom: "erro",
      texto: "Não foi possível conectar. Verifique sua internet e tente de novo.",
    };
  }
  return { tom: "erro", texto: "Algo deu errado do nosso lado. Tente de novo em instantes." };
}

/**
 * Por que o link do e-mail não abriu. Queda de conexão não gasta o código:
 * dizer "já foi usado" mandaria a pessoa pedir outro link à toa.
 */
export function motivoDoLinkInvalido(erro: ErroDeAuth): string {
  if (falhaDeRede(erro)) {
    return "Não foi possível conectar. Verifique sua internet e abra o link do e-mail de novo.";
  }
  return "Este link venceu ou já foi usado. Cada link funciona uma vez só.";
}

/** O erro ao gravar a senha nova, em português. */
export function mensagemDaSenhaNova(erro: ErroDeAuth): string {
  if (erro.code === "same_password") {
    return "Essa já é a sua senha atual. Escolha outra, ou volte e entre com ela.";
  }
  if (erro.code === "weak_password") {
    return `A senha precisa ter pelo menos ${MIN_SENHA} caracteres.`;
  }
  if (erro.code === "insufficient_aal") {
    // O link do e-mail já foi gasto ao abrir esta tela: só um novo serve.
    return "Falta confirmar o código do app autenticador. Peça um link novo e confirme o código antes da senha.";
  }
  if (erro.code === "session_not_found" || erro.code === "session_expired") {
    return "O tempo para trocar a senha acabou. Peça um link novo.";
  }
  return "Não foi possível salvar a senha nova. Tente de novo em instantes.";
}
