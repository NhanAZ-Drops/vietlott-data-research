const state = {
  manifest: null,
  predictions: null,
  product: null,
  selectedNumber: null,
  reportCache: new Map(),
  reportPromises: new Map(),
  selectionRequestId: 0,
};

const numberFormatter = new Intl.NumberFormat("vi-VN");
const compactFormatter = new Intl.NumberFormat("vi-VN", {
  notation: "compact",
  maximumFractionDigits: 1,
});

document.addEventListener("DOMContentLoaded", () => {
  setupMenu();
  initialize().catch(showFatalError);
});

async function initialize() {
  const initialHash = window.location.hash;
  const [manifest, predictions] = await Promise.all([
    fetchJson("data/manifest.json"),
    fetchJson("data/predictions.json"),
  ]);
  state.manifest = manifest;
  state.predictions = predictions;
  renderManifest(manifest);
  renderProductTabs(manifest.products);
  renderPredictionShell(predictions, manifest.products);
  renderProjectVerdict(manifest.products).catch((error) => {
    console.error("Không tổng hợp được kết luận toàn bộ sản phẩm", error);
  });

  const requested = new URLSearchParams(window.location.search).get("product");
  const initial = manifest.products.some((item) => item.slug === requested)
    ? requested
    : "power655";
  await selectProduct(initial);
  if (initialHash) {
    window.requestAnimationFrame(() => {
      const target = document.querySelector(initialHash);
      if (!target) return;
      const previousBehavior = document.documentElement.style.scrollBehavior;
      document.documentElement.style.scrollBehavior = "auto";
      target.scrollIntoView();
      document.documentElement.style.scrollBehavior = previousBehavior;
    });
  }
}

function setupMenu() {
  const button = document.querySelector(".menu-button");
  const nav = document.querySelector(".site-nav");
  if (!button || !nav) return;
  button.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    button.setAttribute("aria-expanded", String(open));
  });
  nav.addEventListener("click", () => {
    nav.classList.remove("open");
    button.setAttribute("aria-expanded", "false");
  });
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Không đọc được ${url}: HTTP ${response.status}`);
  return response.json();
}

async function loadProductReport(slug) {
  if (state.reportCache.has(slug)) return state.reportCache.get(slug);
  if (state.reportPromises.has(slug)) return state.reportPromises.get(slug);
  const request = fetchJson(`data/products/${slug}.json`)
    .then((report) => {
      state.reportCache.set(slug, report);
      return report;
    })
    .finally(() => state.reportPromises.delete(slug));
  state.reportPromises.set(slug, request);
  return request;
}

async function renderProjectVerdict(products) {
  const settled = await Promise.allSettled(
    products.map((product) => loadProductReport(product.slug)),
  );
  const reports = settled
    .filter((result) => result.status === "fulfilled")
    .map((result) => result.value)
    .filter((report) => report.backtest?.status === "complete");
  const wins = reports.filter(
    (report) => report.backtest.comparison?.beats_baseline,
  ).length;

  if (!reports.length) {
    text("verdict-backtest-count", "Chưa đủ dữ liệu");
    text(
      "project-verdict-summary",
      "Chưa đọc được báo cáo để đưa ra kết luận tổng hợp.",
    );
    return;
  }

  text("verdict-backtest-count", `${wins}/${reports.length}`);
  const conclusion = wins === 0
    ? `Không phương pháp nào trong ${reports.length} backtest hiện tại vượt cách chọn ngẫu nhiên một cách đáng tin cậy.`
    : `${wins} trong ${reports.length} phương pháp vượt mốc ngẫu nhiên theo tiêu chí hiện tại, nhưng vẫn cần xác nhận bằng dự đoán đã lưu trước.`;
  text("project-verdict-summary", conclusion);
  text(
    "prediction-current-conclusion",
    `${conclusion} Các bộ số dưới đây là thí nghiệm, không phải gợi ý mua vé.`,
  );
}

function renderManifest(manifest) {
  text("hero-draw-count", numberFormatter.format(manifest.draw_rows));
  text("hero-product-count", manifest.products.length);
  const latestDate = manifest.products
    .map((item) => item.latest_date)
    .sort()
    .at(-1);
  text("hero-date", formatDate(latestDate));
  text("confirmed-count", numberFormatter.format(manifest.confirmed_rows));
  text("unconfirmed-count", numberFormatter.format(manifest.not_confirmed_rows));
  text("prize-count", numberFormatter.format(manifest.prize_rows));
  text("method-version", manifest.methodology_version);
}

function renderProductTabs(products) {
  const container = document.getElementById("product-tabs");
  container.innerHTML = products
    .map(
      (product) => `
        <button class="product-tab" type="button" role="tab"
          id="tab-${escapeHtml(product.slug)}"
          aria-controls="dashboard"
          aria-selected="false"
          data-product="${escapeHtml(product.slug)}">
          ${escapeHtml(product.short_name)}
          ${product.active ? "" : '<span class="inactive-tag">lịch sử</span>'}
        </button>`,
    )
    .join("");
  container.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-product]");
    if (tab) selectProduct(tab.dataset.product).catch(showDashboardError);
  });
}

async function selectProduct(slug) {
  const requestId = ++state.selectionRequestId;
  const product = state.manifest?.products.find((item) => item.slug === slug);
  document.querySelectorAll(".product-tab").forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset.product === slug));
  });
  showDashboardLoading(`Đang mở báo cáo ${product?.name || slug}...`);
  document.getElementById("dashboard").hidden = true;
  try {
    const report = await loadProductReport(slug);
    if (requestId !== state.selectionRequestId) return;
    state.product = slug;
    renderProductReport(report);
    document.getElementById("dashboard").hidden = false;

    const url = new URL(window.location);
    url.searchParams.set("product", slug);
    window.history.replaceState({}, "", url);
  } catch (error) {
    if (requestId === state.selectionRequestId) throw error;
  } finally {
    if (requestId === state.selectionRequestId) {
      document.getElementById("dashboard-loading").hidden = true;
    }
  }
}

function renderProductReport(report) {
  const { product, summary, analysis, backtest } = report;
  text(
    "product-kind",
    product.kind === "number_set" ? "Tập số không lặp" : "Chuỗi chữ số có vị trí",
  );
  text("product-name", product.name);
  text("product-note", product.note);
  text("latest-draw-id", `#${summary.latest_draw_id}`);
  text("latest-draw-date", formatDate(summary.latest_date));

  renderMetrics(summary, analysis, product);
  renderUniformity(analysis.uniformity, product.kind);
  renderBacktest(backtest, product.kind);
  renderPrizeReport(summary.prizes);
  renderRecentDraws(summary.recent_draws, product.kind);

  const numberSection = document.getElementById("number-analysis");
  const digitSection = document.getElementById("digit-analysis");
  if (product.kind === "number_set") {
    numberSection.hidden = false;
    digitSection.hidden = true;
    renderNumberAnalysis(analysis, product);
  } else {
    numberSection.hidden = true;
    digitSection.hidden = false;
    renderDigitAnalysis(analysis, product);
  }
}

