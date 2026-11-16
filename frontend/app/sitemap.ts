import type { MetadataRoute } from "next";

import { PAGINAS_PUBLICAS, URL_DO_SITE } from "../lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  return PAGINAS_PUBLICAS.map((caminho) => ({
    url: caminho === "/" ? URL_DO_SITE : `${URL_DO_SITE}${caminho}`,
  }));
}
