import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  expect: { timeout: 15000 },
  workers: 1,
  retries: 0,
  outputDir: "../output/testing/evidence/browser-artifacts",
  reporter: [["list"], ["json", { outputFile: "../output/testing/evidence/browser-results.json" }], ["html", { outputFolder: "../output/testing/evidence/browser-report", open: "never" }]],
  use: { baseURL: "http://127.0.0.1:3001", actionTimeout: 10000, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox-desktop", use: { ...devices["Desktop Firefox"] } },
    { name: "chromium-mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    { command: '"..\\backend\\.venv\\Scripts\\python.exe" "..\\scripts\\evaluation_server.py"', url: "http://127.0.0.1:8001/api/v1/health/ready", timeout: 120000, reuseExistingServer: false },
    { command: ".\\node_modules\\.bin\\next.cmd build && .\\node_modules\\.bin\\next.cmd start --hostname 127.0.0.1 --port 3001", url: "http://127.0.0.1:3001", timeout: 180000, reuseExistingServer: false, env: { TELEMETRYX_API_URL: "http://127.0.0.1:8001", NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8001/api/v1", NEXT_DIST_DIR: ".next-evaluation" } },
  ],
});
