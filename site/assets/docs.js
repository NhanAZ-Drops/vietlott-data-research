const docsNumberFormatter = new Intl.NumberFormat("vi-VN");

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const response = await fetch("data/manifest.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const manifest = await response.json();
    document.querySelectorAll("[data-manifest]").forEach((node) => {
      const value = manifest[node.dataset.manifest];
      node.textContent = typeof value === "number" ? docsNumberFormatter.format(value) : value;
    });
    renderCoverage(manifest.products);
  } catch (error) {
    const table = document.getElementById("coverage-table");
    if (table) table.textContent = `Không đọc được manifest: ${error.message}`;
  }
});

function renderCoverage(products) {
  const rows = products
    .map(
      (product) => `
        <tr>
          <td>${escapeDocs(product.name)}</td>
          <td>${docsNumberFormatter.format(product.confirmed_draws)}</td>
          <td>${escapeDocs(formatDocsDate(product.first_date))}</td>
          <td>${escapeDocs(formatDocsDate(product.latest_date))}</td>
          <td>${product.active ? "Đang hoạt động" : "Lịch sử"}</td>
        </tr>`,
    )
    .join("");
  document.getElementById("coverage-table").innerHTML = `
    <table class="data-table">
      <thead><tr><th>Sản phẩm</th><th>Kỳ xác nhận</th><th>Từ ngày</th><th>Đến ngày</th><th>Trạng thái</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function formatDocsDate(value) {
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

function escapeDocs(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
