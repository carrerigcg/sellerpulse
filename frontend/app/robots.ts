import type { MetadataRoute } from "next";

import { FORA_DA_BUSCA, URL_DO_SITE } from "../lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: [...FORA_DA_BUSCA] },
    sitemap: `${URL_DO_SITE}/sitemap.xml`,
  };
}
