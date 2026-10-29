/** Título da tela. Sem seletor de período: assinatura não tem janela de datas. */
export function CabecalhoSimples() {
  return (
    <header>
      <h1 className="text-2xl font-semibold tracking-tight">Assinatura</h1>
      <p className="mt-1 text-sm text-muted">O seu plano, a cobrança e como trocar ou cancelar.</p>
    </header>
  );
}
