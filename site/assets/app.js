const state = {
  manifest: null,
  predictions: null,
  auditSummary: null,
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
  const [manifest, predictions, auditSummary] = await Promise.all([
    fetchJson("data/manifest.json"),
    fetchJson("data/predictions.json"),
    fetchJson("data/audit-summary.json"),
  ]);
  state.manifest = manifest;
  state.predictions = predictions;
  state.auditSummary = auditSummary;
  renderManifest(manifest);
  renderAuditOverview(auditSummary);
  renderProductTabs(manifest.products);
  renderPredictionShell(predictions, manifest.products);

  const requested = new URLSearchParams(window.location.search).get("product");
  const initial = manifest.products.some((item) => item.slug === requested)
    ? requested
    : "power655";
  await selectProduct(initial);
  renderProjectVerdict(manifest.products, manifest.backtest_summary).catch((error) => {
    console.error("Không tổng hợp được kết luận toàn bộ sản phẩm", error);
  });
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

async function renderProjectVerdict(products, backtestSummary) {
  const settled = await Promise.allSettled(
    products.map((product) => loadProductReport(product.slug)),
  );
  const reports = settled
    .filter((result) => result.status === "fulfilled")
    .map((result) => result.value)
    .filter((report) => report.backtest?.status === "complete");
  const wins = reports.filter((report) => {
    const backtest = report.backtest;
    return (
      backtest.comparison?.beats_baseline
      || backtest.recent_comparison?.beats_baseline
      || backtest.audit_comparison?.beats_baseline
    );
  }).length;
  const adjustedComparisons = reports.reduce((count, report) => (
    count
    + Number(Boolean(report.backtest.comparison?.beats_baseline))
    + Number(Boolean(report.backtest.recent_comparison?.beats_baseline))
    + Number(Boolean(report.backtest.audit_comparison?.beats_baseline))
  ), 0);
  const unadjustedComparisons = reports.reduce((count, report) => (
    count
    + Number(Boolean(report.backtest.comparison?.beats_baseline_unadjusted))
    + Number(Boolean(report.backtest.recent_comparison?.beats_baseline_unadjusted))
    + Number(Boolean(report.backtest.audit_comparison?.beats_baseline_unadjusted))
  ), 0);

  if (!reports.length) {
    text("verdict-backtest-count", "Chưa đủ dữ liệu");
    text("backtest-overview-summary", "Chưa đọc được báo cáo");
    text(
      "project-verdict-summary",
      "Chưa đọc được báo cáo để đưa ra kết luận tổng hợp.",
    );
    return;
  }

  text("verdict-backtest-count", `${wins}/${reports.length}`);
  const conclusion = wins === 0
    ? `Không sản phẩm nào trong ${reports.length} báo cáo vượt mốc ngẫu nhiên sau hiệu chỉnh nhiều phép thử.`
    : `${wins} trong ${reports.length} sản phẩm có ít nhất một chiến lược vượt mốc ngẫu nhiên sau hiệu chỉnh, nhưng vẫn cần xác nhận bằng dự đoán đã lưu trước.`;
  text("project-verdict-summary", conclusion);
  text(
    "backtest-correction-summary",
    `${adjustedComparisons} tín hiệu qua hiệu chỉnh; ${unadjustedComparisons} tín hiệu thô có p < 0,05 trên ${backtestSummary?.comparison_count ?? reports.length * 3} phép so sánh.`,
  );
  renderBacktestOverview(reports);
  text(
    "prediction-current-conclusion",
    `${conclusion} ${predictionOutcomeConclusion()} Các bộ số dưới đây là thí nghiệm, không phải gợi ý mua vé.`,
  );
}

function renderBacktestOverview(reports) {
  const container = document.getElementById("backtest-overview-list");
  if (!container) return;
  const rows = reports.map((report) => {
    const backtest = report.backtest;
    const kind = report.product.kind;
    const comparisons = [
      { label: "Kết hợp ba dấu hiệu", comparison: backtest.comparison },
      backtest.recent_comparison
        ? {
            label: "Tần suất cửa sổ gần",
            comparison: backtest.recent_comparison,
          }
        : null,
      backtest.audit_comparison
        ? {
            label: "Khai thác kiểm định công bằng",
            comparison: backtest.audit_comparison,
          }
        : null,
    ].filter(Boolean);
    const winners = comparisons.filter((item) => item.comparison?.beats_baseline);
    const rawSignals = comparisons.filter(
      (item) => item.comparison?.beats_baseline_unadjusted,
    );
    const status = winners.length
      ? "Vượt sau hiệu chỉnh"
      : rawSignals.length
        ? "Có tín hiệu thô, chưa qua hiệu chỉnh"
        : "Chưa vượt baseline";
    const evidence = comparisons.map((item) => {
      const difference = kind === "number_set"
        ? item.comparison.mean_hit_difference
        : item.comparison.mean_position_match_difference;
      return `
        <li class="${item.comparison.beats_baseline ? "is-winner" : ""}">
          <span>${escapeHtml(item.label)}</span>
          <strong>${formatSigned(difference)}</strong>
          <small>
            p ${formatPValue(item.comparison.approximate_p_value)}
            · q ${formatPValue(item.comparison.q_value_global_bh)}
          </small>
        </li>`;
    }).join("");
    return `
      <article class="backtest-overview-row ${winners.length ? "has-winner" : ""}">
        <div>
          <span>${escapeHtml(report.product.name)}</span>
          <strong>${escapeHtml(status)}</strong>
          <small>${numberFormatter.format(backtest.samples)} kỳ kiểm tra</small>
        </div>
        <ul>${evidence}</ul>
      </article>`;
  });
  const winningStrategies = reports.reduce((count, report) => (
    count
    + Number(Boolean(report.backtest.comparison?.beats_baseline))
    + Number(Boolean(report.backtest.recent_comparison?.beats_baseline))
    + Number(Boolean(report.backtest.audit_comparison?.beats_baseline))
  ), 0);
  const rawSignals = reports.reduce((count, report) => (
    count
    + Number(Boolean(report.backtest.comparison?.beats_baseline_unadjusted))
    + Number(Boolean(report.backtest.recent_comparison?.beats_baseline_unadjusted))
    + Number(Boolean(report.backtest.audit_comparison?.beats_baseline_unadjusted))
  ), 0);
  text(
    "backtest-overview-summary",
    `${reports.filter((report) => (
      report.backtest.comparison?.beats_baseline
      || report.backtest.recent_comparison?.beats_baseline
      || report.backtest.audit_comparison?.beats_baseline
    )).length}/${reports.length} sản phẩm; ${winningStrategies} tín hiệu qua hiệu chỉnh; ${rawSignals} tín hiệu thô`,
  );
  container.innerHTML = `
    <p class="backtest-overview-note">
      Baseline là điểm kỳ vọng chính xác của cách chọn đồng đều, không phải kết quả
      của một lần bốc ngẫu nhiên. Chỉ ghi nhận vượt baseline khi chênh lệch dương và
      q Benjamini-Hochberg toàn hệ thống nhỏ hơn 0,05. p thô vẫn được công bố để
      người đọc kiểm tra tác động của hiệu chỉnh.
    </p>
    ${rows.join("")}`;
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
  text("ribbon-product-count", numberFormatter.format(manifest.products.length));
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
  const { product, summary, analysis, backtest, audit, weather } = report;
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
  renderFairnessAudit(audit);
  renderWeatherReport(weather);
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
  const quality = summary.data_quality || {};
  const resultCoverage = Number(quality.result_coverage_rate || 0);
  const prizeCoverage = Number(quality.prize_coverage_rate || 0);
  const officialRate = Number(quality.official_source_rate || 0);
  const crossCheckedRate = Number(quality.cross_checked_rate || 0);
  const sourceNames = Object.entries(quality.source_origins || {})
    .sort((left, right) => right[1] - left[1])
    .slice(0, 2)
    .map(([name]) => sourceOriginLabel(name))
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
      label: "Độ phủ kết quả",
      value: formatPercent(resultCoverage),
      note: `${numberFormatter.format(quality.result_coverage_rows || 0)} dòng có kết quả`,
    },
    {
      label: "Độ phủ giải thưởng",
      value: formatPercent(prizeCoverage),
      note: `${numberFormatter.format(quality.prize_coverage_draws || 0)} kỳ có bảng giải chi tiết`,
    },
    {
      label: "Nguồn chính thức rõ provenance",
      value: formatPercent(officialRate),
      note: sourceNames || "Chưa phân loại được nguồn",
    },
    {
      label: "Đã đối chiếu nhiều nguồn",
      value: formatPercent(crossCheckedRate),
      note: `${numberFormatter.format(quality.cross_checked_rows || 0)} dòng có bằng chứng đối chiếu`,
    },
    {
      label: "Ngày có dữ liệu",
      value: numberFormatter.format(summary.calendar_days_with_draws),
      note: `${formatDecimal(summary.average_draws_per_active_day)} kỳ mỗi ngày hoạt động`,
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

function sourceOriginLabel(value) {
  const labels = {
    official: "Chính thức",
    secondary: "Nguồn phụ",
    community: "Gương cộng đồng",
    unknown: "Chưa truy ngược",
  };
  return labels[value] || value.replaceAll("_", " ");
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

  const entropy = uniformity.normalized_entropy;
  const metrics = [
    [
      "Mức bất thường",
      formatPValue(pValue),
      pValue >= 0.05
        ? "Chưa bất thường. p nằm từ 0 đến 1; càng nhỏ càng khó giải thích bằng dao động ngẫu nhiên."
        : "Có tín hiệu thống kê. p dưới 0,05 cần được kiểm tra tiếp và hiệu chỉnh khi thử nhiều phép kiểm.",
    ],
    [
      "Độ lệch thực tế",
      formatDecimal(effect, 4),
      effect < 0.1
        ? "Rất nhỏ. Cohen's w bắt đầu từ 0, không có trần cố định; 0,1 thường được xem là mức nhỏ."
        : effect < 0.3
          ? "Nhỏ. Mốc tham khảo Cohen's w là 0,1 nhỏ, 0,3 vừa và 0,5 lớn."
          : effect < 0.5
            ? "Vừa. Mốc tham khảo Cohen's w là 0,1 nhỏ, 0,3 vừa và 0,5 lớn."
            : "Lớn theo mốc Cohen's w từ 0,5 trở lên.",
    ],
    [
      "Độ đồng đều",
      formatDecimal(entropy, 6),
      entropy >= 0.99
        ? "Rất gần đồng đều. Chỉ số nằm từ 0 đến 1; càng gần 1, tần suất càng phân tán đều."
        : entropy >= 0.9
          ? "Khá đồng đều. Chỉ số nằm từ 0 đến 1 và càng gần 1 càng đồng đều."
          : "Phân bố tập trung hơn. Chỉ số nằm từ 0 đến 1 và càng thấp càng kém đồng đều.",
    ],
  ];
  document.getElementById("test-metrics").innerHTML = metrics
    .map(
      ([label, value, note]) => `
        <div class="test-metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
          <small>${escapeHtml(note)}</small>
        </div>`,
    )
    .join("");
}

function renderAuditOverview(report) {
  if (!report) return;
  const summary = report.summary || report;
  const counts = summary.status_counts || {};
  const singleCondition =
    Number(counts.statistically_notable || 0)
    + Number(counts.practically_large || 0);
  text("audit-test-count", numberFormatter.format(summary.test_count || 0));
  text("audit-review-count", numberFormatter.format(counts.both || 0));
  text("audit-watch-count", numberFormatter.format(singleCondition));
  text("audit-global-conclusion", summary.conclusion || "Chưa có kết luận kiểm định.");
  text(
    "audit-log-summary",
    `${numberFormatter.format(summary.test_count || 0)} kiểm định, `
    + `${numberFormatter.format(summary.product_count || 0)} sản phẩm, `
    + `${numberFormatter.format(counts.both || 0)} đạt cả hai điều kiện, `
    + `${numberFormatter.format(singleCondition)} chỉ đạt một điều kiện`,
  );
  renderAuditVisualLog(report);
}

function renderAuditVisualLog(report) {
  const container = document.getElementById("audit-log-visual");
  if (!container) return;
  const summary = report.summary || {};
  const products = report.products || [];
  const strongest = summary.strongest_signal;
  const statusCounts = summary.status_counts || {};
  const productsHtml = [...products]
    .sort((left, right) => auditProductRank(left) - auditProductRank(right))
    .map(renderAuditProductCard)
    .join("");
  container.innerHTML = `
    <div class="audit-log-lead">
      <div>
        <span>Tóm tắt toàn cục</span>
        <strong>${escapeHtml(summary.conclusion || "Chưa có kết luận.")}</strong>
      </div>
      <div class="audit-log-statuses">
        ${renderAuditStatusPill("pass", statusCounts.pass || 0)}
        ${renderAuditStatusPill("statistically_notable", statusCounts.statistically_notable || 0)}
        ${renderAuditStatusPill("practically_large", statusCounts.practically_large || 0)}
        ${renderAuditStatusPill("both", statusCounts.both || 0)}
        ${renderAuditStatusPill("skipped", statusCounts.skipped || 0)}
      </div>
    </div>
    ${strongest ? `
      <article class="audit-signal-card ${escapeHtml(strongest.status)}">
        <span>Tín hiệu mạnh nhất trong snapshot</span>
        <strong>${escapeHtml(strongest.label)}</strong>
        <p>
          ${escapeHtml(strongest.algorithm)}.
          q toàn cục ${formatPValue(strongest.q_value_global_bh ?? strongest.q_value_bh)}.
          ${escapeHtml(strongest.interpretation)}
        </p>
      </article>` : ""}
    ${renderAuditThresholdSensitivity(report)}
    <div class="audit-log-products">
      ${productsHtml}
    </div>`;
}

function renderAuditThresholdSensitivity(report) {
  const sensitivity = report.threshold_sensitivity;
  const globalRows = sensitivity?.global || [];
  if (!globalRows.length) return "";
  const thresholds = report.effect_thresholds || [];
  const rows = globalRows.map((row) => `
    <div>
      <dt>${formatDecimal(row.threshold_multiplier, 1)}x</dt>
      <dd>
        ${numberFormatter.format(row.practically_large_count)}
        <small>${numberFormatter.format(row.both_count)} đạt cả hai</small>
      </dd>
    </div>`).join("");
  return `
    <article class="audit-signal-card pass threshold-sensitivity-card">
      <span>Độ nhạy ngưỡng hiệu ứng</span>
      <strong>${numberFormatter.format(thresholds.length)} ngưỡng đã khóa, rà soát theo 4 mức</strong>
      <p>
        Các mức dưới đây đếm lại số phép kiểm đạt độ lớn thực dụng nếu nhân ngưỡng
        với hệ số tương ứng. Mức 1,0x là luật đang dùng trong báo cáo.
      </p>
      <dl class="threshold-sensitivity-grid">${rows}</dl>
    </article>`;
}

function renderAuditProductCard(product) {
  const counts = product.status_counts || {};
  const status = auditProductStatus(product);
  const signal = product.strongest_signal;
  const qValue = signal?.q_value_global_bh ?? signal?.q_value_bh;
  const reliability = product.reliability_sensitivity || {};
  return `
    <article class="audit-product-card ${escapeHtml(status)}">
      <div class="audit-product-top">
        <div>
          <span>${escapeHtml(auditStatusLabel(status))}</span>
          <strong>${escapeHtml(product.name)}</strong>
        </div>
        <small>${numberFormatter.format(product.history_draws || 0)} kỳ</small>
      </div>
      <div class="audit-status-pills">
        ${renderAuditStatusPill("pass", counts.pass || 0)}
        ${renderAuditStatusPill("statistically_notable", counts.statistically_notable || 0)}
        ${renderAuditStatusPill("practically_large", counts.practically_large || 0)}
        ${renderAuditStatusPill("both", counts.both || 0)}
        ${renderAuditStatusPill("skipped", counts.skipped || 0)}
      </div>
      ${signal ? `
        <p class="audit-signal">
          <b>${escapeHtml(signal.label)}</b>
          <span>${escapeHtml(signal.algorithm)}</span>
          <em>q ${qValue == null ? "N/A" : formatPValue(qValue)}</em>
        </p>` : ""}
      ${renderAuditProductReliabilityNote(reliability)}
      <p>${escapeHtml(product.conclusion || "")}</p>
    </article>`;
}

function renderAuditProductReliabilityNote(reliability) {
  if (!reliability || !reliability.status) return "";
  const low = reliability.low_reliability_confirmed_draws || 0;
  const filtered = reliability.filtered_confirmed_draws || 0;
  return `
    <p class="audit-reliability-note">
      <b>${escapeHtml(reliabilityStatusLabel(reliability.status))}</b>
      <span>${numberFormatter.format(low)} kỳ provenance thấp · ${numberFormatter.format(filtered)} kỳ trong lát tin cậy</span>
    </p>`;
}

function renderAuditStatusPill(status, value) {
  return `
    <span class="audit-status-pill ${escapeHtml(status)}">
      ${escapeHtml(auditStatusLabel(status))}
      <b>${numberFormatter.format(value)}</b>
    </span>`;
}

function auditProductStatus(product) {
  const counts = product.status_counts || {};
  if (counts.both) return "both";
  if (counts.statistically_notable) return "statistically_notable";
  if (counts.practically_large) return "practically_large";
  if (counts.skipped) return "skipped";
  return "pass";
}

function auditProductRank(product) {
  const order = {
    both: 0,
    statistically_notable: 1,
    practically_large: 2,
    skipped: 3,
    pass: 4,
  };
  return order[auditProductStatus(product)] ?? 4;
}

function auditStatusLabel(status) {
  const labels = {
    pass: "Bình thường",
    statistically_notable: "Nổi bật thống kê",
    practically_large: "Độ lớn thực dụng",
    both: "Đạt cả hai",
    skipped: "Tạm hoãn",
  };
  return labels[status] || status;
}

function renderFairnessAudit(audit) {
  if (!audit) return;
  const counts = audit.status_counts || {};
  const both = counts.both || 0;
  const statisticallyNotable = counts.statistically_notable || 0;
  const practicallyLarge = counts.practically_large || 0;
  const pass = counts.pass || 0;
  const powerSummary = audit.power_summary || {};
  const reliability = audit.reliability_sensitivity || {};
  const reliabilityBaseline = reliability.baseline || {};
  const powerCoverage = powerSummary.supported_test_count
    ? `${numberFormatter.format(powerSummary.threshold_detectable_count || 0)}/${numberFormatter.format(powerSummary.supported_test_count)}`
    : "N/A";
  const verdict = both
    ? "Đạt cả hai điều kiện"
    : statisticallyNotable
      ? "Nổi bật thống kê, hiệu ứng nhỏ"
      : practicallyLarge
        ? "Độ lớn đáng chú ý, chưa đủ thống kê"
        : "Chưa thấy tín hiệu mạnh";
  text("audit-product-verdict", verdict);
  text("audit-product-conclusion", audit.conclusion);
  const metrics = [
    ["Kiểm định đã chạy", audit.tests.length],
    ["Đạt ngưỡng bình thường", pass],
    ["Nổi bật thống kê", statisticallyNotable],
    ["Độ lớn thực dụng", practicallyLarge],
    ["Đạt cả hai", both],
    ["Ngưỡng đủ công suất", powerCoverage],
    ["Kỳ chưa xác nhận đã loại", reliabilityBaseline.not_confirmed_rows || 0],
    ["Kỳ provenance thấp", reliability.low_reliability_confirmed_draws || 0],
    ["Chạy lại sau", `${numberFormatter.format(audit.audit_interval_draws)} kỳ`],
  ];
  document.getElementById("audit-product-metrics").innerHTML = metrics
    .map(
      ([label, value]) => `
        <article>
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </article>`,
    )
    .join("");

  const ranked = [...audit.tests].sort((left, right) => {
    const order = {
      both: 0,
      statistically_notable: 1,
      practically_large: 2,
      skipped: 3,
      pass: 4,
    };
    const leftRank = order[left.status] ?? 4;
    const rightRank = order[right.status] ?? 4;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return (left.q_value_global_bh || left.q_value_bh || 1)
      - (right.q_value_global_bh || right.q_value_bh || 1);
  });
  const highlightedTests = ranked.slice(0, 8);
  document.getElementById("audit-test-list").innerHTML = `
    ${renderAuditReliabilityPanel(audit)}
    <details class="audit-test-details">
      <summary>
        <span>Chi tiết kiểm định</span>
        <strong>${numberFormatter.format(highlightedTests.length)} phép kiểm nổi bật</strong>
      </summary>
      <div class="audit-test-list-inner">
        <aside class="audit-stat-guide">
          <strong>Cách đọc p, q và độ lớn</strong>
          <p><b>p gốc</b> nằm từ 0 đến 1. Số càng nhỏ thì kết quả càng khó xảy ra nếu mô hình tham chiếu đúng.</p>
          <p><b>q hiệu chỉnh</b> cũng nằm từ 0 đến 1, nhưng đã tính việc chạy nhiều phép kiểm. Khi kết luận, ưu tiên đọc q thay cho p.</p>
          <p><b>Độ lớn</b> cho biết sai lệch mạnh đến đâu. Thang đo thay đổi theo thuật toán, vì vậy phải so với "ngưỡng thực dụng" của chính phép kiểm đó.</p>
          <p><b>MDE 80%</b> là hiệu ứng nhỏ nhất xấp xỉ có thể phát hiện ở công suất 80% với mẫu hiện tại.</p>
        </aside>
        ${highlightedTests.map(renderAuditTestRow).join("")}
      </div>
    </details>
    ${renderAuditPositionResiduals(audit)}`;

  document.getElementById("audit-method-catalog").innerHTML = `
    <div class="audit-family-list">
      ${(audit.families || []).map((family) => `
        <article>
          <strong>${escapeHtml(family.label)}</strong>
          <span>${escapeHtml(family.plain_language)}</span>
        </article>`).join("")}
    </div>
    ${renderAuditDependencyMatrix(audit)}
    <p class="method-note">
      Nhóm thuật toán nặng như HMM, MCMC, TestU01 đầy đủ và deep learning chưa chạy tự động
      trong phiên bản này vì chi phí cao và dễ khó giải thích.
    </p>`;
}

function renderAuditReliabilityPanel(audit) {
  const sensitivity = audit.reliability_sensitivity;
  if (!sensitivity) return "";
  const baseline = sensitivity.baseline || {};
  const largest = sensitivity.largest_effect_shift;
  const rows = (sensitivity.comparisons || []).slice(0, 4);
  return `
    <article class="audit-reliability-panel ${escapeHtml(sensitivity.status || "unknown")}">
      <div class="audit-reliability-heading">
        <div>
          <span>Độ nhạy dữ liệu tin cậy</span>
          <strong>${escapeHtml(reliabilityStatusLabel(sensitivity.status))}</strong>
        </div>
        <p>${escapeHtml(sensitivity.interpretation || "")}</p>
      </div>
      <dl class="audit-reliability-metrics">
        <div><dt>Kỳ chưa xác nhận</dt><dd>${numberFormatter.format(baseline.not_confirmed_rows || 0)}</dd></div>
        <div><dt>Kỳ audit chính</dt><dd>${numberFormatter.format(baseline.confirmed_draws_in_audit || 0)}</dd></div>
        <div><dt>Provenance thấp</dt><dd>${numberFormatter.format(sensitivity.low_reliability_confirmed_draws || 0)}</dd></div>
        <div><dt>Lát tin cậy</dt><dd>${numberFormatter.format(sensitivity.filtered_confirmed_draws || 0)}</dd></div>
        <div><dt>Phép so lại</dt><dd>${numberFormatter.format(sensitivity.compared_test_count || 0)}</dd></div>
      </dl>
      ${largest ? `
        <p class="audit-reliability-strongest">
          <b>${escapeHtml(largest.label || largest.test_id)}</b>
          <span>Δ effect ${formatSigned(largest.effect_size_delta || 0, 4)} · mẫu ${numberFormatter.format(largest.filtered_sample_size || 0)}/${numberFormatter.format(largest.baseline_sample_size || 0)}</span>
        </p>` : ""}
      ${rows.length ? `
        <div class="audit-reliability-comparisons">
          ${rows.map((row) => `
            <div>
              <span>${escapeHtml(row.label)}</span>
              <strong>${formatSigned(row.effect_size_delta || 0, 4)}</strong>
              <small>${numberFormatter.format(row.filtered_sample_size || 0)}/${numberFormatter.format(row.baseline_sample_size || 0)} mẫu</small>
            </div>`).join("")}
        </div>` : ""}
    </article>`;
}

function reliabilityStatusLabel(status) {
  const labels = {
    available: "Đã so lại lát tin cậy",
    confirmed_only_baseline: "Baseline đã đủ tin cậy",
    insufficient_reliable_history: "Thiếu lát tin cậy",
    missing_confirmed_history: "Thiếu lịch sử confirmed",
  };
  return labels[status] || status || "Không rõ";
}

function renderAuditDependencyMatrix(audit) {
  const matrix = audit.dependency_matrix || {};
  const pairs = matrix.pairs || [];
  if (!pairs.length) return "";
  const counts = matrix.counts || {};
  const order = { high: 0, medium: 1, low: 2 };
  const labels = { high: "Cao", medium: "Vừa", low: "Thấp" };
  const highlightedPairs = [...pairs]
    .sort((left, right) => (order[left.dependency_strength] ?? 9) - (order[right.dependency_strength] ?? 9))
    .slice(0, 6);
  return `
    <section class="audit-dependency-panel" aria-labelledby="audit-dependency-title">
      <div class="audit-dependency-heading">
        <div>
          <span>Ma trận phụ thuộc</span>
          <strong id="audit-dependency-title">Phép kiểm nào đang nhìn cùng dữ liệu?</strong>
        </div>
        <p>${escapeHtml(matrix.note || "")}</p>
      </div>
      <div class="audit-dependency-grid">
        ${["high", "medium", "low"].map((key) => `
          <article class="${escapeHtml(key)}">
            <span>${escapeHtml(labels[key])}</span>
            <strong>${numberFormatter.format(counts[key] || 0)}</strong>
          </article>`).join("")}
      </div>
      <div class="audit-dependency-pairs">
        ${highlightedPairs.map((pair) => `
          <article class="${escapeHtml(pair.dependency_strength)}">
            <span>${escapeHtml(labels[pair.dependency_strength] || pair.dependency_strength)}</span>
            <strong>${escapeHtml(pair.left_label)} · ${escapeHtml(pair.right_label)}</strong>
            <p>${escapeHtml(pair.rationale)}</p>
            <small>${escapeHtml((pair.shared_tags || []).join(", "))}</small>
          </article>`).join("")}
      </div>
    </section>`;
}

function renderAuditPositionResiduals(audit) {
  const test = audit.tests.find((item) => item.id === "digit_position_chi_square");
  const residuals = test?.parameters?.position_residuals || [];
  if (!residuals.length) return "";
  const grouped = new Map();
  for (const item of residuals) {
    if (!grouped.has(item.position)) grouped.set(item.position, []);
    grouped.get(item.position).push(item);
  }
  const maxAbs = Math.max(
    2,
    ...residuals.map((item) => Math.abs(item.standardized_residual)),
  );
  return `
    <section class="position-residual-panel" aria-labelledby="position-residual-title">
      <div class="position-residual-heading">
        <div>
          <span>Phân rã kiểm định theo vị trí</span>
          <strong id="position-residual-title">Ô nào đóng góp nhiều vào độ lệch tổng?</strong>
        </div>
        <p>
          Residual dương nghĩa là xuất hiện nhiều hơn kỳ vọng, residual âm nghĩa là
          ít hơn. Mốc ±2 chỉ giúp định hướng đọc, không phải một kiểm định mới cho từng ô.
        </p>
      </div>
      <div class="position-residual-scroll">
        <div class="position-residual-grid">
          ${[...grouped.entries()].map(([position, rows]) => `
            <div class="position-residual-row">
              <span>Vị trí ${position}</span>
              ${rows.map((item) => `
                <div
                  style="background:${residualColor(item.standardized_residual / maxAbs)}"
                  title="Vị trí ${item.position}, số ${item.digit}: quan sát ${numberFormatter.format(item.observed)}, kỳ vọng ${formatDecimal(item.expected, 1)}, residual ${formatSigned(item.standardized_residual)}">
                  <b>${item.digit}</b>
                  <strong>${formatSigned(item.standardized_residual)}</strong>
                </div>`).join("")}
            </div>`).join("")}
        </div>
      </div>
      <small>${escapeHtml(test.parameters.residual_note || "")}</small>
      ${renderAuditTierBreakdown(test)}
      ${renderAuditPeriodBreakdown(test)}
      ${renderAuditSourceBreakdown(test)}
      ${renderAuditSourceLeaveOneOut(test)}
    </section>`;
}

function renderAuditTierBreakdown(test) {
  const breakdown = test.parameters?.tier_breakdown;
  if (!breakdown || breakdown.status === "not_applicable") return "";
  const tiers = breakdown.tiers || [];
  const resultTypes = breakdown.result_types || [];
  if (!tiers.length && !resultTypes.length) return "";
  return `
    <div class="position-tier-panel" aria-label="Phân rã theo hạng giải">
      <div class="position-tier-heading">
        <div>
          <span>Hạng giải và loại kết quả</span>
          <strong>Phân rã residual, không tạo p-value mới</strong>
        </div>
        <p>${escapeHtml(breakdown.interpretation || "")}</p>
      </div>
      <div class="position-result-types">
        ${resultTypes.map((item) => `
          <article class="${item.usable_for_position_audit ? "usable" : "excluded"}">
            <span>${escapeHtml(item.label || item.result_type)}</span>
            <strong>${numberFormatter.format(item.outcomes || 0)}</strong>
            <small>${escapeHtml(item.plain_language || "")}</small>
          </article>`).join("")}
      </div>
      <div class="position-tier-grid">
        ${tiers.map((tier) => `
          <article>
            <span>${escapeHtml(tier.tier_label || tier.tier)}</span>
            <strong>${numberFormatter.format(tier.outcomes || 0)} kết quả</strong>
            <dl>
              <div><dt>Số kỳ</dt><dd>${numberFormatter.format(tier.draws || 0)}</dd></div>
              <div><dt>Đóng góp χ²</dt><dd>${formatDecimal(tier.chi_square_contribution || 0, 3)}</dd></div>
              <div><dt>Độ lớn</dt><dd>${formatDecimal(tier.effect_size || 0, 4)}</dd></div>
              <div><dt>|residual|max</dt><dd>${formatDecimal(tier.max_abs_standardized_residual || 0, 3)}</dd></div>
            </dl>
          </article>`).join("")}
      </div>
    </div>`;
}

function renderAuditPeriodBreakdown(test) {
  const breakdown = test.parameters?.period_breakdown;
  const segments = breakdown?.segments || [];
  if (!breakdown || breakdown.status !== "available" || !segments.length) return "";
  return `
    <div class="position-period-panel" aria-label="Phân rã theo giai đoạn thời gian">
      <div class="position-period-heading">
        <div>
          <span>Giai đoạn không chồng lấn</span>
          <strong>Residual có lặp lại qua lịch sử không?</strong>
        </div>
        <p>${escapeHtml(breakdown.interpretation || "")}</p>
      </div>
      <div class="position-period-grid">
        ${segments.map((segment) => `
          <article>
            <header>
              <span>${escapeHtml(segment.segment_label || `Giai đoạn ${segment.segment_index}`)}</span>
              <strong>${formatDate(segment.start_date)} đến ${formatDate(segment.end_date)}</strong>
              <small>#${escapeHtml(segment.start_draw_id)} đến #${escapeHtml(segment.end_draw_id)}</small>
            </header>
            <dl>
              <div><dt>Số kỳ</dt><dd>${numberFormatter.format(segment.draws || 0)}</dd></div>
              <div><dt>Kết quả</dt><dd>${numberFormatter.format(segment.outcomes || 0)}</dd></div>
              <div><dt>Đóng góp χ²</dt><dd>${formatDecimal(segment.chi_square_contribution || 0, 3)}</dd></div>
              <div><dt>|residual|max</dt><dd>${formatDecimal(segment.max_abs_standardized_residual || 0, 3)}</dd></div>
            </dl>
            <div class="position-period-residuals">
              ${(segment.top_residuals || []).map((item) => `
                <span title="Vị trí ${item.position}, số ${item.digit}: quan sát ${numberFormatter.format(item.observed)}, kỳ vọng ${formatDecimal(item.expected, 1)}">
                  V${escapeHtml(item.position)}:${escapeHtml(item.digit)}
                  <b>${formatSigned(item.standardized_residual)}</b>
                </span>`).join("")}
            </div>
          </article>`).join("")}
      </div>
    </div>`;
}

function renderAuditSourceBreakdown(test) {
  const breakdown = test.parameters?.source_breakdown;
  const sources = breakdown?.sources || [];
  if (!breakdown || !sources.length) return "";
  const statusLabels = {
    available: "Đủ nguồn đối chứng",
    limited_comparison: "Đối chứng hạn chế",
    single_source: "Một nguồn chính",
    missing_source_metadata: "Thiếu metadata nguồn",
  };
  const sampleLabels = {
    usable: "Đủ mẫu mô tả",
    too_small: "Mẫu nhỏ",
  };
  return `
    <div class="position-source-panel" aria-label="Phân rã theo nguồn dữ liệu">
      <div class="position-source-heading">
        <div>
          <span>Nguồn dữ liệu</span>
          <strong>Tín hiệu có tập trung ở parser hoặc mirror nào không?</strong>
        </div>
        <p>${escapeHtml(breakdown.interpretation || "")}</p>
      </div>
      <div class="position-source-status">
        <span>${escapeHtml(statusLabels[breakdown.status] || breakdown.status)}</span>
        <strong>${numberFormatter.format(breakdown.eligible_source_count || 0)}/${numberFormatter.format(breakdown.source_count || sources.length)} nguồn đủ mẫu</strong>
      </div>
      <div class="position-source-grid">
        ${sources.map((source) => `
          <article class="${escapeHtml(source.sample_status || "unknown")}">
            <header>
              <span>${escapeHtml(sampleLabels[source.sample_status] || source.sample_status || "Không rõ")}</span>
              <strong>${escapeHtml(source.source_label || source.source_key)}</strong>
              <small>${renderSourceCounters(source.source_hosts)}</small>
            </header>
            <dl>
              <div><dt>Số kỳ</dt><dd>${numberFormatter.format(source.draws || 0)}</dd></div>
              <div><dt>Kết quả</dt><dd>${numberFormatter.format(source.outcomes || 0)}</dd></div>
              <div><dt>Đóng góp χ²</dt><dd>${source.chi_square_contribution == null ? "N/A" : formatDecimal(source.chi_square_contribution, 3)}</dd></div>
              <div><dt>|residual|max</dt><dd>${source.max_abs_standardized_residual == null ? "N/A" : formatDecimal(source.max_abs_standardized_residual, 3)}</dd></div>
            </dl>
            ${source.sample_note ? `<p>${escapeHtml(source.sample_note)}</p>` : ""}
            <div class="position-source-residuals">
              ${(source.top_residuals || []).map((item) => `
                <span title="Vị trí ${item.position}, số ${item.digit}: quan sát ${numberFormatter.format(item.observed)}, kỳ vọng ${formatDecimal(item.expected, 1)}">
                  V${escapeHtml(item.position)}:${escapeHtml(item.digit)}
                  <b>${formatSigned(item.standardized_residual)}</b>
                </span>`).join("")}
            </div>
          </article>`).join("")}
      </div>
    </div>`;
}

function renderAuditSourceLeaveOneOut(test) {
  const sensitivity = test.parameters?.source_leave_one_out;
  const rows = sensitivity?.excluded_sources || [];
  if (!sensitivity || !rows.length) return "";
  const statusLabels = {
    available: "Đủ lát còn lại",
    limited_comparison: "Có lát còn nhỏ",
    insufficient_remaining_data: "Thiếu mẫu còn lại",
    single_source: "Một nguồn chính",
    missing_source_metadata: "Thiếu metadata nguồn",
  };
  const sampleLabels = {
    usable: "Còn đủ mẫu",
    too_small: "Còn mẫu nhỏ",
  };
  const strongest = sensitivity.strongest_effect_shift;
  const strongestText = strongest
    ? `Dịch chuyển mạnh nhất khi bỏ ${strongest.excluded_source_label || strongest.excluded_source_key}: Δw ${formatSigned(strongest.effect_size_delta, 4)}`
    : "";
  return `
    <div class="position-source-sensitivity-panel" aria-label="Độ nhạy khi loại từng nguồn dữ liệu">
      <div class="position-source-sensitivity-heading">
        <div>
          <span>Độ nhạy loại nguồn</span>
          <strong>Bỏ một nguồn thì tín hiệu đổi bao nhiêu?</strong>
        </div>
        <p>${escapeHtml(sensitivity.interpretation || "")}</p>
      </div>
      <div class="position-source-sensitivity-status">
        <span>${escapeHtml(statusLabels[sensitivity.status] || sensitivity.status)}</span>
        <strong>${numberFormatter.format(sensitivity.eligible_source_count || 0)}/${numberFormatter.format(sensitivity.source_count || rows.length)} lát còn đủ mẫu</strong>
        ${strongestText ? `<em>${escapeHtml(strongestText)}</em>` : ""}
      </div>
      <div class="position-source-sensitivity-grid">
        ${rows.map((row) => `
          <article class="${escapeHtml(row.sample_status || "unknown")}">
            <header>
              <span>${escapeHtml(sampleLabels[row.sample_status] || row.sample_status || "Không rõ")}</span>
              <strong>Bỏ ${escapeHtml(row.excluded_source_label || row.excluded_source_key)}</strong>
              <small>${renderSourceCounters(row.excluded_source_hosts)}</small>
            </header>
            <dl>
              <div><dt>Nguồn bị loại</dt><dd>${numberFormatter.format(row.excluded_draws || 0)} kỳ</dd></div>
              <div><dt>Còn lại</dt><dd>${numberFormatter.format(row.remaining_outcomes || 0)} kết quả</dd></div>
              <div><dt>Δ độ lớn</dt><dd>${formatSigned(row.effect_size_delta || 0, 4)}</dd></div>
              <div><dt>Δ χ²</dt><dd>${formatSigned(row.statistic_delta || 0, 3)}</dd></div>
              <div><dt>Độ lớn còn lại</dt><dd>${formatDecimal(row.effect_size || 0, 4)}</dd></div>
              <div><dt>|residual|max</dt><dd>${formatDecimal(row.max_abs_standardized_residual || 0, 3)}</dd></div>
            </dl>
            ${row.sample_note ? `<p>${escapeHtml(row.sample_note)}</p>` : ""}
            <div class="position-source-sensitivity-residuals">
              ${(row.top_residuals || []).map((item) => `
                <span title="Vị trí ${item.position}, số ${item.digit}: quan sát ${numberFormatter.format(item.observed)}, kỳ vọng ${formatDecimal(item.expected, 1)}">
                  V${escapeHtml(item.position)}:${escapeHtml(item.digit)}
                  <b>${formatSigned(item.standardized_residual)}</b>
                </span>`).join("")}
            </div>
          </article>`).join("")}
      </div>
    </div>`;
}

function renderSourceCounters(rows = []) {
  if (!rows.length) return "không rõ host";
  return rows
    .slice(0, 2)
    .map((row) => `${row.key}: ${numberFormatter.format(row.count)}`)
    .join(" · ");
}

function renderAuditTestRow(test) {
  const qValue = test.q_value_global_bh ?? test.q_value_bh;
  const pValue = test.p_value == null ? "N/A" : formatPValue(test.p_value);
  const qDisplay = qValue == null ? "N/A" : formatPValue(qValue);
  const familyQ = test.q_value_dependency_family_bh == null
    ? "N/A"
    : formatPValue(test.q_value_dependency_family_bh);
  const effect = test.effect_size == null ? "N/A" : formatDecimal(test.effect_size, 4);
  const threshold = test.practical_effect_threshold == null
    ? "Không áp dụng"
    : formatDecimal(test.practical_effect_threshold, 4);
  const power = test.power_analysis || {};
  const mde80 = renderPowerMde(power, 0.8);
  const observedPower = power.status === "available" && power.observed_power != null
    ? formatPercent(power.observed_power)
    : "N/A";
  const permutation = renderPermutationCheck(test.parameters?.permutation_check);
  const bootstrap = renderBlockBootstrapCheck(test.parameters?.block_bootstrap_check);
  const changePoint = renderChangePointScan(test.parameters?.change_point_scan);
  return `
    <article class="audit-test-row ${escapeHtml(test.status)}">
      <div>
        <span>${escapeHtml(test.algorithm)}</span>
        <strong>${escapeHtml(test.label)}</strong>
        <p>${escapeHtml(test.plain_language)}</p>
      </div>
      <div class="audit-test-metrics">
        <dl>
          <div><dt>Trạng thái</dt><dd>${escapeHtml(auditStatusLabel(test.status))}</dd></div>
          <div><dt>p gốc</dt><dd>${escapeHtml(pValue)}</dd></div>
          <div><dt>q hiệu chỉnh</dt><dd>${escapeHtml(qDisplay)}</dd></div>
          <div><dt>q theo họ</dt><dd>${escapeHtml(familyQ)}</dd></div>
          <div><dt>Họ phụ thuộc</dt><dd>${escapeHtml(test.dependency_family_label || "Chưa phân nhóm")}</dd></div>
          <div><dt>Độ lớn</dt><dd>${escapeHtml(effect)}</dd></div>
          <div><dt>Ngưỡng thực dụng</dt><dd>${escapeHtml(threshold)}</dd></div>
          <div><dt>MDE 80%</dt><dd>${escapeHtml(mde80)}</dd></div>
          <div><dt>Công suất xấp xỉ</dt><dd>${escapeHtml(observedPower)}</dd></div>
        </dl>
        ${permutation}
        ${bootstrap}
        ${changePoint}
      </div>
    </article>`;
}

function renderPowerMde(power, targetPower) {
  if (!power || power.status !== "available") return "N/A";
  const target = (power.target_powers || []).find((item) => item.power === targetPower);
  if (!target || target.minimum_detectable_effect == null) return "N/A";
  return formatDecimal(target.minimum_detectable_effect, 4);
}

function renderPermutationCheck(check) {
  if (!check || check.status !== "available") return "";
  const sampleText = check.permutation_value_count < check.full_value_count
    ? `, mẫu đều ${numberFormatter.format(check.permutation_value_count)}/${numberFormatter.format(check.full_value_count)}`
    : "";
  return `
    <p class="audit-permutation-note">
      <strong>Permutation p ${escapeHtml(formatPValue(check.empirical_p_value))}</strong>
      <span>Hoán vị nguyên đơn vị: ${escapeHtml(permutationUnitLabel(check.preserve_unit))}${escapeHtml(sampleText)}; không đổi q/status.</span>
    </p>`;
}

function permutationUnitLabel(unit) {
  const labels = {
    whole_draw_sum: "tổng của từng kỳ",
    whole_digit_value: "giá trị chuỗi của từng kết quả",
    whole_digit_sum: "tổng chữ số của từng kết quả",
  };
  return labels[unit] || "từng đơn vị quan sát";
}

function renderBlockBootstrapCheck(check) {
  if (!check || check.status !== "available") return "";
  const lower = formatDecimal(check.confidence_interval_lower, 4);
  const upper = formatDecimal(check.confidence_interval_upper, 4);
  const sampleText = check.bootstrap_value_count < check.full_value_count
    ? `, mẫu đều ${numberFormatter.format(check.bootstrap_value_count)}/${numberFormatter.format(check.full_value_count)}`
    : "";
  return `
    <p class="audit-bootstrap-note">
      <strong>Block bootstrap 95% [${escapeHtml(lower)}, ${escapeHtml(upper)}]</strong>
      <span>Block liên tiếp ${numberFormatter.format(check.block_length)} đơn vị${escapeHtml(sampleText)}; không đổi q/status.</span>
    </p>`;
}

function renderChangePointScan(scan) {
  if (!scan || scan.status !== "available") return "";
  const strongest = scan.strongest_candidate || {};
  const fraction = strongest.candidate_fraction == null
    ? "N/A"
    : formatPercent(strongest.candidate_fraction, 0);
  const rawP = scan.raw_p_value == null ? "N/A" : formatPValue(scan.raw_p_value);
  const adjustedP = scan.adjusted_p_value == null ? "N/A" : formatPValue(scan.adjusted_p_value);
  return `
    <p class="audit-change-point-note">
      <strong>Change-point scan ${numberFormatter.format(scan.candidate_count || 0)} điểm</strong>
      <span>Mạnh nhất tại ${escapeHtml(fraction)} lịch sử; p thô ${escapeHtml(rawP)}, p Bonferroni ${escapeHtml(adjustedP)}.</span>
    </p>`;
}

function renderWeatherReport(weather) {
  const container = document.getElementById("weather-report");
  if (!container) return;
  if (!weather || weather.status !== "ready") {
    container.innerHTML = `
      <div class="weather-empty">
        Chưa có đủ dữ liệu thời tiết đã khóa để ghép với sản phẩm này.
      </div>`;
    return;
  }
  const coverage = weather.coverage;
  const venueText = (coverage.venues || [])
    .map((venue) => `${venue.name}: ${numberFormatter.format(venue.days)} ngày`)
    .join(" · ");
  const associations = (weather.associations || [])
    .map((item) => {
      const strength = correlationStrength(Math.abs(item.correlation));
      return `
        <article class="weather-association ${escapeHtml(item.status)}">
          <span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(strength)}</strong>
          <dl>
            <div><dt>Liên hệ</dt><dd>${formatSigned(item.correlation, 3)}</dd></div>
            <div><dt>q hiệu chỉnh</dt><dd>${formatPValue(item.q_value_bh)}</dd></div>
            <div><dt>Số ngày</dt><dd>${numberFormatter.format(item.sample_days)}</dd></div>
          </dl>
          <p>
            Liên hệ chạy từ -1 đến 1. Gần 0 nghĩa là gần như không đi cùng nhau;
            dấu âm hoặc dương chỉ hướng thay đổi, không chứng minh nguyên nhân.
          </p>
        </article>`;
    })
    .join("");
  const bands = (weather.temperature_bands || [])
    .map(
      (band) => `
        <article>
          <span>${escapeHtml(band.label)}</span>
          <strong>${formatDecimal(band.temperature_mean, 1)}°C</strong>
          <small>
            ${numberFormatter.format(band.days)} ngày ·
            ${escapeHtml(weather.outcome_feature.label)} ${formatDecimal(band.outcome_mean, 2)}
          </small>
        </article>`,
    )
    .join("");
  container.innerHTML = `
    <div class="weather-conclusion">
      <div>
        <span>Kết luận hiện tại</span>
        <strong>${escapeHtml(weather.conclusion)}</strong>
      </div>
      <div class="weather-coverage">
        <span>Độ phủ</span>
        <strong>${formatPercent(coverage.coverage_rate)}</strong>
        <small>
          ${numberFormatter.format(coverage.matched_draws)} kỳ,
          ${numberFormatter.format(coverage.matched_days)} ngày,
          đến ${formatDate(coverage.latest_date)}
        </small>
      </div>
    </div>
    <p class="weather-venue-note">${escapeHtml(venueText)}</p>
    <div class="weather-association-grid">${associations}</div>
    <div class="weather-band-heading">
      <span>Ba nhóm nhiệt độ để đọc mô tả</span>
      <small>Mô tả thô, chưa khử mùa vụ. Không dùng riêng ba ô này để kết luận.</small>
    </div>
    <div class="weather-band-grid">${bands}</div>
    <details class="weather-method">
      <summary>Phạm vi đúng của phép kiểm này</summary>
      <p>${escapeHtml(weather.method)}</p>
      <ul>${weather.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      <p>
        Nguồn khí tượng <a href="${escapeHtml(weather.source.documentation)}">Open-Meteo ERA5-Land</a>.
        Mốc chuyển địa điểm theo
        <a href="${escapeHtml(weather.source.venue_source)}">thông báo chính thức của Vietlott</a>.
      </p>
    </details>`;
}

function correlationStrength(value) {
  if (value < 0.05) return "Gần như không có";
  if (value < 0.1) return "Rất yếu";
  if (value < 0.3) return "Yếu";
  if (value < 0.5) return "Vừa";
  return "Mạnh";
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
    ? "Vẫn nổi bật khi xét toàn bộ số"
    : "Chưa nổi bật khi xét toàn bộ số";
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
  const baselineValue =
    kind === "number_set"
      ? backtest.baseline.average_hits
      : backtest.baseline.average_best_position_matches;
  const targetScope = backtest.target_scope || {};
  const unit = kind === "number_set" ? "số trùng mỗi kỳ" : "vị trí trùng tốt nhất";
  const modelRows = [
    {
      label: "Kết hợp ba dấu hiệu",
      model: backtest.model,
      comparison: backtest.comparison,
    },
    backtest.recent_model && backtest.recent_comparison
      ? {
          label: "Tần suất cửa sổ gần",
          model: backtest.recent_model,
          comparison: backtest.recent_comparison,
        }
      : null,
    backtest.audit_model && backtest.audit_comparison
      ? {
          label: "Khai thác kiểm định công bằng",
          model: backtest.audit_model,
          comparison: backtest.audit_comparison,
        }
      : null,
  ].filter(Boolean);
  const hasAdjustedWinner = modelRows.some((row) => row.comparison?.beats_baseline);
  const hasRawSignal = modelRows.some(
    (row) => row.comparison?.beats_baseline_unadjusted,
  );
  const conclusion = hasAdjustedWinner
    ? "Có ít nhất một chiến lược vượt mốc ngẫu nhiên sau hiệu chỉnh nhiều phép thử, nhưng vẫn phải xác nhận bằng dự đoán đã lưu trước."
    : hasRawSignal
      ? "Có tín hiệu với p thô dưới 0,05, nhưng tín hiệu không còn đủ mạnh sau khi hiệu chỉnh toàn hệ thống."
      : "Kết luận: các chiến lược hiện tại chưa tốt hơn cách chọn đồng đều một cách đáng tin cậy.";
  const scoreDescription = renderBacktestScoreFormulas(backtest.score_formulas, kind);
  container.innerHTML = `
    <div class="backtest-score">
      ${modelRows.map((row) => {
        const value = kind === "number_set"
          ? row.model.average_hits
          : row.model.average_best_position_matches;
        return `
          <div class="backtest-side model">
            <span>${escapeHtml(row.label)}</span>
            <strong>${formatDecimal(value, 3)}</strong>
            <small>${escapeHtml(unit)}</small>
          </div>`;
      }).join("")}
      <div class="backtest-side">
        <span>Mốc chọn ngẫu nhiên</span>
        <strong>${formatDecimal(baselineValue, 3)}</strong>
        <small>${escapeHtml(unit)}</small>
      </div>
    </div>
    <p class="backtest-verdict">${escapeHtml(conclusion)}</p>
    ${modelRows.map((row) => {
      const comparisonValue = kind === "number_set"
        ? row.comparison.mean_hit_difference
        : row.comparison.mean_position_match_difference;
      return `
        <p class="backtest-evidence">
          <span>${escapeHtml(row.label)}</span>
          Chênh lệch ${formatSigned(comparisonValue)}, p thô
          ${formatPValue(row.comparison.approximate_p_value)}, q sau hiệu chỉnh
          ${formatPValue(row.comparison.q_value_global_bh)}. Khoảng ước lượng 95%
          từ ${formatSigned(row.comparison.confidence_interval_lower)} đến
          ${formatSigned(row.comparison.confidence_interval_upper)} trên
          ${numberFormatter.format(backtest.samples)} kỳ kiểm tra.
        </p>`;
    }).join("")}
    ${renderBacktestPartialBaseline(backtest.baseline?.partial_match_baseline)}
    <details class="backtest-method-details">
      <summary>
        <span>Phương pháp và công thức của báo cáo này</span>
        <small>Walk-forward, baseline, cách chấm và ngưỡng kết luận</small>
      </summary>
      <div class="backtest-method-body">
        <ol>
          <li><strong>Chia dữ liệu theo thời gian</strong><span>Tại kỳ t, thuật toán chỉ nhìn các kỳ trước t. Sau khi chấm xong kỳ t, kết quả kỳ đó mới được thêm vào lịch sử để dự đoán kỳ kế tiếp.</span></li>
          <li><strong>Phạm vi kiểm tra</strong><span>${numberFormatter.format(backtest.samples)} kỳ, từ mã kỳ ${escapeHtml(backtest.first_test_draw_id)} đến ${escapeHtml(backtest.latest_test_draw_id)}. Trước kỳ kiểm tra đầu có ${numberFormatter.format(backtest.initial_training_draws)} kỳ lịch sử. Cửa sổ ngắn ${numberFormatter.format(backtest.short_window_draws)} kỳ, cửa sổ gần ${numberFormatter.format(backtest.recent_window_draws)} kỳ${backtest.pair_window_draws ? `, cửa sổ cặp ${numberFormatter.format(backtest.pair_window_draws)} kỳ` : ""}.</span></li>
          <li><strong>Tập kỳ mục tiêu chung</strong><span>Baseline, ba chiến lược và ba phép so sánh cùng dùng ${numberFormatter.format(targetScope.target_draw_count || backtest.samples)} kỳ mục tiêu. Scope ${escapeHtml(targetScope.scope_id || "chưa công bố")} khóa bằng hash danh sách mã kỳ.</span></li>
          ${scoreDescription}
          <li><strong>Baseline đồng đều chính xác</strong><span>Với tập số, kỳ vọng và phân bố số trùng được tính bằng phân bố siêu bội. Với chuỗi chữ số, chương trình đếm chính xác toàn bộ không gian chuỗi hợp lệ của từng kỳ. Kết quả không phụ thuộc seed.</span></li>
          <li><strong>So sánh theo từng kỳ</strong><span>Với mỗi kỳ tính d = điểm chiến lược - điểm kỳ vọng đồng đều. Báo cáo lấy trung bình d và tính z = trung bình(d) / (độ lệch chuẩn(d) / √n), rồi lấy p hai phía từ phân bố chuẩn.</span></li>
          <li><strong>Hiệu chỉnh toàn hệ thống</strong><span>Tất cả p-value của ba chiến lược trên mọi sản phẩm được hiệu chỉnh Benjamini-Hochberg. Chỉ ghi "vượt baseline" khi trung bình d &gt; 0 và q toàn hệ thống &lt; 0,05.</span></li>
        </ol>
        <p>
          Mã triển khai nằm trong
          <a href="https://github.com/NhanAZ/vietlott-data-research/blob/main/src/vietlott_analytics/predictions.py">src/vietlott_analytics/predictions.py</a>.
          Báo cáo backtest đủ ba chiến lược đang được ghi vào sổ dự đoán là “Kết hợp ba dấu hiệu”,
          “Tần suất cửa sổ gần” và “Tín hiệu kiểm định”.
        </p>
      </div>
    </details>`;
}

function renderBacktestPartialBaseline(baseline) {
  if (!baseline) return "";
  const expectedPartial = formatExpectedCount(baseline.expected_partial_match_count);
  const expectedNear = formatExpectedCount(baseline.expected_near_count);
  const expectedZero = formatExpectedCount(baseline.expected_zero_match_count);
  return `
    <p class="backtest-evidence">
      <span>Baseline trùng một phần</span>
      Chọn đều kỳ vọng ${expectedPartial} lượt có trùng một phần,
      ${expectedNear} lượt gần đúng và ${expectedZero} lượt không trùng gì.
      Xác suất mỗi kỳ: trùng một phần ${formatProbability(baseline.partial_match_probability)},
      gần đúng ${formatProbability(baseline.near_probability)},
      không trùng ${formatProbability(baseline.zero_match_probability)}.
    </p>`;
}

function renderBacktestScoreFormulas(formulas, kind) {
  if (!formulas) {
    const score = kind === "number_set"
      ? "Số lượng số chính dự đoán trùng với kết quả thật."
      : "Số vị trí khớp nhiều nhất giữa chuỗi dự đoán và các kết quả công bố trong kỳ.";
    return `<li><strong>Điểm mỗi kỳ</strong><span>${escapeHtml(score)}</span></li>`;
  }
  const typeLabel = formulas.product_kind === "number_set"
    ? "Tập số dùng thước đo số chính trùng mỗi kỳ"
    : "Chuỗi chữ số dùng thước đo vị trí trùng tốt nhất mỗi kỳ";
  const strategyRows = (formulas.strategies || []).map((row) => `
    <li>
      <strong>${escapeHtml(row.label || row.strategy)}</strong>
      <span>${escapeHtml(row.formula || "")}. ${escapeHtml(row.selection_rule || "")}</span>
    </li>`).join("");
  return `
    <li><strong>Thước đo riêng</strong><span>${escapeHtml(typeLabel)}; không gộp chung với loại sản phẩm khác.</span></li>
    <li><strong>Điểm mỗi kỳ</strong><span>${escapeHtml(formulas.per_draw_score || "")}</span></li>
    <li><strong>Chênh lệch ghép cặp</strong><span>${escapeHtml(formulas.comparison_difference || "")}</span></li>
    ${strategyRows}`;
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
  const outcome = predictions.outcome_summary || {};
  const integrity = predictions.ledger_integrity || {};
  const expectedNear = Number(outcome.expected_near_by_chance || 0);
  const nearExcess = Number(outcome.near_excess_vs_chance || 0);
  text("pending-predictions", numberFormatter.format(predictions.pending_count));
  text("exact-predictions", numberFormatter.format(outcome.exact || 0));
  text("near-predictions", numberFormatter.format(outcome.near || 0));
  text("wrong-predictions", numberFormatter.format(outcome.wrong || 0));
  text("archive-evaluated-draws", numberFormatter.format(outcome.evaluated_draws || 0));
  text(
    "archive-evaluated-predictions",
    numberFormatter.format(outcome.evaluated_predictions || predictions.evaluation_count || 0),
  );
  text("archive-partial-matches", numberFormatter.format(outcome.partial_matches || 0));
  text(
    "prediction-near-rule",
    `${outcome.near_rule || ""} ${numberFormatter.format(predictions.evaluation_count)} lượt dự đoán hiện thuộc ${numberFormatter.format(outcome.evaluated_draws || 0)} kỳ quay thực tế. Nếu chọn ngẫu nhiên theo cùng luật chấm, kỳ vọng gần đúng khoảng ${formatExpectedCount(expectedNear)} lượt; thực tế ${formatExpectedCount(outcome.near || 0)} lượt, chênh ${formatSignedExpected(nearExcess)}.`,
  );
  text("prediction-current-conclusion", predictionOutcomeConclusion());
  text(
    "prediction-ledger-integrity",
    integrity.status === "valid" && integrity.root_hash
      ? `Chuỗi hash hợp lệ gồm ${numberFormatter.format(integrity.event_count)} sự kiện. Hash gốc ${integrity.root_hash}.`
      : "Sổ dự đoán chưa có chuỗi hash hợp lệ để công bố.",
  );
  setupPredictionArchive();
  const select = document.getElementById("prediction-product");
  const available = products.filter((product) => predictions.latest[product.slug]);
  select.innerHTML = available
    .map(
      (product) =>
        `<option value="${escapeHtml(product.slug)}">${escapeHtml(product.name)}</option>`,
    )
    .join("");
  const requested = new URLSearchParams(window.location.search).get("product");
  select.value = available.some((item) => item.slug === requested)
    ? requested
    : available.some((item) => item.slug === "keno")
      ? "keno"
      : available[0]?.slug;
  select.addEventListener("change", () => renderPredictionCards(select.value));
  renderPredictionCards(select.value);
}

function setupPredictionArchive() {
  document.querySelectorAll("[data-archive-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      renderPredictionArchiveDetail(button.dataset.archiveFilter || "evaluated-predictions");
    });
  });
  document.getElementById("prediction-archive-detail-close")?.addEventListener("click", () => {
    const panel = document.getElementById("prediction-archive-detail");
    if (panel) panel.hidden = true;
  });
}