function renderMetrics(summary, analysis, product) {
  const coverage = summary.prizes.draws_with_prizes / summary.confirmed_draws;
  const officialCount = summary.data_sources.official_vietlott || 0;
  const officialRate = officialCount / summary.confirmed_draws;
  const sourceNames = Object.entries(summary.data_sources)
    .sort((left, right) => right[1] - left[1])
    .slice(0, 2)
    .map(([name]) => sourceLabel(name))
    .join(", ");
  const cards = [
    {
      label: "Kỳ đã xác nhận",
      value: numberFormatter.format(summary.confirmed_draws),
      note: `${formatDate(summary.first_date)} đến ${formatDate(summary.latest_date)}`,
    },
    {
      label: product.kind === "number_set" ? "Không gian số" : "Số kết quả phân tích",
      value:
        product.kind === "number_set"
          ? `${analysis.pool.pick_count}/${analysis.pool.size}`
          : numberFormatter.format(analysis.outcomes),
      note:
        product.kind === "number_set"
          ? `Chọn ${analysis.pool.pick_count} từ ${analysis.pool.size} số`
          : `${analysis.sequence_length} chữ số có thứ tự`,
    },
    {
      label: "Ngày có dữ liệu",
      value: numberFormatter.format(summary.calendar_days_with_draws),
      note: `${formatDecimal(summary.average_draws_per_active_day)} kỳ mỗi ngày hoạt động`,
    },
    {
      label: "Dòng nguồn chính thức",
      value: formatPercent(officialRate),
      note: sourceNames || "Chưa có nhãn nguồn",
    },
    {
      label: "Độ phủ giải thưởng",
      value: formatPercent(coverage),
      note: `${numberFormatter.format(summary.prizes.draws_with_prizes)} kỳ có dòng giải`,
    },
  ];
  document.getElementById("product-metrics").innerHTML = cards
    .map(
      (card) => `
        <article class="metric-card">
          <span>${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(card.value)}</strong>
          <small>${escapeHtml(card.note)}</small>
        </article>`,
    )
    .join("");
}

