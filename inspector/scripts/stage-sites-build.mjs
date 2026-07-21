import { copyFile, mkdir, readdir, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const dist = resolve(root, "dist");
const retainedProjection = "ebrt-apply-revision-acceptance-v0.6.2.1.json";
const mode = process.argv[2];

if (mode !== "recorded" && mode !== "public-live") {
  throw new Error("stage-sites-build.mjs requires mode: recorded | public-live");
}

for (const entry of await readdir(resolve(dist, "data"))) {
  if (entry !== retainedProjection) {
    await rm(resolve(dist, "data", entry), { force: true, recursive: true });
  }
}

await mkdir(resolve(dist, "server"), { recursive: true });
await mkdir(resolve(dist, ".openai"), { recursive: true });
if (mode === "public-live") {
  await copyFile(resolve(root, "worker", "index.js"), resolve(dist, "server", "index.js"));
} else {
  await writeFile(
    resolve(dist, "server", "index.js"),
    `export default {
  async fetch(request, env) {
    if (env?.ASSETS && typeof env.ASSETS.fetch === "function") {
      return env.ASSETS.fetch(request);
    }
    return new Response("Static asset binding unavailable", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  },
};
`,
  );
}
await copyFile(resolve(root, ".openai", "hosting.json"), resolve(dist, ".openai", "hosting.json"));
