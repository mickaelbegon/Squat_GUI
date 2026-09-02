import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [inputPath, outputPath, reportPath, previewDir = ""] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("usage: node build_workbook.mjs payload.json output.xlsx [preview_dir]");
}

const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();
const headerFill = "#245B4A";
const alternateFill = "#EAF2EE";

for (const [sheetIndex, [name, table]] of Object.entries(payload.tables).entries()) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const matrix = [table.columns, ...table.rows];
  const used = sheet.getRangeByIndexes(0, 0, matrix.length, table.columns.length);
  used.values = matrix;
  const header = sheet.getRangeByIndexes(0, 0, 1, table.columns.length);
  header.format = {
    fill: headerFill,
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: "#183D32" },
  };
  header.format.rowHeight = 34;
  if (table.rows.length > 0) {
    sheet.tables.add(used, true, `SquatTable${sheetIndex + 1}`);
    const body = sheet.getRangeByIndexes(1, 0, table.rows.length, table.columns.length);
    body.format.borders = {
      insideHorizontal: { style: "thin", color: "#D8E1DD" },
    };
    if (table.rows.length > 1) {
      for (let row = 2; row <= table.rows.length; row += 2) {
        sheet.getRangeByIndexes(row, 0, 1, table.columns.length).format.fill = alternateFill;
      }
    }
  }
  used.format.autofitColumns();
  for (let col = 0; col < table.columns.length; col += 1) {
    const columnRange = sheet.getRangeByIndexes(0, col, matrix.length, 1);
    const columnName = table.columns[col];
    const isLongText = [
      "anthropometry_scaling_rule",
      "scaling_rule",
      "contact_source",
      "support_point_source",
      "capacity_model",
      "capacity_source",
      "definition",
      "sign_convention",
    ].includes(columnName);
    const maximumWidth = name === "Définitions" || isLongText ? 48 : 24;
    const width = Math.min(
      Math.max(columnRange.format.columnWidth || 12, 11),
      maximumWidth,
    );
    columnRange.format.columnWidth = width;
    if (isLongText) {
      columnRange.format.wrapText = true;
    }
    if (/(^|_)(time|delta_time|duration).*_s$/.test(columnName)) {
      columnRange.format.numberFormat = "0.000";
    } else if (/(_m|_m_s|_m_s2|_kg_m|_kg_m2|_N|_Nm|_W)$/.test(columnName)) {
      columnRange.format.numberFormat = "0.000000";
    } else if (/(_deg|_deg_s|_deg_s2|_percent)$/.test(columnName)) {
      columnRange.format.numberFormat = "0.000";
    }
  }
  used.format.autofitRows();
  header.format.rowHeight = 34;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(2);
}

if (previewDir) {
  await fs.mkdir(previewDir, { recursive: true });
  for (const name of Object.keys(payload.tables)) {
    // The data dictionary can contain hundreds of rows; a bounded preview
    // avoids allocating a bitmap taller than the renderer supports.
    const previewOptions = name === "Définitions"
      ? { sheetName: name, range: "A1:G40", scale: 1, format: "png" }
      : { sheetName: name, range: "A1:L20", scale: 1, format: "png" };
    const preview = await workbook.render(previewOptions);
    await fs.writeFile(`${previewDir}/${name}.png`, new Uint8Array(await preview.arrayBuffer()));
  }
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

// These tables intentionally contain typed values only and no formulas.  A
// formula error list is therefore empty by construction; importing the saved
// workbook in the Python fallback test independently scans cell contents.
const errors = [];
await fs.rm(`${outputPath}.inspect.ndjson`, { force: true });

await fs.writeFile(
  reportPath,
  JSON.stringify({ sheets: Object.keys(payload.tables), formulaErrors: errors }),
  "utf8",
);
