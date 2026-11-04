/**
 * A verificação em duas etapas (app autenticador, TOTP do Supabase Auth).
 *
 * O Supabase diz o nível da sessão (`currentLevel`) e o que ela alcança
 * (`nextLevel`): quem ativou o app tem `nextLevel` `aal2`, e até digitar o
 * código a sessão fica em `aal1`. O backend recusa essa sessão com 401
 * `segundo-fator`; a tela leva para `/verificar` antes disso.
 */

export type NivelDaSessao = { currentLevel: string | null; nextLevel: string | null };

export function faltaOCodigo(nivel: NivelDaSessao | null | undefined): boolean {
  return nivel?.nextLevel === "aal2" && nivel.currentLevel !== "aal2";
}

/** O código do app: seis dígitos, sem espaço. */
export function codigoValido(texto: string): string | null {
  const digitos = texto.replace(/\s/g, "");
  return /^\d{6}$/.test(digitos) ? digitos : null;
}
