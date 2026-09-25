import type { AuthError } from "@supabase/supabase-js";

/**
 * Traduz erros do Supabase Auth para português, separando o que é culpa do
 * usuário do que é falha técnica.
 *
 * Por que isso importa: a primeira versão devolvia "Email ou senha
 * incorretos" para QUALQUER falha. Em produção, um header malformado fez o
 * browser recusar a requisição antes de sair da máquina — e a tela dizia ao
 * usuário que a senha estava errada. Alguém nessa situação troca a senha
 * várias vezes tentando resolver um problema que não é dele, e quem depura
 * persegue a pista errada (foi o que aconteceu aqui).
 *
 * Credencial inválida continua com mensagem genérica de propósito: dizer
 * "esse email não existe" entrega ao atacante quais emails estão na base.
 */

const CREDENCIAL_INVALIDA = "Email ou senha incorretos.";
const FALHA_DE_REDE = "Não foi possível conectar. Verifique sua internet e tente de novo.";
const FALHA_TECNICA = "Algo deu errado do nosso lado. Tente de novo em instantes.";

export function mensagemDeLogin(erro: AuthError | Error): string {
  const codigo = "code" in erro ? String(erro.code ?? "") : "";
  const status = "status" in erro ? Number(erro.status ?? 0) : 0;
  const texto = erro.message.toLowerCase();

  // Único caso em que a culpa é do que o usuário digitou.
  if (
    codigo === "invalid_credentials" ||
    texto.includes("invalid login credentials") ||
    texto.includes("invalid_credentials")
  ) {
    return CREDENCIAL_INVALIDA;
  }

  if (codigo === "email_not_confirmed" || texto.includes("email not confirmed")) {
    return "Confirme seu email antes de entrar. Procure o link que enviamos.";
  }

  if (codigo === "over_request_rate_limit" || status === 429 || texto.includes("rate limit")) {
    return "Muitas tentativas seguidas. Espere um minuto e tente de novo.";
  }

  // Erros de transporte: o request nem chegou ao servidor, ou voltou quebrado.
  if (
    erro.name === "AuthRetryableFetchError" ||
    erro.name === "TypeError" ||
    texto.includes("failed to fetch") ||
    texto.includes("networkerror") ||
    texto.includes("load failed")
  ) {
    return FALHA_DE_REDE;
  }

  return FALHA_TECNICA;
}

/**
 * Loga o erro real no console do browser.
 *
 * A tela mostra mensagem genérica por segurança, mas engolir o detalhe
 * também de quem está depurando transforma qualquer investigação em
 * adivinhação — que foi exatamente o custo da versão anterior.
 */
export function registraErroDeAuth(contexto: string, erro: unknown): void {
  if (typeof console !== "undefined") {
    console.error(`[auth:${contexto}]`, erro);
  }
}