function sourceLabel(value) {
  const labels = {
    official_vietlott: "Vietlott",
    community_mirror: "Gương cộng đồng",
    xosominhngoc_net_vn: "Nguồn dự phòng",
    xoso_com_vn: "Nguồn lịch sử",
    gap_consensus: "Đối chiếu nhiều nguồn",
    unknown: "Chưa gắn nhãn",
  };
  return labels[value] || value.replaceAll("_", " ");
}

function renderUniformity(uniformity, kind) {
  const pValue = uniformity.approximate_p_value;
  const effect = uniformity.cohens_w;
  const practicallySmall = effect < 0.05;
  const notSignificant = pValue >= 0.05;
  const verdict = notSignificant || practicallySmall
    ? "Chưa thấy sai lệch thực dụng"
    : "Có sai lệch cần kiểm tra tiếp";
  const verdictNode = document.getElementById("test-verdict");
  verdictNode.textContent = verdict;
  verdictNode.classList.toggle("alert", !(notSignificant || practicallySmall));

  const subject = kind === "number_set" ? "tần suất các số" : "tần suất mười chữ số";
  const explanation = notSignificant
    ? `Với dữ liệu hiện có, ${subject} chưa khác mô hình đồng đều đủ mạnh để loại trừ dao động lấy mẫu thông thường.`
    : practicallySmall
      ? `Kiểm định phát hiện khác biệt ở ${subject}, nhưng độ lớn hiệu ứng rất nhỏ. Mẫu lớn có thể làm một sai lệch cực nhỏ trở nên có ý nghĩa thống kê.`
      : `Dữ liệu cho thấy ${subject} khác mô hình đồng đều và độ lớn không còn ở mức rất nhỏ. Cần kiểm tra theo giai đoạn, nguồn và thay đổi quy trình trước khi diễn giải.`;
  text("test-explanation", explanation);

  const metrics = [
    ["Mức bất thường (p)", formatPValue(pValue)],
    ["Độ lệch thực tế", formatDecimal(effect, 4)],
    ["Mức phân tán đều", formatDecimal(uniformity.normalized_entropy, 6)],
  ];
  document.getElementById("test-metrics").innerHTML = metrics
    .map(
      ([label, value]) => `
        <div class="test-metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>`,
    )
    .join("");
}

function renderNumberAnalysis(analysis, product) {
  const numbers = analysis.numbers;
  const preferred =
    numbers.find((item) => item.number === state.selectedNumber) ||
    [...numbers].sort((a, b) => Math.abs(b.z_score) - Math.abs(a.z_score))[0];
  state.selectedNumber = preferred.number;
  renderNumberGrid(numbers);
  renderNumberProfile(preferred);
  renderFrequencyChart(numbers);
  renderOverdueChart(numbers);
  renderMonthChart(analysis.months, preferred, analysis.pool.expected_probability_per_draw);
  renderWeekdayChart(
    analysis.weekdays,
    preferred,
    analysis.pool.expected_probability_per_draw,
  );
  renderNumberPositionHeatmap(analysis.positions);
  renderHistogram("sum-histogram", analysis.structure.sum.histogram, "Tổng bộ số");
  renderStructureSummary(analysis.structure);
  renderPairTable(analysis.pairs);
}

function renderNumberGrid(numbers) {
  const maxAbs = Math.max(2, ...numbers.map((item) => Math.abs(item.z_score)));
  const grid = document.getElementById("number-grid");
  grid.innerHTML = numbers
    .map((item) => {
      const selected = item.number === state.selectedNumber;
      return `
        <button type="button"
          class="number-cell${selected ? " selected" : ""}"
          data-number="${item.number}"
          style="background:${residualColor(item.z_score / maxAbs)}"
          title="Số ${item.number}: z = ${formatDecimal(item.z_score, 2)}"
          aria-pressed="${selected}">
          ${String(item.number).padStart(2, "0")}
        </button>`;
    })
    .join("");
  grid.onclick = (event) => {
    const button = event.target.closest("[data-number]");
    if (!button) return;
    const report = state.reportCache.get(state.product);
    state.selectedNumber = Number(button.dataset.number);
    const item = report.analysis.numbers.find(
      (number) => number.number === state.selectedNumber,
    );
    renderNumberGrid(report.analysis.numbers);
    renderNumberProfile(item);
    renderMonthChart(
      report.analysis.months,
      item,
      report.analysis.pool.expected_probability_per_draw,
    );
    renderWeekdayChart(
      report.analysis.weekdays,
      item,
      report.analysis.pool.expected_probability_per_draw,
    );
  };
}

