import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { Client } from "../mcp/memory-layer/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js";
import { StdioClientTransport } from "../mcp/memory-layer/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js";

// A new MCP process must load native dependencies and find a note it indexed.
const vault = await mkdtemp(join(tmpdir(), "halo-mcp-smoke-"));
const client = new Client({ name: "halo-runtime-smoke", version: "1.0.0" });
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [fileURLToPath(new URL("../mcp/memory-layer/dist/server.js", import.meta.url))],
  env: { VAULT_PATH: vault },
  stderr: "pipe",
});

try {
  await client.connect(transport);
  const written = await client.callTool({
    name: "write_note",
    arguments: { path: "runtime-check.md", content: "# Halo runtime\nNative compatibility probe." },
  });
  assert.ok(!written.isError, "MCP write_note failed");
  const found = await client.callTool({
    name: "search_vault", arguments: { query: "compatibility probe", limit: 1 },
  });
  assert.ok(!found.isError, "MCP search_vault failed");
  assert.ok(found.content.some((part) => part.type === "text" && part.text.includes("runtime-check.md")));
  console.log(`MCP write/search passed under ${process.version} using a temporary vault.`);
} finally {
  await client.close();
  await transport.close();
  await rm(vault, { recursive: true, force: true });
}
