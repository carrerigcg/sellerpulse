import { SEGMENTOS, definicaoSegmento } from "../components/analytics/segmentos";
import type { SegmentoRfm } from "./api";

/**
 * O `?segmento=` da URL de Clientes, validado. Vem do cartão do Resumo, que
 * abre a lista já nos clientes em risco — mas a URL é digitável, então só
 * passa o que existe.
 */
export function segmentoDaUrl(valor: unknown): SegmentoRfm | null {
  return SEGMENTOS.find((s) => s.parametro === valor)?.chave ?? null;
}

/** O caminho de volta, para o link do Resumo não repetir o texto da URL. */
export function parametroDoSegmento(chave: SegmentoRfm): string {
  return definicaoSegmento(chave).parametro;
}
