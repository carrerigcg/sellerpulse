/**
 * A verificação em duas etapas (app autenticador, TOTP do Supabase Auth).
 *
 * O Supabase diz o nível da sessão (`currentLevel`) e o que ela alcança
 * (`nextLevel`): quem ativou o app tem `nextLevel` `aal2`, e até digitar o
 * código a sessão fica em `aal1`. O backend recusa essa sessão com 401
 * `segundo-fator`; a tela leva para `/verificar` antes disso.
 */

import { URL_DO_SITE } from "./site";

/**
 * O nome que fica gravado no app autenticador do vendedor. Sem ele, o Supabase
 * usa o Site URL da hora do cadastro, e quem ativou antes do domínio próprio
 * ficou com o endereço da Vercel. O app guarda o nome para sempre: trocar aqui
 * só vale para quem ativar depois.
 */
export const EMISSOR_DO_APP_AUTENTICADOR = new URL(URL_DO_SITE).host;

export type NivelDaSessao = { currentLevel: string | null; nextLevel: string | null };

export function faltaOCodigo(nivel: NivelDaSessao | null | undefined): boolean {
  return nivel?.nextLevel === "aal2" && nivel.currentLevel !== "aal2";
}

/** O código do app: seis dígitos, sem espaço. */
export function codigoValido(texto: string): string | null {
  const digitos = texto.replace(/\s/g, "");
  return /^\d{6}$/.test(digitos) ? digitos : null;
}
