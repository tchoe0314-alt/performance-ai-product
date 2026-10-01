import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import ts from "typescript";

// Embed the same module used by the server, preserving a standalone HTML file.
const source = fileURLToPath(new URL("../app/utils/culDeSacConcept.ts", import.meta.url));
const target = fileURLToPath(new URL("../public/concepts/cul-de-sac.html", import.meta.url));
const compiled = ts.transpileModule(await readFile(source, "utf8"), {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS },
}).outputText;
const html = await readFile(target, "utf8");
const embedded = `// BEGIN GENERATED CONCEPT CORE\nconst ConceptCore=(()=>{const exports={};\n${compiled}\nreturn exports;})();\n// END GENERATED CONCEPT CORE`;
const updated = html.replace(/\/\/ BEGIN GENERATED CONCEPT CORE[\s\S]*?\/\/ END GENERATED CONCEPT CORE/, embedded);
if (!html.includes("// BEGIN GENERATED CONCEPT CORE")) throw new Error("Missing core markers");
if (process.argv.includes("--check")) {
  if (html !== updated) throw new Error("Embedded concept core is out of date. Run npm run concept:sync.");
  console.log("Embedded concept core matches the server module.");
} else {
  await writeFile(target, updated);
  console.log("Updated generated concept core.");
}
