import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

function widgetEmbedPlugin(widgetUrl: string, clientId: string): Plugin {
  return {
    name: "widget-embed",
    transformIndexHtml: {
      order: "pre",
      handler(html) {
        return html
          .replace("__CHAT_WIDGET_URL__", widgetUrl)
          .replace("__CHAT_WIDGET_CLIENT_ID__", clientId);
      },
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  const widgetUrl = env.VITE_CHAT_WIDGET_URL || "/src/chat-widget.js";
  const clientId = env.VITE_CHAT_WIDGET_CLIENT_ID || "client_demo";

  return {
    plugins: [widgetEmbedPlugin(widgetUrl, clientId), tailwindcss(), react()],
    server: {
      port: 5173,
    },
  };
});
