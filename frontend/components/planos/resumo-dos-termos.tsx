/**
 * O essencial dos Termos de Uso, que a pessoa lê antes de marcar "li e aceito".
 * Usado no aceite de quem já tem plano (`/aceite`) e na contratação
 * (`/assinar`): o texto é um só, para os dois aceites provarem a mesma coisa.
 */
export function ResumoDosTermos({ versao }: { versao: string }) {
  return (
    <section className="mt-6 space-y-3 rounded-xl border border-line bg-surface p-5 text-sm leading-relaxed">
      <h2 className="font-semibold">O essencial dos termos</h2>
      <ul className="list-disc space-y-2 pl-5">
        <li>
          O SellerPulse lê, com a sua autorização, os pedidos, anúncios e envios da sua conta do
          Mercado Livre, e só para calcular as análises do painel. Nunca altera nada na sua
          conta.
        </li>
        <li>
          Os dados dos seus compradores são tratados em seu nome. Não guardamos nome, e-mail,
          telefone, endereço ou CPF de comprador, nem dados de cartão.
        </li>
        <li>
          Os números dependem do que o Mercado Livre entrega e do custo que você informa. O
          custo dos produtos só entra na conta quando você o informa.
        </li>
        <li>
          Você pode desconectar a conta do Mercado Livre quando quiser, e pedir a exclusão dos
          seus dados.
        </li>
        <li>
          O plano mensal renova sozinho a cada mês, e o anual vale por 12 meses. Você cancela
          quando quiser, e o acesso continua até o fim do período já pago.
        </li>
      </ul>
      <p className="text-xs text-muted">
        Versão {versao}. Este é um resumo: valem os{" "}
        <a href="/termos" target="_blank" className="underline hover:text-accent">
          Termos de Uso
        </a>{" "}
        e a{" "}
        <a href="/privacidade" target="_blank" className="underline hover:text-accent">
          Política de Privacidade
        </a>{" "}
        completos.
      </p>
    </section>
  );
}