function renderNumberProfile(item) {
  const significance = item.q_value_bh < 0.05
    ? "Vẫn nổi bật sau khi kiểm tra nhiều số"
    : "Chưa đủ nổi bật sau khi kiểm tra nhiều số";
  document.getElementById("number-profile").innerHTML = `
    <div class="profile-number">
      <strong>${String(item.number).padStart(2, "0")}</strong>
      <span>${escapeHtml(significance)}</span>
    </div>
    <div class="profile-stats">
      ${profileStat("Số lần xuất hiện", numberFormatter.format(item.count))}
      ${profileStat("Mỗi 100 kỳ", formatDecimal(item.rate_per_100_draws, 2))}
      ${profileStat("Mức lệch toàn lịch sử", formatSigned(item.z_score))}
      ${profileStat("Mức lệch trong kỳ gần đây", formatSigned(item.recent_z_score))}
      ${profileStat("Đã vắng", `${numberFormatter.format(item.draws_since)} kỳ`)}
      ${profileStat("Lần cuối", item.last_seen_date ? formatDate(item.last_seen_date) : "Chưa có")}
      ${profileStat("Khoảng vắng lớn nhất", `${numberFormatter.format(item.maximum_gap_draws)} kỳ`)}
    </div>`;
}

function profileStat(label, value) {
  return `<div class="profile-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function renderFrequencyChart(numbers) {
  const high = [...numbers].sort((a, b) => b.z_score - a.z_score).slice(0, 6);
  const low = [...numbers].sort((a, b) => a.z_score - b.z_score).slice(0, 6);
  const rows = [...high, ...low];
  const max = Math.max(...rows.map((item) => Math.abs(item.z_score)), 1);
  renderBars(
    "frequency-chart",
    rows.map((item) => ({
      label: String(item.number).padStart(2, "0"),
      value: Math.abs(item.z_score),
      display: formatSigned(item.z_score),
      className: item.z_score >= 0 ? "warm" : "cool",
      maximum: max,
    })),
  );
}

function renderOverdueChart(numbers) {
  const rows = [...numbers].sort((a, b) => b.draws_since - a.draws_since).slice(0, 12);
  const max = Math.max(...rows.map((item) => item.draws_since), 1);
  renderBars(
    "overdue-chart",
    rows.map((item) => ({
      label: String(item.number).padStart(2, "0"),
      value: item.draws_since,
      display: `${numberFormatter.format(item.draws_since)} kỳ`,
      className: "",
      maximum: max,
    })),
  );
}

function renderBars(containerId, rows) {
  document.getElementById(containerId).innerHTML = rows
    .map(
      (row) => `
        <div class="bar-row">
          <span class="bar-label">${escapeHtml(row.label)}</span>
          <span class="bar-track">
            <span class="bar-fill ${escapeHtml(row.className || "")}"
              style="width:${Math.max(2, (row.value / row.maximum) * 100)}%"></span>
          </span>
          <span class="bar-value">${escapeHtml(row.display)}</span>
        </div>`,
    )
    .join("");
}

function renderMonthChart(months, item, expectedRate) {
  text("month-title", `Số ${String(item.number).padStart(2, "0")} theo tháng`);
  const rows = months.map((month) => {
    const value = month.values.find((entry) => entry.number === item.number);
    return { ...month, rate: value.rate_per_draw };
  });
  const deviations = rows.map((row) =>
    expectedRate ? (row.rate - expectedRate) / expectedRate : 0,
  );
  const maxAbs = Math.max(0.15, ...deviations.map(Math.abs));
  document.getElementById("month-chart").innerHTML = rows
    .map(
      (row, index) => `
        <div class="month-cell"
          style="background:${residualColor(deviations[index] / maxAbs)}"
          title="${numberFormatter.format(row.draws)} kỳ trong tháng ${row.month}">
          <span>Tháng ${row.month}</span>
          <strong>${formatPercent(row.rate)}</strong>
          <small>${numberFormatter.format(row.draws)} kỳ</small>
        </div>`,
    )
    .join("");
}

function renderWeekdayChart(weekdays, item, expectedRate) {
  const labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"];
  const rows = weekdays.map((weekday) => {
    const value = weekday.values.find((entry) => entry.number === item.number);
    return { ...weekday, rate: value.rate_per_draw };
  });
  const deviations = rows.map((row) =>
    expectedRate ? (row.rate - expectedRate) / expectedRate : 0,
  );
  const maxAbs = Math.max(0.15, ...deviations.map(Math.abs));
  document.getElementById("weekday-chart").innerHTML = rows
    .map(
      (row, index) => `
        <div class="month-cell"
          style="background:${residualColor(deviations[index] / maxAbs)}"
          title="${numberFormatter.format(row.draws)} kỳ vào ${labels[row.weekday]}">
          <span>${labels[row.weekday]}</span>
          <strong>${formatPercent(row.rate)}</strong>
          <small>${numberFormatter.format(row.draws)} kỳ</small>
        </div>`,
    )
    .join("");
}

function renderNumberPositionHeatmap(positions) {
  const allRates = positions.flatMap((position) => position.values.map((item) => item.rate));
  const max = Math.max(...allRates, 0.001);
  const columns = positions[0]?.values || [];
  document.getElementById("position-heatmap").innerHTML = `
    <table class="heatmap">
      <thead><tr><th>Vị trí</th>${columns
        .map((item) => `<th>${String(item.number).padStart(2, "0")}</th>`)
        .join("")}</tr></thead>
      <tbody>${positions
        .map(
          (position) => `
            <tr>
              <th>${position.position}</th>
              ${position.values
                .map(
                  (item) => `
                    <td style="background:${singleScale(item.rate / max)}"
                      title="Vị trí ${position.position}, số ${item.number}: ${formatPercent(item.rate)}">
                      ${item.count ? formatTinyRate(item.rate) : ""}
                    </td>`,
                )
                .join("")}
            </tr>`,
        )
        .join("")}</tbody>
    </table>`;
}

function renderStructureSummary(structure) {
  const groups = [
    ["Số lượng số lẻ", structure.odd_count_distribution],
    ["Số cặp liên tiếp", structure.consecutive_pair_distribution],
  ];
  document.getElementById("structure-summary").innerHTML = groups
    .map(
      ([title, rows]) => `
        <div class="structure-group">
          <h4>${escapeHtml(title)}</h4>
          <div class="distribution-pills">
            ${rows
              .map(
                (row) => `
                  <span class="distribution-pill">
                    ${row.value}: <strong>${numberFormatter.format(row.count)}</strong>
                  </span>`,
              )
              .join("")}
          </div>
        </div>`,
    )
    .join("");
}

function renderPairTable(pairs) {
  const panel = document.getElementById("pair-panel");
  if (!pairs) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const rows = pairs.highest_residuals.slice(0, 10);
  document.getElementById("pair-table").innerHTML = table(
    ["Cặp", "Số lần", "Kỳ vọng", "Tỷ lệ", "Mức lệch"],
    rows.map((row) => [
      row.pair.map((value) => String(value).padStart(2, "0")).join(" + "),
      numberFormatter.format(row.count),
      formatDecimal(row.expected_count, 1),
      `${formatDecimal(row.ratio_to_expected, 2)}x`,
      formatSigned(row.z_score),
    ]),
  );
}

function renderDigitAnalysis(analysis) {
  const maxDigit = Math.max(...analysis.digits.map((item) => item.count), 1);
  renderBars(
    "digit-chart",
    analysis.digits.map((item) => ({
      label: String(item.digit),
      value: item.count,
      display: formatPercent(item.rate),
      className: "warm",
      maximum: maxDigit,
    })),
  );
  renderDigitPositionHeatmap(analysis.positions);
  renderHistogram("digit-sum-histogram", counterRowsToHistogram(analysis.sum_distribution), "Tổng chữ số");
  const maxUnique = Math.max(...analysis.unique_digit_distribution.map((item) => item.count), 1);
  renderBars(
    "digit-unique-chart",
    analysis.unique_digit_distribution.map((item) => ({
      label: `${item.value} chữ số`,
      value: item.count,
      display: numberFormatter.format(item.count),
      className: "",
      maximum: maxUnique,
    })),
  );
  document.getElementById("sequence-table").innerHTML = table(
    ["Thứ hạng", "Chuỗi", "Số lần"],
    analysis.most_frequent_sequences.map((item, index) => [
      index + 1,
      item.sequence,
      numberFormatter.format(item.count),
    ]),
  );
}

function renderDigitPositionHeatmap(positions) {
  const allRates = positions.flatMap((position) => position.values.map((item) => item.rate));
  const max = Math.max(...allRates, 0.001);
  document.getElementById("digit-position-heatmap").innerHTML = `
    <table class="heatmap" style="min-width:520px">
      <thead><tr><th>Vị trí</th>${Array.from({ length: 10 }, (_, digit) => `<th>${digit}</th>`).join("")}</tr></thead>
      <tbody>${positions
        .map(
          (position) => `
            <tr><th>${position.position}</th>${position.values
              .map(
                (item) => `
                  <td style="background:${singleScale(item.rate / max)}"
                    title="Vị trí ${position.position}, chữ số ${item.digit}: ${formatPercent(item.rate)}">
                    ${formatPercent(item.rate, 0)}
                  </td>`,
              )
              .join("")}</tr>`,
        )
        .join("")}</tbody>
    </table>`;
}

function renderHistogram(containerId, bins, label) {
  const width = 620;
  const height = 260;
  const margin = { top: 12, right: 10, bottom: 42, left: 42 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;
  const maximum = Math.max(...bins.map((item) => item.count), 1);
  const barWidth = chartWidth / Math.max(bins.length, 1);
  const bars = bins
    .map((item, index) => {
      const barHeight = (item.count / maximum) * chartHeight;
      const x = margin.left + index * barWidth;
      const y = margin.top + chartHeight - barHeight;
      const tick =
        bins.length <= 16 || index % Math.ceil(bins.length / 10) === 0
          ? `<text x="${x + barWidth / 2}" y="${height - 18}" text-anchor="middle">${escapeHtml(String(item.start))}</text>`
          : "";
      return `
        <rect x="${x + 1}" y="${y}" width="${Math.max(1, barWidth - 2)}" height="${barHeight}"
          rx="3" fill="#64c8c3">
          <title>${label} ${item.start}${item.end !== item.start ? `-${item.end}` : ""}: ${numberFormatter.format(item.count)}</title>
        </rect>${tick}`;
    })
    .join("");
  document.getElementById(containerId).innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(label)}">
      <line x1="${margin.left}" y1="${margin.top + chartHeight}" x2="${width - margin.right}" y2="${margin.top + chartHeight}" stroke="#c9c7bd"/>
      <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${margin.top + chartHeight}" stroke="#c9c7bd"/>
      ${bars}
      <text x="${margin.left - 8}" y="${margin.top + 5}" text-anchor="end">${compactFormatter.format(maximum)}</text>
      <text x="${width / 2}" y="${height - 2}" text-anchor="middle">${escapeHtml(label)}</text>
    </svg>`;
}

