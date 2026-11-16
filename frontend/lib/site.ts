/**
 * O endereço público do site e o que os buscadores podem ler. Fixo, e não
 * de variável de ambiente: o preview da Vercel tem outro endereço, e um
 * sitemap ou uma prévia de link apontando para o preview mandaria quem chega
 * do Google para uma versão de teste.
 */
export const URL_DO_SITE = "https://usesellerpulse.com";

/** As páginas abertas, que valem ser achadas por quem procura. */
export const PAGINAS_PUBLICAS = [
  "/",
  "/planos",
  "/demo",
  "/demo/produtos",
  "/demo/clientes",
  "/demo/financeiro",
  "/demo/custos",
  "/termos",
  "/privacidade",
] as const;

/**
 * O que fica fora da busca: o painel e os passos de conta. Não é proteção
 * (quem protege é o login), é só para o Google não listar uma tela de senha.
 */
export const FORA_DA_BUSCA = [
  "/dashboard",
  "/assinar",
  "/aceite",
  "/verificar",
  "/redefinir-senha",
  "/esqueci-senha",
  "/demo/exportar",
] as const;
