import Image from "next/image";

type Fonte = { src: string; width: number; height: number };

/**
 * Moldura de "janela de navegador" em volta de um print real do produto.
 * Três pontinhos no topo bastam pra ler como "isto é uma tela", sem
 * simular uma barra de endereço falsa (que exigiria inventar uma URL).
 *
 * Duas fontes de imagem, não uma só redimensionada por CSS: o mesmo
 * recorte de 1104px de largura, encolhido pra caber nos ~340px de um
 * celular, deixa o texto pequeno das telas (rótulo de eixo, cabeçalho de
 * tabela) ilegível — é exatamente o "print de desktop espremido a 400px"
 * que a spec pede pra evitar. `mobile` é um recorte separado, tirado a
 * ~650px de largura (a própria página do dashboard, não desktop-first
 * nessa largura), então o texto que sobra no celular já nasceu perto do
 * tamanho em que vai ser exibido. As duas tags ficam sempre no DOM — troca
 * é só CSS (`hidden`/`block` por breakpoint), sem JS, sem layout shift.
 */
export function BrowserFrame({
  desktop,
  mobile,
  alt,
}: {
  desktop: Fonte;
  mobile: Fonte;
  alt: string;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-bg shadow-xl shadow-ink/10">
      <div className="flex items-center gap-1.5 border-b border-line bg-surface px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-line" aria-hidden />
        <span className="h-2.5 w-2.5 rounded-full bg-line" aria-hidden />
        <span className="h-2.5 w-2.5 rounded-full bg-line" aria-hidden />
      </div>
      <Image
        src={mobile.src}
        width={mobile.width}
        height={mobile.height}
        alt={alt}
        className="block h-auto w-full sm:hidden"
      />
      <Image
        src={desktop.src}
        width={desktop.width}
        height={desktop.height}
        alt={alt}
        className="hidden h-auto w-full sm:block"
      />
    </div>
  );
}