function counterRowsToHistogram(rows) {
  return rows.map((row) => ({ start: row.value, end: row.value, count: row.count }));
}

function renderBacktest(backtest, kind) {
  const container = document.getElementById("backtest-report");
  if (!backtest || backtest.status !== "complete") {
    container.innerHTML = '<p class="method-note">Chưa đủ dữ liệu để backtest.</p>';
    return;
  }
  const modelValue =
    kind === "number_set"
      ? backtest.model.average_hits
      : backtest.model.average_best_position_matches;
  const baselineValue =
    kind === "number_set"
      ? backtest.baseline.average_hits
      : backtest.baseline.average_best_position_matches;
  const unit = kind === "number_set" ? "số trùng mỗi kỳ" : "vị trí trùng tốt nhất";
  const comparisonValue =
    kind === "number_set"
      ? backtest.comparison.mean_hit_difference
      : backtest.comparison.mean_position_match_difference;
  const conclusion = backtest.comparison.beats_baseline
    ? "Trong bài thử này, cách kết hợp dấu hiệu đang tốt hơn mốc ngẫu nhiên, nhưng chưa đủ để khuyên chọn số."
    : "Kết luận: cách kết hợp dấu hiệu chưa tốt hơn chọn ngẫu nhiên.";
  container.innerHTML = `
    <div class="backtest-score">
      <div class="backtest-side model">
        <span>Kết hợp ba dấu hiệu</span>
        <strong>${formatDecimal(modelValue, 3)}</strong>
        <small>${escapeHtml(unit)}</small>
      </div>
      <span class="backtest-vs">SO VỚI</span>
      <div class="backtest-side">
        <span>Chọn ngẫu nhiên</span>
        <strong>${formatDecimal(baselineValue, 3)}</strong>
        <small>${escapeHtml(unit)}</small>
      </div>
    </div>
    <p class="backtest-verdict">${escapeHtml(conclusion)}</p>
    <details class="technical-details">
      <summary>Xem chi tiết học thuật</summary>
      <p>
        Chênh lệch ${formatSigned(comparisonValue)}, p xấp xỉ
        ${formatPValue(backtest.comparison.approximate_p_value)} trên
        ${numberFormatter.format(backtest.samples)} kỳ kiểm tra.
      </p>
    </details>`;
}

