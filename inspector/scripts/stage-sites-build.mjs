import { copyFile, mkdir, readdir, rm } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const dist = resolve(root, "dist");
const retainedProjection = "ebrt-apply-revision-acceptance-v0.6.2.1.json";

for (const entry of await readdir(resolve(dist, "data"))) {
  if (entry !== retainedProjection) {
    await rm(resolve(dist, "data", entry), { force: true, recursive: true });
  }
}

await mkdir(resolve(dist, "server"), { recursive: true });
await mkdir(resolve(dist, ".openai"), { recursive: true });
await copyFile(resolve(root, "worker", "index.js"), resolve(dist, "server", "index.js"));
await copyFile(resolve(root, ".openai", "hosting.json"), resolve(dist, ".openai", "hosting.json"));
