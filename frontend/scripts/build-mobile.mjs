import { spawnSync } from "node:child_process";

process.env.VITE_API_URL =
  process.env.VITE_API_URL ||
  "https://django-backend-460809694305.us-central1.run.app";
process.env.VITE_APP_ENV = "production";

const run = (command, args) => {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    shell: true,
    env: process.env,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
};

run("npx", ["vite", "build"]);
run("npx", ["cap", "sync"]);