function renderPrizeReport(prizes) {
  const metrics = [
    ["Kỳ có dữ liệu giải", numberFormatter.format(prizes.draws_with_prizes)],
    ["Dòng giải", numberFormatter.format(prizes.rows)],
    ["Lượt trúng công bố", compactFormatter.format(prizes.reported_winners)],
    ["Giá trị giải lớn nhất", prizes.largest_prize_value_vnd ? formatMoney(prizes.largest_prize_value_vnd) : "Chưa có"],
  ];
  document.getElementById("prize-report").innerHTML = metrics
    .map(
      ([label, value]) => `
        <div class="prize-metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>`,
    )
    .join("");
}

function renderRecentDraws(draws, kind) {
  document.getElementById("recent-draws").innerHTML = draws
    .map((draw) => {
      let result;
      if (kind === "number_set") {
        result = `
          <div class="draw-balls">
            ${draw.result.numbers.map((value) => `<span class="ball">${String(value).padStart(2, "0")}</span>`).join("")}
            ${draw.result.special_numbers.map((value) => `<span class="ball special">${String(value).padStart(2, "0")}</span>`).join("")}
          </div>`;
      } else {
        const outcomes = draw.result.outcomes.slice(0, 12);
        result = `
          <div>${outcomes.map((value) => `<span class="sequence-chip">${escapeHtml(value)}</span>`).join("")}</div>
          ${draw.result.outcomes.length > outcomes.length ? `<small>và ${draw.result.outcomes.length - outcomes.length} kết quả khác</small>` : ""}`;
      }
      return `
        <article class="draw-card">
          <div class="draw-meta">
            <span>#${escapeHtml(draw.draw_id)}</span>
            <time>${formatDate(draw.draw_date)}</time>
          </div>
          ${result}
        </article>`;
    })
    .join("");
}

