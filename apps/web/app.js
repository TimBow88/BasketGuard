const FIXTURE_URL = "/tests/fixtures/seed_price_observations.json";
const STORAGE_KEY = "basketguard.manualObservations";

const state = {
  fixture: null,
  findings: [],
  manualObservations: [],
  selectedGroup: null,
  retailerFilter: "all",
};

const schemaCards = [
  {
    title: "Collection targets",
    table: "collection_targets",
    fields: "retailer, group, URL, postcode, cadence, priority",
  },
  {
    title: "Raw evidence",
    table: "raw_product_snapshots",
    fields: "raw title, price text, promo text, parser version",
  },
  {
    title: "Clean catalogue",
    table: "products",
    fields: "canonical name, brand, category, pack size, tier",
  },
  {
    title: "Price history",
    table: "price_observations",
    fields: "shelf, loyalty, was, effective, unit price",
  },
  {
    title: "Equivalence",
    table: "equivalence_groups",
    fields: "group, unit basis, comparison level, confidence",
  },
  {
    title: "Ingestion health",
    table: "ingestion_jobs",
    fields: "status, parser errors, missing prices, block signals",
  },
];

document.addEventListener("DOMContentLoaded", initialise);

async function initialise() {
  bindNavigation();
  bindControls();
  state.manualObservations = loadManualObservations();
  await loadData();
}

async function loadData() {
  const response = await fetch(FIXTURE_URL);
  if (!response.ok) {
    throw new Error(`Unable to load fixture data: ${response.status}`);
  }

  state.fixture = await response.json();
  state.findings = buildFindings(state.fixture);
  state.selectedGroup = state.fixture.groups[0]?.slug ?? null;

  populateSelectors();
  render();
}

function bindNavigation() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("is-active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("is-active"));
      tab.classList.add("is-active");
      document.getElementById(tab.dataset.view).classList.add("is-active");
    });
  });
}

function bindControls() {
  document.getElementById("refreshButton").addEventListener("click", loadData);
  document.getElementById("exportButton").addEventListener("click", downloadManualObservations);
  document.getElementById("retailerFilter").addEventListener("change", (event) => {
    state.retailerFilter = event.target.value;
    renderOffenders();
  });
  document.getElementById("groupSelect").addEventListener("change", (event) => {
    state.selectedGroup = event.target.value;
    renderComparison();
  });
  document.getElementById("captureForm").addEventListener("submit", handleCaptureSubmit);
  document.getElementById("clearFormButton").addEventListener("click", () => {
    document.getElementById("captureForm").reset();
  });
  document.getElementById("clearCapturesButton").addEventListener("click", () => {
    state.manualObservations = [];
    saveManualObservations();
    renderManualObservations();
  });
}

function populateSelectors() {
  const retailers = [...new Set(state.findings.map((finding) => finding.retailer))];
  const groups = state.fixture.groups;

  fillSelect(
    document.getElementById("retailerFilter"),
    [{ value: "all", label: "All retailers" }, ...retailers.map((retailer) => ({ value: retailer, label: retailer }))],
  );

  fillSelect(
    document.getElementById("groupSelect"),
    groups.map((group) => ({ value: group.slug, label: group.display_name })),
  );

  const form = document.getElementById("captureForm");
  fillSelect(
    form.elements.retailer,
    retailers.map((retailer) => ({ value: retailer, label: retailer })),
  );
  fillSelect(
    form.elements.groupSlug,
    groups.map((group) => ({ value: group.slug, label: group.display_name })),
  );
}

function fillSelect(select, options) {
  select.replaceChildren(
    ...options.map((option) => {
      const element = document.createElement("option");
      element.value = option.value;
      element.textContent = option.label;
      return element;
    }),
  );
}

function render() {
  renderSummary();
  renderOffenders();
  renderRetailerTotals();
  renderComparison();
  renderManualObservations();
  renderSchema();
}

function renderSummary() {
  const totals = retailerBasketTotals();
  const worst = totals[0];
  const cheapestBasket = Math.min(...totals.map((total) => total.total));
  const overspend = worst.total - cheapestBasket;

  document.getElementById("worstRetailer").textContent = worst.retailer;
  document.getElementById("worstRetailerDetail").textContent = `${formatMoney(worst.total)} tracked basket`;
  document.getElementById("avoidableOverspend").textContent = formatMoney(overspend);
  document.getElementById("trackedGroups").textContent = state.fixture.groups.length;
  document.getElementById("observationCoverage").textContent = `${state.findings.length} retailer observations`;
  document.getElementById("manualCaptureCount").textContent = state.manualObservations.length;
}

