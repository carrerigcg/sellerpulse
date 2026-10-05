import { NavegacaoDemo } from "./navegacao";

/**
 * Layout da demonstração pública — sem `createClient`/`getUser`: ao
 * contrário de `dashboard/layout.tsx`, esta árvore inteira não tem sessão
 * pra checar. É esse o ponto da demo.
 *
 * O aviso de dado fictício fica dentro do conteúdo, não acima da sidebar:
 * uma faixa atravessando a tela inteira roubaria altura da navegação no
 * celular, e o aviso pertence ao dado, que é o que está no conteúdo.
 */
export default function DemoLayout({ children }: LayoutProps<"/demo">) {
  return (
    <NavegacaoDemo>
      <p className="mb-6 rounded-lg border border-line bg-highlight/10 px-4 py-2 text-center text-xs text-muted">
        Você está vendo dados de demonstração fictícios, não uma loja real.
      </p>
      {children}
    </NavegacaoDemo>
  );
}