function renderPredictionShell(predictions, products) {
  text("pending-predictions", numberFormatter.format(predictions.pending_count));
  text("evaluated-predictions", numberFormatter.format(predictions.evaluation_count));
  text("prediction-version", predictions.model_version);
  const select = document.getElementById("prediction-product");
  const available = products.filter((product) => predictions.latest[product.slug]);
  select.innerHTML = available
    .map(
      (product) =>
        `<option value="${escapeHtml(product.slug)}">${escapeHtml(product.name)}</option>`,
    )
    .join("");
  select.value = available.some((item) => item.slug === "power655")
    ? "power655"
    : available[0]?.slug;
  select.addEventListener("change", () => renderPredictionCards(select.value));
  renderPredictionCards(select.value);
}

function renderPredictionCards(slug) {
  const predictions = state.predictions.latest[slug] || [];
  const product = state.manifest.products.find((item) => item.slug === slug);
  const latest = predictions[0];
  text(
    "prediction-ledger-status",
    latest
      ? `Dùng dữ liệu đến kỳ #${latest.dataset_cutoff_draw_id} ngày ${formatDate(latest.dataset_cutoff_date)}`
      : "Chưa có dự đoán",
  );
  document.getElementById("prediction-cards").innerHTML = predictions
    .map((prediction) => {
      const copy = predictionStrategyCopy(prediction.strategy);
      const values = prediction.prediction.numbers;
      const output = values
        ? `
          <div class="prediction-values">
            ${values.map((value) => `<span class="ball">${String(value).padStart(2, "0")}</span>`).join("")}
            ${(prediction.prediction.special_numbers || []).map((value) => `<span class="ball special">${String(value).padStart(2, "0")}</span>`).join("")}
          </div>`
        : `<div class="prediction-sequence">${escapeHtml(prediction.prediction.sequence)}</div>`;
      return `
        <article class="prediction-card${prediction.strategy === "balanced_signal" ? " primary" : ""}">
          <span class="strategy-name">${escapeHtml(copy.title)}</span>
          <p class="strategy-description">${escapeHtml(copy.description)}</p>
          ${output}
          <div class="prediction-meta">
            <span>Mã lưu vết ${escapeHtml(prediction.prediction_id)}</span>
            <span>Dữ liệu đến kỳ #${escapeHtml(prediction.dataset_cutoff_draw_id)}</span>
            <span>Cách tính phiên bản ${escapeHtml(prediction.model_version)}</span>
          </div>
        </article>`;
    })
    .join("");
  if (!predictions.length) {
    document.getElementById("prediction-cards").innerHTML =
      '<div class="error-card">Chưa có dự đoán cho sản phẩm này.</div>';
  }
  if (product) document.getElementById("prediction-product").value = product.slug;
}

