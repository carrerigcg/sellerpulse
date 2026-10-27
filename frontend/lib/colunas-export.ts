import type { Coluna } from "./csv";
import type { AbcLinha, FluxoDia, RfmLinha } from "./api";

/**
 * As colunas de cada exportação, num arquivo só.
 *
 * Juntas aqui de propósito, e não espalhadas nas páginas: quando uma tela
 * ganhar coluna nova — custo de produto, visitas, conversão —, este é o lugar
 * onde fica óbvio que o arquivo também precisa ganhar. Espalhado, a tela ganha
 * a coluna e o arquivo fica pra trás, em silêncio.
 *
 * Cabeçalhos em português por extenso: `margem_contribuicao` é nome de coluna
 * de banco; quem abre a planilha quer ler "Margem de contribuição".
 */

export const COLUNAS_FLUXO: Coluna<FluxoDia>[] = [
  { titulo: "Data", campo: "date" },
  { titulo: "Receita bruta", campo: "receita_bruta" },
  { titulo: "Comissão do Mercado Livre", campo: "taxas_ml" },
  { titulo: "Frete", campo: "frete" },
  { titulo: "Custo dos produtos", campo: "custo_produtos" },
  { titulo: "Receita sem custo informado", campo: "receita_sem_custo" },
  { titulo: "Margem de contribuição", campo: "margem_contribuicao" },
];

export const COLUNAS_ABC: Coluna<AbcLinha>[] = [
  { titulo: "Classe", campo: "classe" },
  { titulo: "SKU", campo: "sku" },
  { titulo: "Título", campo: "titulo" },
  { titulo: "Receita", campo: "receita" },
  { titulo: "% da receita", campo: "receita_pct" },
  { titulo: "% acumulado", campo: "receita_acumulada_pct" },
  { titulo: "Custo dos produtos", campo: "custo_produtos" },
  { titulo: "Receita sem custo informado", campo: "receita_sem_custo" },
  { titulo: "Unidades", campo: "unidades" },
  { titulo: "Unidades com visita medida", campo: "unidades_com_visita" },
  { titulo: "Visitas", campo: "visitas" },
  { titulo: "Conversão (%)", campo: "conversao" },
];

export const COLUNAS_RFM: Coluna<RfmLinha>[] = [
  { titulo: "Comprador", campo: "buyer_id" },
  { titulo: "Segmento", campo: "segmento" },
  { titulo: "Recência (dias)", campo: "recency_dias" },
  { titulo: "Frequência", campo: "frequency" },
  { titulo: "Valor", campo: "monetary" },
  { titulo: "R", campo: "r_score" },
  { titulo: "F", campo: "f_score" },
  { titulo: "M", campo: "m_score" },
];
