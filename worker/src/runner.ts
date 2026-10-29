import { DurableObject } from "cloudflare:workers";
import type { Env } from "./env";

const PORT = 8080;
const IDLE_MS = 5 * 60_000;
const BOOT_TRIES = 60;
const BOOT_WAIT_MS = 500;

// One container per instance; it plays one game at a time and sleeps when idle.
export class Runner extends DurableObject<Env> {
  async fetch(req: Request): Promise<Response> {
    const container = this.ctx.container!;
    const image = container.images.runner;
    if (container.running && (await this.ctx.storage.get("image")) !== image) {
      await container.destroy(); // a deploy shipped a new image; don't keep serving the old one
    }
    if (!container.running) {
      await this.ctx.storage.put("image", image);
      container.start({ image, instance: "standard-1", enableInternet: false });
      container.monitor().catch((e) => console.error("container stopped", String(e)));
    }
    await container.setInactivityTimeout(IDLE_MS);
    const body = await req.arrayBuffer();
    const port = container.getTcpPort(PORT);
    for (let i = 0; ; i++) {
      try {
        return await port.fetch(req.url, { method: req.method, headers: req.headers, body });
      } catch (e) {
        if (i >= BOOT_TRIES) throw e;
        await new Promise((r) => setTimeout(r, BOOT_WAIT_MS));
      }
    }
  }
}
