#!/usr/bin/env node
/**
 * Export README.md to PDF with repo images resolved (handles ./path and /path).
 *
 * Usage:
 *   node scripts/export_readme_pdf.js
 *   node scripts/export_readme_pdf.js README.md dist/README.pdf
 */

const fs = require("fs");
const path = require("path");
const MarkdownIt = require("markdown-it");
const mdAnchor = require("markdown-it-anchor");
const puppeteer = require("puppeteer");

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function toFileUrl(absPath) {
  // Convert Windows backslashes; encode spaces and other URL-unsafe chars.
  const posixPath = absPath.split(path.sep).join(path.posix.sep);
  return "file://" + encodeURI(posixPath);
}

/**
 * Rewrites src/href URLs:
 * - http(s), #, data: are left untouched
 * - "/foo.png" is treated as repo-root-relative (repoRoot + foo.png)
 * - "./foo.png" and "foo.png" are treated as repo-root-relative
 */
function rewriteUrls(html, repoRoot) {
  return html.replace(/(src|href)=["']([^"']+)["']/g, (m, attr, url) => {
    if (
      url.startsWith("http://") ||
      url.startsWith("https://") ||
      url.startsWith("#") ||
      url.startsWith("data:") ||
      url.startsWith("mailto:")
    ) return m;

    if (url.startsWith("file://")) return m;

    // Keep query/hash tail if present
    const match = url.match(/^([^?#]+)([?#].*)?$/);
    const base = match ? match[1] : url;
    const tail = match && match[2] ? match[2] : "";

    let abs;
    if (base.startsWith("/")) {
      // GitHub-style repo-root absolute path
      abs = path.resolve(repoRoot, "." + base);
    } else {
      abs = path.resolve(repoRoot, base);
    }

    return `${attr}="${toFileUrl(abs)}${tail}"`;
  });
}

(async () => {
  const inputMd = process.argv[2] || "README.md";
  const outputPdf = process.argv[3] || path.join("dist", "README.pdf");

  const repoRoot = process.cwd();
  const inputPath = path.resolve(repoRoot, inputMd);
  const outPath = path.resolve(repoRoot, outputPdf);

  if (!fs.existsSync(inputPath)) {
    console.error(`ERROR: Cannot find ${inputMd} at ${inputPath}`);
    process.exit(1);
  }

  ensureDir(path.dirname(outPath));

  const md = new MarkdownIt({ html: true, linkify: true, typographer: true })
    .use(mdAnchor);

  const mdText = fs.readFileSync(inputPath, "utf8");
  let bodyHtml = md.render(mdText);

  // Make repo images work locally (handles your "/System architecture.png" case)
  bodyHtml = rewriteUrls(bodyHtml, repoRoot);

  const fullHtml = `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(path.basename(inputMd))}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 32px; }
    code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }
    pre { padding: 12px; overflow-x: auto; border-radius: 8px; background: #f6f8fa; }
    img { max-width: 100%; }
    h1, h2, h3 { page-break-after: avoid; }
    pre, blockquote, table { page-break-inside: avoid; }
    table { border-collapse: collapse; }
    table, th, td { border: 1px solid #ddd; }
    th, td { padding: 8px; }
    a { color: #0969da; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
${bodyHtml}
</body>
</html>`;

  const browser = await puppeteer.launch({
    headless: "new",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--allow-file-access-from-files",
    ],
  });

  try {
    const page = await browser.newPage();
    await page.setContent(fullHtml, { waitUntil: ["domcontentloaded", "networkidle0"] });
    await page.pdf({
      path: outPath,
      format: "A4",
      printBackground: true,
      margin: { top: "18mm", right: "14mm", bottom: "18mm", left: "14mm" },
    });
    console.log(`✅ PDF exported: ${outputPdf}`);
  } finally {
    await browser.close();
  }
})();