function renderOffenders() {
  const list = document.getElementById("offenderList");
  const template = document.getElementById("offenderTemplate");
  const visibleFindings = state.findings
    .filter((finding) => state.retailerFilter === "all" || finding.retailer === state.retailerFilter)
    .slice(0, 8);

  list.replaceChildren(
    ...visibleFindings.map((finding) => {
      const card = template.content.firstElementChild.cloneNode(true);
      card.querySelector(".offender-title").textContent = `${finding.retailer} - ${finding.groupName}`;
      card.querySelector(".score-pill").textContent = `${finding.offenderScore}/100`;
      card.querySelector(".offender-meta").textContent = finding.recommendation;
      card.querySelector(".score-bar span").style.setProperty("--score-width", `${finding.offenderScore}%`);

      const evidence = card.querySelector(".evidence-line");
      evidence.replaceChildren(
        evidenceItem("YoY", formatPercent(finding.yoy)),
        evidenceItem("Competitor median", formatPercent(finding.competitorMedianYoy)),
        evidenceItem("Premium", formatPercent(finding.currentPremium)),
      );
      return card;
    }),
  );
}

function renderRetailerTotals() {
  const container = document.getElementById("retailerTotals");
  const totals = retailerBasketTotals();
  const maxTotal = Math.max(...totals.map((total) => total.total));

  container.replaceChildren(
    ...totals.map((total) => {
      const element = document.createElement("article");
      element.className = "retailer-total";
      element.innerHTML = `
        <span>${total.retailer}</span>
        <strong>${formatMoney(total.total)}</strong>
        <div class="score-bar" aria-hidden="true"><span style="--score-width: ${(total.total / maxTotal) * 100}%"></span></div>
      `;
      return element;
    }),
  );
}

function renderComparison() {
  const group = state.fixture.groups.find((item) => item.slug === state.selectedGroup);
  if (!group) return;

  document.getElementById("groupSelect").value = group.slug;

  const groupFindings = state.findings
    .filter((finding) => finding.groupSlug === group.slug)
    .sort((a, b) => b.offenderScore - a.offenderScore);

  const worst = groupFindings[0];
  const cheapest = groupFindings.reduce((best, finding) =>
    finding.currentUnitPrice < best.currentUnitPrice ? finding : best,
  );

  document.getElementById("groupEvidence").replaceChildren(
    evidenceCard("Worst retailer", worst.retailer, `${worst.offenderScore}/100 offender score`),
    evidenceCard("Cheapest equivalent", cheapest.retailer, `${formatMoney(cheapest.currentUnitPrice)} per ${group.unit_basis}`),
    evidenceCard("Data confidence", "High", "4 retailer matches in fixture data"),
  );

  document.getElementById("comparisonRows").replaceChildren(
    ...groupFindings.map((finding) => {
      const row = document.createElement("tr");
      const verdict = verdictForScore(finding.offenderScore);
      row.innerHTML = `
        <td><strong>${escapeHtml(finding.retailer)}</strong></td>
        <td>${escapeHtml(finding.productName)}</td>
        <td>${formatMoney(finding.currentPrice)}</td>
        <td>${formatMoney(finding.currentUnitPrice)} / ${escapeHtml(group.unit_basis)}</td>
        <td>${formatPercent(finding.yoy)}</td>
        <td>${formatPercent(finding.currentPremium)}</td>
        <td>${finding.offenderScore}</td>
        <td><span class="verdict-pill ${verdict.className}">${verdict.label}</span></td>
      `;
      return row;
    }),
  );
}

function renderManualObservations() {
  document.getElementById("manualCaptureCount").textContent = state.manualObservations.length;
  document.getElementById("captureSummary").replaceChildren(
    evidenceCard("Draft records", String(state.manualObservations.length), "ready for ingestion review"),
    evidenceCard("Storage", "Browser", "local capture queue"),
  );
  document.getElementById("exportPreview").value = JSON.stringify(state.manualObservations, null, 2);

  const list = document.getElementById("manualObservationList");
  if (state.manualObservations.length === 0) {
    const empty = document.createElement("article");
    empty.className = "manual-item";
    empty.innerHTML = "<strong>No manual observations</strong><span>Capture queue is empty</span>";
    list.replaceChildren(empty);
    return;
  }

  list.replaceChildren(
    ...state.manualObservations.map((observation) => {
      const item = document.createElement("article");
      item.className = "manual-item";
      item.innerHTML = `
        <strong>${escapeHtml(observation.retailer)} - ${escapeHtml(observation.product_name)}</strong>
        <span>${escapeHtml(observation.equivalence_group_slug)} · ${formatMoney(observation.shelf_price)} · ${escapeHtml(observation.collected_at)}</span>
      `;
      return item;
    }),
  );
}

function renderSchema() {
  document.getElementById("schemaGrid").replaceChildren(
    ...schemaCards.map((card) => {
      const element = document.createElement("article");
      element.className = "schema-card";
      element.innerHTML = `
        <strong>${escapeHtml(card.title)}</strong>
        <code>${escapeHtml(card.table)}</code>
        <span>${escapeHtml(card.fields)}</span>
      `;
      return element;
    }),
  );
}

function handleCaptureSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const group = state.fixture.groups.find((item) => item.slug === data.get("groupSlug"));

  const observation = {
    collection_target: {
      retailer: data.get("retailer"),
      equivalence_group_slug: data.get("groupSlug"),
      target_name: data.get("productName"),
      target_url: data.get("url") || null,
      external_product_id: data.get("externalProductId") || null,
      postcode_context: data.get("postcodeContext") || null,
      collection_frequency: "manual",
      priority: 50,
    },
    retailer: data.get("retailer"),
    equivalence_group_slug: data.get("groupSlug"),
    unit_basis: group?.unit_basis ?? data.get("unitBasis"),
    product_name: data.get("productName"),
    external_product_id: data.get("externalProductId") || null,
    url: data.get("url") || null,
    shelf_price: numberOrNull(data.get("shelfPrice")),
    loyalty_price: numberOrNull(data.get("loyaltyPrice")),
    unit_price: numberOrNull(data.get("unitPrice")),
    unit_price_basis: data.get("unitBasis"),
    pack_size_value: numberOrNull(data.get("packSizeValue")),
    pack_size_unit: data.get("packSizeUnit"),
    promotion_text: data.get("promotionText") || null,
    postcode_context: data.get("postcodeContext") || null,
    collection_status: "manual_capture",
    collected_at: new Date().toISOString(),
  };

  state.manualObservations.unshift(observation);
  saveManualObservations();
  form.reset();
  renderManualObservations();
}

function buildFindings(fixture) {
  const findings = [];

  for (const group of fixture.groups) {
    const enriched = group.observations.map((observation) => {
      const currentUnitPrice = unitPrice(observation.current);
      const previousUnitPrice = unitPrice(observation.previous_year);
      const yoy = relativeChange(currentUnitPrice, previousUnitPrice);
      return { observation, currentUnitPrice, previousUnitPrice, yoy };
    });
    const yoyByRetailer = Object.fromEntries(enriched.map((item) => [item.observation.retailer, item.yoy]));
    const cheapestUnitPrice = Math.min(...enriched.map((item) => item.currentUnitPrice));

    for (const item of enriched) {
      const competitorMedianYoy = median(
        Object.entries(yoyByRetailer)
          .filter(([retailer]) => retailer !== item.observation.retailer)
          .map(([, yoy]) => yoy),
      );
      const excess = item.yoy - competitorMedianYoy;
      const currentPremium = item.currentUnitPrice / cheapestUnitPrice - 1;
      const offenderScore = weightedScore(excess, currentPremium);
      const verdict = verdictForScore(offenderScore);

      findings.push({
        groupSlug: group.slug,
        groupName: group.display_name,
        retailer: item.observation.retailer,
        productName: item.observation.product_name,
        currentPrice: Number(item.observation.current.price),
        currentUnitPrice: item.currentUnitPrice,
        previousUnitPrice: item.previousUnitPrice,
        yoy: item.yoy,
        competitorMedianYoy,
        currentPremium,
        offenderScore,
        recommendation: recommendationFor(verdict.label, item.observation.retailer),
      });
    }
  }

  return findings.sort((a, b) => b.offenderScore - a.offenderScore || b.currentPremium - a.currentPremium);
}

function retailerBasketTotals() {
  const totals = new Map();
  for (const group of state.fixture.groups) {
    for (const observation of group.observations) {
      totals.set(
        observation.retailer,
        (totals.get(observation.retailer) ?? 0) + Number(observation.current.price),
      );
    }
  }

  return [...totals.entries()]
    .map(([retailer, total]) => ({ retailer, total }))
    .sort((a, b) => b.total - a.total);
}

function unitPrice(observation) {
  return Number(observation.price) / Number(observation.normalised_size);
}

function relativeChange(current, previous) {
  return (current - previous) / previous;
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
}

function weightedScore(excessInflation, currentPremium) {
  const excessScore = ratioToScore(excessInflation, 0.5);
  const premiumScore = ratioToScore(currentPremium, 0.5);
  return Math.round((0.4 * excessScore + 0.25 * premiumScore) * 10) / 10;
}

function ratioToScore(value, cap) {
  return Math.max(0, Math.min(100, (value / cap) * 100));
}

function verdictForScore(score) {
  if (score >= 60) return { label: "Avoid", className: "avoid" };
  if (score >= 40) return { label: "Poor value", className: "watch" };
  if (score >= 20) return { label: "Watch", className: "watch" };
  return { label: "Normal", className: "normal" };
}

function recommendationFor(verdict, retailer) {
  if (verdict === "Avoid") return `Avoid ${retailer} for this item this week.`;
  if (verdict === "Poor value") return `${retailer} is poor value against comparable products.`;
  if (verdict === "Watch") return `${retailer} is mildly above the comparison set.`;
  return "No issue detected.";
}

function evidenceItem(label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = value;
  wrapper.append(term, detail);
  return wrapper;
}

function evidenceCard(label, value, detail) {
  const card = document.createElement("article");
  card.className = "evidence-card";
  card.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><p>${escapeHtml(detail)}</p>`;
  return card;
}

function loadManualObservations() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveManualObservations() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.manualObservations));
}

function downloadManualObservations() {
  const blob = new Blob([JSON.stringify(state.manualObservations, null, 2)], {
    type: "application/json",
  });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `basketguard-manual-observations-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function numberOrNull(value) {
  return value === null || value === "" ? null : Number(value);
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(value);
}

function formatPercent(value) {
  return new Intl.NumberFormat("en-GB", {
    style: "percent",
    maximumFractionDigits: 1,
    signDisplay: "exceptZero",
  }).format(value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
