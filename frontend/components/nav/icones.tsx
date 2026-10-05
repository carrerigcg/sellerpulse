/**
 * Ícones da navegação, escritos à mão em vez de uma biblioteca.
 *
 * São seis. Uma dependência de ícones custa mais que isso em bundle e em
 * superfície de atualização, e o projeto já recusou um plugin de scrollbar
 * pelo mesmo motivo. Se um dia forem trinta, reavalia.
 *
 * `currentColor` em tudo: a cor vem da classe do link (ativo/inativo), então
 * o ícone não precisa saber nada sobre tema.
 */

type Props = { className?: string };

const base = "h-5 w-5 shrink-0";

export function IconeExecutive({ className = "" }: Props) {
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
      <path d="M3 20h18" />
      <path d="M6 20V11M11 20V5M16 20v-6M21 20v-9" />
    </svg>
  );
}

export function IconeProdutos({ className = "" }: Props) {
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden>
      <path d="M21 8 12 3 3 8l9 5 9-5Z" />
      <path d="M3 12l9 5 9-5M3 16l9 5 9-5" />
    </svg>
  );
}

export function IconeClientes({ className = "" }: Props) {
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" />
      <path d="M16 5.5a3.2 3.2 0 0 1 0 5M18 14.8c2 .7 3 2.6 3 5.2" />
    </svg>
  );
}

export function IconeRelatorios({ className = "" }: Props) {
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </svg>
  );
}

export function IconeConectar({ className = "" }: Props) {
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden>
      <path d="M10 13a4.5 4.5 0 0 0 6.4.2l2.6-2.6a4.5 4.5 0 0 0-6.4-6.4l-1.5 1.5" />
      <path d="M14 11a4.5 4.5 0 0 0-6.4-.2L5 13.4a4.5 4.5 0 0 0 6.4 6.4l1.5-1.5" />
    </svg>
  );
}

export function IconeMenu({ className = "" }: Props) {
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

export function IconeFechar({ className = "" }: Props) {
  return (
    <svg className={`${base} ${className}`} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}