function renderPredictionArchiveDetail(filter) {
  const panel = document.getElementById("prediction-archive-detail");
  const title = document.getElementById("prediction-archive-detail-title");
  const kicker = document.getElementById("prediction-archive-detail-kicker");
  const list = document.getElementById("prediction-archive-detail-list");
  if (!panel || !title || !kicker || !list) return;

  const payload = predictionArchivePayload(filter);
  kicker.textContent = payload.kicker;
  title.textContent = payload.title;
  list.innerHTML = payload.rows.length
    ? payload.rows
      .map((row) =>
        row.outcome
          ? renderPredictionEvaluation(row, { showProduct: true })
          : renderPendingPrediction(row),
      )
      .join("")
    : `<div class="prediction-empty">${escapeHtml(payload.empty)}</div>`;
  panel.hidden = false;
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function predictionArchivePayload(filter) {
  const predictions = state.predictions || {};
  const summary = predictions.outcome_summary || {};
  const evaluations = predictions.archived_evaluations || predictions.recent_evaluations || [];
  const pending = predictionPendingRows(predictions);
  const base = {
    "evaluated-draws": {
      rows: evaluations,
      title: `${numberFormatter.format(summary.evaluated_draws || 0)} kỳ đã đối chiếu · ${numberFormatter.format(evaluations.length)} lượt dự đoán`,
      kicker: "Kỳ đã đối chiếu",
      empty: "Chưa có kỳ nào đủ điều kiện đối chiếu.",
    },
    "evaluated-predictions": {
      rows: evaluations,
      title: `${numberFormatter.format(evaluations.length)} lượt dự đoán đã đối chiếu`,
      kicker: "Lượt dự đoán",
      empty: "Chưa có lượt dự đoán nào đã đối chiếu.",
    },
    exact: {
      rows: evaluations.filter((row) => row.outcome?.status === "exact"),
      title: `${numberFormatter.format(summary.exact || 0)} lượt đúng toàn bộ`,
      kicker: "Đúng toàn bộ",
      empty: "Chưa có lượt nào đúng toàn bộ.",
    },
    near: {
      rows: evaluations.filter((row) => row.outcome?.status === "near"),
      title: `${numberFormatter.format(summary.near || 0)} lượt gần đúng`,
      kicker: "Gần đúng",
      empty: "Chưa có lượt gần đúng.",
    },
    wrong: {
      rows: evaluations.filter((row) => row.outcome?.status === "wrong"),
      title: `${numberFormatter.format(summary.wrong || 0)} lượt sai`,
      kicker: "Sai",
      empty: "Chưa có lượt sai.",
    },
    partial: {
      rows: evaluations.filter((row) => row.outcome?.has_partial_match),
      title: `${numberFormatter.format(summary.partial_matches || 0)} lượt có trùng một phần`,
      kicker: "Có trùng một phần",
      empty: "Chưa có lượt nào trùng một phần.",
    },
    pending: {
      rows: pending,
      title: `${numberFormatter.format(predictions.pending_count || pending.length)} lượt đang chờ kết quả`,
      kicker: "Đang chờ kết quả",
      empty: "Không còn lượt dự đoán nào đang chờ kết quả.",
    },
  };
  return base[filter] || base["evaluated-predictions"];
}

function predictionPendingRows(predictions) {
  if (Array.isArray(predictions.pending_predictions)) {
    return predictions.pending_predictions;
  }
  return Object.values(predictions.latest || {}).flat();
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
        <article class="prediction-card${prediction.strategy === "audit_signal" ? " primary" : ""}">
          <span class="strategy-name">${escapeHtml(copy.title)}</span>
          <p class="strategy-description">${escapeHtml(copy.description)}</p>
          ${output}
          <div class="prediction-meta">
            <span>Mã lưu vết ${escapeHtml(prediction.prediction_id)}</span>
            <span>Dữ liệu đến kỳ #${escapeHtml(prediction.dataset_cutoff_draw_id)}</span>
          </div>
        </article>`;
    })
    .join("");
  if (!predictions.length) {
    document.getElementById("prediction-cards").innerHTML =
      '<div class="error-card">Chưa có dự đoán cho sản phẩm này.</div>';
  }
  renderPredictionResults(slug);
  if (product) document.getElementById("prediction-product").value = product.slug;
}

function renderPredictionResults(slug) {
  const evaluations = (state.predictions.recent_evaluations || []).filter(
    (evaluation) => evaluation.product === slug,
  );
  const productOutcome = state.predictions.product_outcomes?.[slug] || {};
  const summary = document.getElementById("prediction-product-summary");
  const latest = document.getElementById("prediction-latest-comparison");
  const exact = Number(productOutcome.exact || 0);
  const near = Number(productOutcome.near || 0);
  const wrong = Number(productOutcome.wrong || 0);
  const partial = Number(productOutcome.partial_matches || 0);
  const expectedNear = Number(productOutcome.expected_near_by_chance || 0);
  const nearExcess = Number(productOutcome.near_excess_vs_chance || 0);
  const evaluatedDraws = Number(productOutcome.evaluated_draws || 0);
  const evaluatedPredictions = Number(
    productOutcome.evaluated_predictions || evaluations.length,
  );
  const distribution = productOutcome.score_distribution || [];
  const scoreKind = productOutcome.score_kind || evaluations[0]?.outcome.score_kind;
  const distributionLabel = scoreKind === "positions"
    ? "Số vị trí trùng"
    : "Số chính trùng";

  summary.innerHTML = `
    <div class="prediction-product-metrics">
      <button class="prediction-product-metric" type="button" data-product-filter="evaluated-draws" aria-controls="prediction-history-list"><span>Kỳ đã đối chiếu</span><strong>${numberFormatter.format(evaluatedDraws)}</strong></button>
      <button class="prediction-product-metric" type="button" data-product-filter="evaluated-predictions" aria-controls="prediction-history-list"><span>Lượt dự đoán</span><strong>${numberFormatter.format(evaluatedPredictions)}</strong></button>
      <button class="prediction-product-metric" type="button" data-product-filter="exact" aria-controls="prediction-history-list"><span>Đúng toàn bộ</span><strong>${numberFormatter.format(exact)}</strong></button>
      <button class="prediction-product-metric" type="button" data-product-filter="near" aria-controls="prediction-history-list"><span>Gần đúng</span><strong>${numberFormatter.format(near)}</strong></button>
      <div class="prediction-product-metric static"><span>Kỳ vọng gần đúng</span><strong>${formatExpectedCount(expectedNear)}</strong></div>
      <div class="prediction-product-metric static"><span>Chênh so với nền</span><strong>${formatSignedExpected(nearExcess)}</strong></div>
      <button class="prediction-product-metric" type="button" data-product-filter="wrong" aria-controls="prediction-history-list"><span>Sai</span><strong>${numberFormatter.format(wrong)}</strong></button>
      <button class="prediction-product-metric" type="button" data-product-filter="partial" aria-controls="prediction-history-list"><span>Có trùng một phần</span><strong>${numberFormatter.format(partial)}</strong></button>
    </div>
    <div class="prediction-hit-distribution">
      <span>${distributionLabel}</span>
      <div>
        ${distribution
          .map(
            (entry) =>
              `<span><strong>${entry.score}</strong> ${numberFormatter.format(entry.count)} lượt</span>`,
          )
          .join("") || "<span>Chưa có lượt đã chấm</span>"}
      </div>
    </div>`;
  setupPredictionProductFilters(evaluations, productOutcome, evaluatedPredictions);

  if (!evaluations.length) {
    latest.innerHTML = `
      <div class="prediction-empty">
        Chưa có kỳ mới để đối chiếu cho sản phẩm này. Dự đoán gốc vẫn được giữ
        nguyên trong sổ và sẽ tự chấm khi kết quả xác nhận xuất hiện.
      </div>`;
    renderPredictionProductHistory("evaluated-predictions", evaluations, productOutcome, evaluatedPredictions, {
      open: false,
    });
    return;
  }

  const latestEvaluation = evaluations[0];
  const latestDrawEvaluations = evaluations.filter(
    (evaluation) =>
      evaluation.actual_draw_id === latestEvaluation.actual_draw_id
      && evaluation.actual_draw_date === latestEvaluation.actual_draw_date,
  );
  latest.innerHTML = `
    <details class="prediction-latest-panel">
      <summary class="prediction-comparison-heading">
        <span>Kỳ mới nhất đã chấm</span>
        <strong>#${escapeHtml(latestEvaluation.actual_draw_id)} · ${formatDate(latestEvaluation.actual_draw_date)}</strong>
      </summary>
      <div class="prediction-latest-list">
        ${latestDrawEvaluations.map(renderPredictionEvaluation).join("")}
      </div>
    </details>`;
  renderPredictionProductHistory("evaluated-predictions", evaluations, productOutcome, evaluatedPredictions, {
    open: false,
  });
}

function setupPredictionProductFilters(evaluations, productOutcome, evaluatedPredictions) {
  document.querySelectorAll("[data-product-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      renderPredictionProductHistory(
        button.dataset.productFilter || "evaluated-predictions",
        evaluations,
        productOutcome,
        evaluatedPredictions,
      );
    });
  });
}

function renderPredictionProductHistory(
  filter,
  evaluations,
  productOutcome,
  evaluatedPredictions,
  options = {},
) {
  const panel = document.querySelector(".prediction-history-panel");
  const label = document.getElementById("prediction-history-label");
  const count = document.getElementById("prediction-history-count");
  const list = document.getElementById("prediction-history-list");
  if (!label || !count || !list) return;

  const payload = predictionProductPayload(
    filter,
    evaluations,
    productOutcome,
    evaluatedPredictions,
  );
  label.textContent = options.open === false
    ? "Mở toàn bộ lịch sử đối chiếu của sản phẩm"
    : `Chi tiết ${payload.kicker.toLowerCase()} của sản phẩm`;
  count.textContent = payload.countLabel;
  list.innerHTML = payload.rows.length
    ? payload.rows.map(renderPredictionEvaluation).join("")
    : `<div class="prediction-empty">${escapeHtml(payload.empty)}</div>`;

  if (panel && options.open !== false) {
    panel.open = true;
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function predictionProductPayload(filter, evaluations, productOutcome, evaluatedPredictions) {
  const exact = Number(productOutcome.exact || 0);
  const near = Number(productOutcome.near || 0);
  const wrong = Number(productOutcome.wrong || 0);
  const partial = Number(productOutcome.partial_matches || 0);
  const evaluatedDraws = Number(productOutcome.evaluated_draws || 0);
  const total = Number(evaluatedPredictions || evaluations.length);
  const countLabel = (rows, totalCount) =>
    rows.length < totalCount
      ? `${numberFormatter.format(rows.length)} lượt gần nhất / ${numberFormatter.format(totalCount)} lượt`
      : `${numberFormatter.format(totalCount)} lượt`;
  const base = {
    "evaluated-draws": {
      rows: evaluations,
      kicker: "Kỳ đã đối chiếu",
      countLabel: `${numberFormatter.format(evaluatedDraws)} kỳ / ${numberFormatter.format(total)} lượt`,
      empty: "Chưa có kỳ nào đủ điều kiện đối chiếu cho sản phẩm này.",
    },
    "evaluated-predictions": {
      rows: evaluations,
      kicker: "Lượt dự đoán",
      countLabel: countLabel(evaluations, total),
      empty: "Chưa có lượt dự đoán nào đã đối chiếu cho sản phẩm này.",
    },
    exact: {
      rows: evaluations.filter((row) => row.outcome?.status === "exact"),
      kicker: "Đúng toàn bộ",
      countLabel: countLabel(
        evaluations.filter((row) => row.outcome?.status === "exact"),
        exact,
      ),
      empty: "Chưa có lượt nào đúng toàn bộ cho sản phẩm này.",
    },
    near: {
      rows: evaluations.filter((row) => row.outcome?.status === "near"),
      kicker: "Gần đúng",
      countLabel: countLabel(
        evaluations.filter((row) => row.outcome?.status === "near"),
        near,
      ),
      empty: "Chưa có lượt gần đúng cho sản phẩm này.",
    },
    wrong: {
      rows: evaluations.filter((row) => row.outcome?.status === "wrong"),
      kicker: "Sai",
      countLabel: countLabel(
        evaluations.filter((row) => row.outcome?.status === "wrong"),
        wrong,
      ),
      empty: "Chưa có lượt sai cho sản phẩm này.",
    },
    partial: {
      rows: evaluations.filter((row) => row.outcome?.has_partial_match),
      kicker: "Có trùng một phần",
      countLabel: countLabel(
        evaluations.filter((row) => row.outcome?.has_partial_match),
        partial,
      ),
      empty: "Chưa có lượt nào trùng một phần cho sản phẩm này.",
    },
  };
  return base[filter] || base["evaluated-predictions"];
}

function renderPredictionEvaluation(evaluation, options = {}) {
  const copy = predictionStrategyCopy(evaluation.strategy);
  const status = evaluation.outcome.status;
  const productPrefix = options.showProduct
    ? `${escapeHtml(predictionProductName(evaluation.product))} · `
    : "";
  const predicted = renderEvaluationValue(
    evaluation.prediction,
    evaluation.outcome,
    "prediction",
  );
  const actual = renderEvaluationValue(
    evaluation.actual_result,
    evaluation.outcome,
    "actual",
  );
  return `
    <article class="prediction-evaluation status-${escapeHtml(status)}">
      <header>
        <div>
          <span class="strategy-name">${escapeHtml(copy.title)}</span>
          <small>${productPrefix}Ghi lúc ${escapeHtml(formatDateTime(evaluation.prediction_generated_at))}</small>
        </div>
        <span class="prediction-status status-${escapeHtml(status)}">
          ${escapeHtml(evaluation.outcome.status_label)}
        </span>
      </header>
      <div class="prediction-versus">
        <div>
          <span>Dự đoán gốc</span>
          ${predicted}
        </div>
        <b>so với</b>
        <div>
          <span>Kết quả kỳ #${escapeHtml(evaluation.actual_draw_id)}</span>
          ${actual}
        </div>
      </div>
      <footer>
        <strong>${escapeHtml(evaluation.outcome.score_label)}</strong>
        <span>${escapeHtml(evaluationBaselineLabel(evaluation))}</span>
        <span>Dữ liệu đã khóa ở kỳ #${escapeHtml(evaluation.dataset_cutoff_draw_id)}</span>
        <span>Mã lưu vết ${escapeHtml(evaluation.prediction_id)}</span>
      </footer>
    </article>`;
}

function renderPendingPrediction(prediction) {
  const copy = predictionStrategyCopy(prediction.strategy);
  const predicted = renderPredictionOnlyValue(prediction.prediction || {});
  return `
    <article class="prediction-evaluation status-pending">
      <header>
        <div>
          <span class="strategy-name">${escapeHtml(copy.title)}</span>
          <small>${escapeHtml(predictionProductName(prediction.product))} · Ghi lúc ${escapeHtml(formatDateTime(prediction.prediction_generated_at))}</small>
        </div>
        <span class="prediction-status status-pending">Đang chờ kết quả</span>
      </header>
      <div class="prediction-versus">
        <div>
          <span>Dự đoán gốc</span>
          ${predicted}
        </div>
        <b>chờ</b>
        <div>
          <span>Kết quả sau kỳ #${escapeHtml(prediction.dataset_cutoff_draw_id)}</span>
          <div class="prediction-pending-result">Chưa có kết quả xác nhận</div>
        </div>
      </div>
      <footer>
        <strong>Dữ liệu khóa ngày ${formatDate(prediction.dataset_cutoff_date)}</strong>
        <span>Mã lưu vết ${escapeHtml(prediction.prediction_id)}</span>
      </footer>
    </article>`;
}

function renderPredictionOnlyValue(result) {
  if (Array.isArray(result.numbers)) {
    const numbers = result.numbers
      .map((value) => `<span class="ball">${String(value).padStart(2, "0")}</span>`)
      .join("");
    const special = (result.special_numbers || [])
      .map((value) => `<span class="ball special">${String(value).padStart(2, "0")}</span>`)
      .join("");
    return `<div class="evaluation-balls">${numbers}${special}</div>`;
  }
  return `
    <div class="evaluation-sequence">
      ${[...String(result.sequence || "")]
        .map((digit) => `<span>${escapeHtml(digit)}</span>`)
        .join("")}
    </div>`;
}

function renderEvaluationValue(result, outcome, side) {
  if (Array.isArray(result.numbers)) {
    const matched = new Set(outcome.matched_numbers || []);
    const numbers = result.numbers
      .map((value) => {
        const isMatched = matched.has(Number(value));
        return `<span class="ball${isMatched ? " matched" : ""}">${String(value).padStart(2, "0")}</span>`;
      })
      .join("");
    const special = (result.special_numbers || [])
      .map((value) => {
        const isMatched = (outcome.matched_special_numbers || []).includes(Number(value));
        return `<span class="ball special${isMatched ? " matched" : ""}">${String(value).padStart(2, "0")}</span>`;
      })
      .join("");
    return `<div class="evaluation-balls">${numbers}${special}</div>`;
  }

  const sequence = side === "prediction"
    ? String(result.sequence || "")
    : String(outcome.best_matching_outcome || result.outcomes?.[0] || "");
  const positions = new Set(outcome.matched_positions || []);
  return `
    <div class="evaluation-sequence">
      ${[...sequence]
        .map(
          (digit, index) =>
            `<span class="${positions.has(index) ? "matched" : ""}">${escapeHtml(digit)}</span>`,
        )
        .join("")}
    </div>`;
}

function predictionProductName(slug) {
  return state.manifest?.products?.find((product) => product.slug === slug)?.name || slug;
}

function predictionOutcomeConclusion() {
  const summary = state.predictions?.outcome_summary;
  if (!summary || !state.predictions.evaluation_count) {
    return "Sổ dự đoán chưa có kỳ nào đến hạn đối chiếu.";
  }
  if (summary.exact) {
    return `Sổ dự đoán ngoài mẫu hiện có ${summary.exact} lượt đúng toàn bộ, ${summary.near} lượt gần đúng và ${summary.wrong} lượt sai.`;
  }
  return `Sau ${state.predictions.evaluation_count} lượt đã đối chiếu, chưa có dự đoán nào đúng toàn bộ hoặc gần đúng theo tiêu chí nghiêm; ${summary.partial_matches} lượt có trùng một phần.`;
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
    audit_signal: {
      title: "Khai thác kiểm định công bằng",
      description: "Ưu tiên lệch tần suất, vị trí hoặc cặp số đang bị bộ kiểm định đưa vào diện theo dõi.",
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

function formatSignedExpected(value) {
  const number = Number(value || 0);
  if (number !== 0 && Math.abs(number) < 0.001) {
    return `${number >= 0 ? "+" : ""}${number.toExponential(2).replace(".", ",")}`;
  }
  return formatSigned(number, Math.abs(number) < 10 ? 2 : 1);
}

function formatExpectedCount(value) {
  const number = Number(value || 0);
  if (number !== 0 && Math.abs(number) < 0.001) {
    return number.toExponential(2).replace(".", ",");
  }
  return formatDecimal(number, number < 10 ? 2 : 1);
}

function formatPercent(value, digits = 1) {
  return Number(value).toLocaleString("vi-VN", {
    style: "percent",
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function formatProbability(value) {
  const number = Number(value || 0);
  if (number !== 0 && Math.abs(number) < 0.000001) {
    return number.toExponential(2).replace(".", ",");
  }
  return formatPercent(number, number < 0.01 ? 4 : 1);
}

function evaluationBaselineLabel(evaluation) {
  const baseline = evaluation.outcome?.baseline_probability;
  if (!baseline) return "Chưa có xác suất nền";
  const suffix = baseline.actual_outcomes > 1
    ? `, ${numberFormatter.format(baseline.actual_outcomes)} dòng giải`
    : "";
  return `Nền ngẫu nhiên: gần đúng ${formatProbability(baseline.near)}, đúng ${formatProbability(baseline.exact)}${suffix}`;
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

function formatDateTime(value) {
  if (!value) return "chưa rõ";
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return String(value);
  return instant.toLocaleString("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

function text(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = normalizeText(value);
}

function escapeHtml(value) {
  return normalizeText(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeText(value) {
  return String(value).normalize("NFC");
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
