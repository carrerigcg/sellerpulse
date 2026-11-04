/**
 * Recuperar a senha esquecida, pelo Supabase Auth (spec
 * `docs/specs/2026-11-04-esqueci-a-senha-design.md`).
 *
 * O link do e-mail chega de dois jeitos:
 * - `token_hash`: o modelo próprio do e-mail, que funciona em qualquer
 *   aparelho. O Supabase só deixa editar o modelo com SMTP próprio.
 * - `code`: o modelo padrão, pelo fluxo PKCE. Só funciona no navegador que
 *   pediu o link, porque a outra metade do código ficou guardada nele.
 */

export const MIN_SENHA = 6;

/** O que importa de um erro do Supabase Auth. */
export type ErroDeAuth = { code?: string; status?: number; name?: string; message: string };

export type LinkDeRecuperacao = { tipo: "token" | "codigo" | "erro"; valor: string };

/**
 * O que o link do e-mail trouxe, ou `null` se a página abriu sem link.
 *
 * No modelo padrão, quem confere o link é o Supabase, antes de a página
 * abrir: vencido ou já usado, ele redireciona para cá só com `error_code`, na
 * query ou depois do `#`. Isso é um link recusado, e não uma página sem link.
 */
export function linkDeRecuperacao(search: string, hash = ""): LinkDeRecuperacao | null {
  const params = new URLSearchParams(search);
  const doHash = new URLSearchParams(hash.replace(/^#/, ""));
  const erro =
    params.get("error_code") || params.get("error") || doHash.get("error_code") || doHash.get("error");
  if (erro) return { tipo: "erro", valor: erro };
  const token = params.get("token_hash");
  if (token && params.get("type") === "recovery") return { tipo: "token", valor: token };
  const codigo = params.get("code");
  if (codigo) return { tipo: "codigo", valor: codigo };
  return null;
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
export function motivoDoLinkInvalido(
  erro: ErroDeAuth,
  tipo: Exclude<LinkDeRecuperacao["tipo"], "erro"> = "token",
): string {
  if (falhaDeRede(erro)) {
    return "Não foi possível conectar. Verifique sua internet e abra o link do e-mail de novo.";
  }
  if (tipo === "codigo") {
    return "Este link venceu, já foi usado ou foi aberto em outro navegador. Abra o link no mesmo navegador em que pediu, ou peça outro.";
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
