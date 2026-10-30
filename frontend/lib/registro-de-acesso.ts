// O backend guarda uma linha por usuário, IP e hora, e ignora a repetição. O
// intervalo só poupa requisição: é curto para pegar a virada da hora e a troca de
// IP (Wi-Fi para 4G), que é o dado que uma ordem judicial pediria.
export const INTERVALO_DO_REGISTRO = 5 * 60 * 1000;

export function criaRegistrador(enviar: () => Promise<void>, agora: () => number = Date.now) {
  let ultimo: number | null = null;
  return async function tenta(): Promise<void> {
    if (ultimo !== null && agora() - ultimo < INTERVALO_DO_REGISTRO) return;
    try {
      await enviar();
      // Só depois do sucesso: falha de rede não pode esperar o intervalo inteiro.
      ultimo = agora();
    } catch {
      // Registro nunca atrapalha a tela.
    }
  };
}
