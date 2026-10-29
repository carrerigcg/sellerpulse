/**
 * O corpo do `PUT /custos/{sku}`, separado de `custos-client.ts` para poder
 * ser testado: aquele arquivo depende do cliente de sessão do navegador.
 *
 * `retroativo` sempre vai explícito, ligado ou não. O backend trata a falta
 * do campo como "a partir de hoje", e um corpo que o perdesse faria a tela
 * prometer o histórico sem o banco gravar
 * (docs/specs/2026-10-28-custo-retroativo-design.md).
 */
export function corpoDoCusto(custoUnitario: number, retroativo: boolean) {
  return { custo_unitario: custoUnitario, retroativo };
}
