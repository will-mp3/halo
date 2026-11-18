// Probe an in-memory database; setup must never open or modify the user's vault.
let db;
try {
  if (process.versions.node.split(".")[0] !== "24") {
    throw new Error(`Expected Node 24, found ${process.version} at ${process.execPath}`);
  }
  const { default: Database } = await import("better-sqlite3");
  const sqliteVec = await import("sqlite-vec");
  db = new Database(":memory:");
  db.exec("CREATE VIRTUAL TABLE probe USING fts5(content)");
  db.prepare("INSERT INTO probe VALUES (?)").run("halo");
  const match = db.prepare("SELECT count(*) AS count FROM probe WHERE probe MATCH ?").get("halo");
  if (match.count !== 1) throw new Error("SQLite full-text search failed");
  sqliteVec.load(db);
  db.prepare("SELECT vec_version()").get();
} catch (error) {
  const detail = error instanceof Error ? error.message : String(error);
  console.error(`memory-layer native dependency check failed: ${detail.slice(0, 500)}`);
  console.error("Run Halo's ./setup.sh to reinstall the locked dependencies under Node 24.");
  process.exitCode = 1;
} finally {
  db?.close();
}
