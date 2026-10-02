import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Civora AI — Civil Site Planning Review",
    short_name: "Civora",
    description:
      "Civil site planning workspace for traceable concepts, review-required engineering signals, and engineer-review packages.",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f7f9",
    theme_color: "#f6f7f9",
    icons: [
      {
        src: "/icon.png",
        sizes: "512x512",
        type: "image/png",
      },
      {
        src: "/brand/civora-primary-mark.png",
        sizes: "1254x1254",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
