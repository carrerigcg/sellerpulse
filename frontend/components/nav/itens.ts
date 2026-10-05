import type { ComponentType } from "react";

import {
  IconeClientes,
  IconeConectar,
  IconeExecutive,
  IconeProdutos,
} from "./icones";

export type ItemDeNavegacao = {
  href: string;
  rotulo: string;
  Icone: ComponentType<{ className?: string }>;
  /**
   * `true` só para a raiz de cada contexto. "/dashboard" é prefixo de todas
   * as outras rotas do dashboard, então marcá-lo por prefixo deixaria ele
   * sempre aceso. As demais casam por prefixo de propósito, para continuarem
   * marcadas em sub-rotas futuras.
   */
  exata?: boolean;
};

export type GrupoDeNavegacao = {
  /** `null` = sem título. Grupo único não precisa de rótulo. */
  titulo: string | null;
  itens: ItemDeNavegacao[];
};

export const GRUPOS_DASHBOARD: GrupoDeNavegacao[] = [
  {
    titulo: "Análises",
    itens: [
      { href: "/dashboard", rotulo: "Executive", Icone: IconeExecutive, exata: true },
      { href: "/dashboard/produtos", rotulo: "Produtos", Icone: IconeProdutos },
      { href: "/dashboard/clientes", rotulo: "Clientes", Icone: IconeClientes },
    ],
  },
  {
    titulo: "Configuração",
    itens: [
      { href: "/dashboard/conectar", rotulo: "Conectar conta", Icone: IconeConectar },
    ],
  },
];

export const GRUPOS_DEMO: GrupoDeNavegacao[] = [
  {
    titulo: null,
    itens: [
      { href: "/demo", rotulo: "Executive", Icone: IconeExecutive, exata: true },
      { href: "/demo/produtos", rotulo: "Produtos", Icone: IconeProdutos },
      { href: "/demo/clientes", rotulo: "Clientes", Icone: IconeClientes },
    ],
  },
];