function predictionStrategyCopy(strategy) {
  const copy = {
    uniform_seeded: {
      title: "Chọn ngẫu nhiên có thể lặp lại",
      description: "Mốc so sánh công bằng. Mã lưu vết giúp tạo lại đúng bộ số này.",
    },
    recent_frequency: {
      title: "Ưu tiên số nổi bật gần đây",
      description: "Chọn các số lệch nhiều trong nhóm kỳ quay gần nhất.",
    },
    balanced_signal: {
      title: "Kết hợp ba dấu hiệu lịch sử",
      description: "Gộp tần suất gần đây, toàn lịch sử và số kỳ vắng mặt.",
    },
  };
  return copy[strategy] || {
    title: strategy.replaceAll("_", " "),
    description: "Một phương pháp thử nghiệm được lưu để đối chiếu sau.",
  };
}

function table(headers, rows) {
  return `
    <table class="data-table">
      <thead><tr>${headers.map((header) => `<th>${escapeHtml(String(header))}</th>`).join("")}</tr></thead>
      <tbody>${rows
        .map(
          (row) =>
            `<tr>${row.map((cell) => `<td>${escapeHtml(String(cell))}</td>`).join("")}</tr>`,
        )
        .join("")}</tbody>
    </table>`;
}

function residualColor(value) {
  const clamped = Math.max(-1, Math.min(1, value));
  if (clamped < 0) {
    const lightness = 92 - Math.abs(clamped) * 24;
    return `hsl(218 48% ${lightness}%)`;
  }
  const lightness = 92 - clamped * 25;
  return `hsl(10 70% ${lightness}%)`;
}

function singleScale(value) {
  const clamped = Math.max(0, Math.min(1, value));
  return `hsl(177 42% ${94 - clamped * 46}%)`;
}

function formatTinyRate(value) {
  if (!value) return "";
  if (value < 0.01) return "<1%";
  return `${Math.round(value * 100)}%`;
}

function formatNumber(value) {
  return numberFormatter.format(value);
}

function formatDecimal(value, digits = 2) {
  return Number(value).toLocaleString("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function formatSigned(value, digits = 2) {
  const number = Number(value);
  return `${number >= 0 ? "+" : ""}${formatDecimal(number, digits)}`;
}

function formatPercent(value, digits = 1) {
  return Number(value).toLocaleString("vi-VN", {
    style: "percent",
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function formatPValue(value) {
  const number = Number(value);
  if (number < 0.000001) return "< 0,000001";
  return formatDecimal(number, 6);
}

function formatMoney(value) {
  if (value >= 1_000_000_000) return `${formatDecimal(value / 1_000_000_000, 2)} tỷ`;
  if (value >= 1_000_000) return `${formatDecimal(value / 1_000_000, 1)} triệu`;
  return `${numberFormatter.format(value)} đ`;
}

function formatDate(value) {
  if (!value) return "Chưa rõ";
  const [year, month, day] = String(value).slice(0, 10).split("-");
  return `${day}/${month}/${year}`;
}

function text(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showDashboardError(error) {
  const loading = document.getElementById("dashboard-loading");
  loading.hidden = false;
  document.getElementById("dashboard").hidden = true;
  loading.innerHTML =
    `<div class="error-card">${escapeHtml(error.message)}</div>`;
  console.error(error);
}

function showDashboardLoading(message) {
  const loading = document.getElementById("dashboard-loading");
  loading.innerHTML = `
    <span class="loader" aria-hidden="true"></span>
    <span id="dashboard-loading-label">${escapeHtml(message)}</span>`;
  loading.hidden = false;
}

function showFatalError(error) {
  showDashboardError(error);
  document.getElementById("hero-draw-count").textContent = "Lỗi dữ liệu";
}
