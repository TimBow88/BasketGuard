const FIXTURE_URL = "/tests/fixtures/seed_price_observations.json";
const STORAGE_KEY = "basketguard.manualObservations";
const STALE_AFTER_DAYS = 7;

const state = {
  fixture: null,
  findings: [],
  manualObservations: [],
  selectedGroup: null,
  retailerFilter: "all",
  error: null,
  isLoading: false,
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
  switchView(document.querySelector(".tab.is-active")?.dataset.view ?? "overview");
  state.manualObservations = loadManualObservations();
  await loadData();
}

async function loadData() {
  state.isLoading = true;
  state.error = null;
  renderLoading();

  try {
    const response = await fetch(FIXTURE_URL);
    if (!response.ok) {
      throw new Error(`Unable to load fixture data: ${response.status}`);
    }

    state.fixture = await response.json();
    state.findings = buildFindings(state.fixture);
    state.selectedGroup = state.selectedGroup ?? state.fixture.groups[0]?.slug ?? null;

    populateSelectors();
  } catch (error) {
    state.error = error;
  } finally {
    state.isLoading = false;
    render();
  }
}

function bindNavigation() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });
}

function switchView(viewId) {
  document.querySelectorAll(".tab").forEach((item) => {
    const isActive = item.dataset.view === viewId;
    item.classList.toggle("is-active", isActive);
    item.setAttribute("aria-selected", String(isActive));
    item.tabIndex = isActive ? 0 : -1;
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("is-active", view.id === viewId);
  });
}

function bindControls() {
  document.getElementById("refreshButton").addEventListener("click", loadData);
  document.getElementById("exportButton").addEventListener("click", downloadManualObservations);
  document.getElementById("inspectTopFindingButton").addEventListener("click", () => {
    const topFinding = state.findings[0];
    if (topFinding) {
      state.selectedGroup = topFinding.groupSlug;
      renderComparison();
      switchView("comparisons");
    }
  });
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
    renderSummary();
  });
}

function populateSelectors() {
  if (!state.fixture) return;

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

function renderLoading() {
  showStatus("Loading latest fixture-backed report data.", "info");
  document.getElementById("weeklyVerdict").textContent = "Loading report";
  document.getElementById("weeklyVerdictDetail").textContent = "Checking the latest fixture-backed price observations.";
  document.getElementById("riskIndex").textContent = "-";
  document.getElementById("riskIndexDetail").textContent = "Loading top finding";
  document.getElementById("headerFreshness").textContent = "-";
  document.getElementById("headerConfidence").textContent = "-";
  document.getElementById("headerCoverage").textContent = "-";
  updateRailStatus("Loading report", "Checking evidence", "info");
  document.getElementById("topFindingsList").replaceChildren(emptyState("Report data is loading."));
  document.getElementById("offenderList").replaceChildren(emptyState("Report data is loading."));
}

function render() {
  if (state.error) {
    renderError();
    renderManualObservations();
    renderSchema();
    return;
  }

  if (!state.fixture) return;

  renderStatusBanner();
  renderSummary();
  renderOffenders();
  renderRetailerTotals();
  renderBasketComparison();
  renderComparison();
  renderManualObservations();
  renderReviewQueue();
  renderSourceHealth();
  renderSchema();
}

function renderError() {
  showStatus(`Report data unavailable: ${state.error.message}`, "error");
  document.getElementById("weeklyVerdict").textContent = "Report unavailable";
  document.getElementById("weeklyVerdictDetail").textContent = "BasketGuard could not load the local report fixture.";
  document.getElementById("riskIndex").textContent = "-";
  document.getElementById("riskIndexDetail").textContent = "No score";
  document.getElementById("headerFreshness").textContent = "Unavailable";
  document.getElementById("headerConfidence").textContent = "Unavailable";
  document.getElementById("headerCoverage").textContent = "Unavailable";
  updateRailStatus("Report unavailable", "Fixture failed to load", "error");
  for (const id of ["topFindingsList", "offenderList", "retailerTotals", "basketRetailerTotals", "basketRoute", "groupSummary", "groupEvidence"]) {
    document.getElementById(id).replaceChildren(emptyState("No report data available."));
  }
  document.getElementById("basketCoverageRows").replaceChildren();
  document.getElementById("dataFreshness").textContent = "Unavailable";
  document.getElementById("confidenceBand").textContent = "Unavailable";
}

function renderStatusBanner() {
  const freshness = freshnessInfo();
  if (freshness.isStale) {
    showStatus(
      `Data is ${freshness.daysOld} days old. Treat recommendations as a review signal until sources refresh.`,
      "warning",
    );
    updateRailStatus("Stale fixture", `${freshness.daysOld} days old`, "warning");
    return;
  }

  showStatus("Fixture-backed report loaded. Public claims still require source and wording review.", "info");
  updateRailStatus("Fixture report", "Evidence loaded", "normal");
}

function showStatus(message, tone) {
  const banner = document.getElementById("statusBanner");
  banner.textContent = message;
  banner.className = `status-banner is-visible ${tone === "error" ? "error" : tone === "warning" ? "warning" : ""}`;
}

function updateRailStatus(label, detail, tone) {
  document.getElementById("railStatusLabel").textContent = label;
  document.getElementById("railStatusDetail").textContent = detail;
  const dot = document.querySelector(".status-dot");
  dot.dataset.tone = tone;
}

function renderSummary() {
  const totals = retailerBasketTotals();
  const worst = totals[0];
  const cheapestBasket = Math.min(...totals.map((total) => total.total));
  const overspend = worst.total - cheapestBasket;
  const topFinding = state.findings[0];
  const freshness = freshnessInfo();
  const confidence = confidenceInfo();
  const warningCount = state.findings.filter((finding) => finding.offenderScore >= 40).length;

  document.getElementById("weeklyVerdict").textContent =
    warningCount > 0 ? `${topFinding.retailer} needs attention this week` : "No major warning this week";
  document.getElementById("weeklyVerdictDetail").textContent =
    warningCount > 0
      ? `${topFinding.groupName} is the highest-risk tracked group. ${topFinding.recommendation}`
      : "Tracked groups do not show a high-confidence avoid signal in the current fixture data.";
  document.getElementById("verdictCaveat").textContent = freshness.isStale
    ? "Data is stale; use this as a review signal."
    : "Evidence-backed comparison across tracked groups.";
  document.getElementById("inspectTopFindingButton").disabled = !topFinding;

  document.getElementById("worstRetailer").textContent = worst.retailer;
  document.getElementById("worstRetailerDetail").textContent = `${formatMoney(worst.total)} tracked basket`;
  document.getElementById("avoidableOverspend").textContent = formatMoney(overspend);
  document.getElementById("trackedGroups").textContent = state.fixture.groups.length;
  document.getElementById("observationCoverage").textContent = `${state.findings.length} retailer observations`;
  document.getElementById("manualCaptureCount").textContent = state.manualObservations.length;
  document.getElementById("dataFreshness").textContent = freshness.label;
  document.getElementById("confidenceBand").textContent = confidence.label;
  document.getElementById("riskIndex").textContent = topFinding ? Math.round(topFinding.offenderScore) : "0";
  document.getElementById("riskIndexDetail").textContent = topFinding ? `${topFinding.retailer} top finding` : "No high-risk finding";
  document.getElementById("headerFreshness").textContent = freshness.label;
  document.getElementById("headerConfidence").textContent = confidence.label.replace(" confidence", "");
  document.getElementById("headerCoverage").textContent = `${state.fixture.groups.length} groups`;

  renderTopFindings();
}

function renderTopFindings() {
  const topFindings = state.findings.slice(0, 3);
  const list = document.getElementById("topFindingsList");
  if (topFindings.length === 0) {
    list.replaceChildren(emptyState("No report findings available."));
    return;
  }

  list.replaceChildren(...topFindings.map((finding) => offenderCard(finding)));
}

function renderOffenders() {
  const list = document.getElementById("offenderList");
  const visibleFindings = state.findings
    .filter((finding) => state.retailerFilter === "all" || finding.retailer === state.retailerFilter)
    .slice(0, 12);

  if (visibleFindings.length === 0) {
    list.replaceChildren(emptyState("No findings match this retailer filter."));
    return;
  }

  list.replaceChildren(...visibleFindings.map((finding) => offenderCard(finding)));
}

function offenderCard(finding) {
  const template = document.getElementById("offenderTemplate");
  const card = template.content.firstElementChild.cloneNode(true);
  const verdict = verdictForScore(finding.offenderScore);

  card.querySelector(".offender-retailer").textContent = `${finding.retailer} - ${verdict.label}`;
  card.querySelector(".offender-title").textContent = finding.groupName;
  card.querySelector(".score-pill").textContent = `${finding.offenderScore}/100`;
  card.querySelector(".offender-meta").textContent = finding.recommendation;
  card.querySelector(".score-bar span").style.setProperty("--score-width", `${finding.offenderScore}%`);

  const evidence = card.querySelector(".evidence-line");
  evidence.replaceChildren(
    evidenceItem("YoY", formatPercent(finding.yoy)),
    evidenceItem("Competitor median", formatPercent(finding.competitorMedianYoy)),
    evidenceItem("Premium", formatPercent(finding.currentPremium)),
    evidenceItem("Cheapest", `${finding.cheapestRetailer} ${formatMoney(finding.cheapestUnitPrice)}`),
  );

  const reasons = card.querySelector(".why-flagged ul");
  reasons.replaceChildren(
    listItem(`${finding.retailer} unit price is ${formatPercent(finding.currentPremium)} versus the cheapest equivalent.`),
    listItem(`Year-on-year movement is ${formatPercent(finding.yoy)} versus competitor median ${formatPercent(finding.competitorMedianYoy)}.`),
    listItem(`Comparable products are available at ${finding.cheapestRetailer} for ${formatMoney(finding.cheapestUnitPrice)} per ${finding.unitBasis}.`),
  );

  return card;
}

function renderRetailerTotals() {
  const totals = retailerBasketTotals();
  renderRetailerTotalList(document.getElementById("retailerTotals"), totals);
  renderRetailerTotalList(document.getElementById("basketRetailerTotals"), totals);
}

function renderRetailerTotalList(container, totals) {
  const maxTotal = Math.max(...totals.map((total) => total.total));
  const cheapest = Math.min(...totals.map((total) => total.total));

  container.replaceChildren(
    ...totals.map((total) => {
      const element = document.createElement("article");
      element.className = "retailer-total";
      const premium = total.total - cheapest;
      element.innerHTML = `
        <span>${escapeHtml(total.retailer)}</span>
        <strong>${formatMoney(total.total)}</strong>
        <p class="small-note">${premium === 0 ? "Cheapest tracked basket" : `${formatMoney(premium)} above cheapest`}</p>
        <div class="score-bar" aria-hidden="true"><span style="--score-width: ${(total.total / maxTotal) * 100}%"></span></div>
      `;
      return element;
    }),
  );
}

function renderBasketComparison() {
  const totals = retailerBasketTotals();
  const worst = totals[0];
  const cheapest = totals[totals.length - 1];
  const overspend = worst.total - cheapest.total;
  const freshness = freshnessInfo();
  const coverage = basketCoverage();

  document.getElementById("basketRoute").replaceChildren(
    routeCard("Cheapest tracked basket", cheapest.retailer, `${formatMoney(cheapest.total)} across ${state.fixture.groups.length} groups`),
    routeCard("Worst tracked basket", worst.retailer, `${formatMoney(worst.total)} in fixture data`),
    routeCard("Avoidable overspend", formatMoney(overspend), `${worst.retailer} versus ${cheapest.retailer}`),
    routeCard(
      freshness.isStale ? "Caveat" : "Coverage",
      freshness.isStale ? "Stale data" : "Complete fixture coverage",
      freshness.isStale
        ? `${freshness.daysOld} days since last collection; refresh before public claims.`
        : "Every tracked group has four retailer observations in this fixture.",
    ),
  );

  document.getElementById("basketCoverageRows").replaceChildren(
    ...coverage.map((item) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td><strong>${escapeHtml(item.retailer)}</strong></td>
        <td>${item.observedGroups}/${item.totalGroups} groups</td>
        <td>${item.missingGroups.length === 0 ? "None" : escapeHtml(item.missingGroups.join(", "))}</td>
        <td>${formatMoney(item.total)}</td>
        <td>${item.missingGroups.length === 0 ? "Complete fixture coverage" : "Comparison is partial"}</td>
      `;
      return row;
    }),
  );
}

function renderComparison() {
  const group = state.fixture.groups.find((item) => item.slug === state.selectedGroup);
  if (!group) {
    document.getElementById("groupSummary").replaceChildren(emptyState("No product group selected."));
    document.getElementById("groupEvidence").replaceChildren(emptyState("No product group selected."));
    document.getElementById("comparisonRows").replaceChildren();
    return;
  }

  document.getElementById("groupSelect").value = group.slug;

  const groupFindings = state.findings
    .filter((finding) => finding.groupSlug === group.slug)
    .sort((a, b) => b.offenderScore - a.offenderScore);

  const worst = groupFindings[0];
  const cheapest = groupFindings.reduce((best, finding) =>
    finding.currentUnitPrice < best.currentUnitPrice ? finding : best,
  );
  const confidence = groupFindings.length >= 4 ? "High" : groupFindings.length >= 3 ? "Good" : "Limited";

  document.getElementById("groupSummary").replaceChildren(
    detailSummary(
      group.display_name,
      `${recommendationFor(verdictForScore(worst.offenderScore).label, worst.retailer)} Cheapest equivalent is ${cheapest.retailer} at ${formatMoney(cheapest.currentUnitPrice)} per ${group.unit_basis}.`,
      `${groupFindings.length} retailer matches - ${confidence.toLowerCase()} confidence`,
    ),
  );

  document.getElementById("groupEvidence").replaceChildren(
    evidenceCard("Recommendation", recommendationFor(verdictForScore(worst.offenderScore).label, worst.retailer), `${worst.offenderScore}/100 offender score`),
    evidenceCard("Cheapest equivalent", cheapest.retailer, `${formatMoney(cheapest.currentUnitPrice)} per ${group.unit_basis}`),
    evidenceCard("Data confidence", confidence, `${groupFindings.length} retailer matches in fixture data`),
    evidenceCard("Source freshness", freshnessInfo().label, `Collected ${state.fixture.collected_at}`),
  );

  document.getElementById("comparisonRows").replaceChildren(
    ...groupFindings.map((finding) => {
      const row = document.createElement("tr");
      const verdict = verdictForScore(finding.offenderScore);
      row.innerHTML = `
        <td><strong>${escapeHtml(finding.retailer)}</strong></td>
        <td>${escapeHtml(finding.productName)}</td>
        <td>${formatMoney(finding.currentPrice)}</td>
        <td>${escapeHtml(finding.packLabel)}</td>
        <td>${formatMoney(finding.currentUnitPrice)} / ${escapeHtml(group.unit_basis)}</td>
        <td>${escapeHtml(finding.loyaltyLabel)}</td>
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
    evidenceCard("Draft records", String(state.manualObservations.length), "Ready for ingestion review"),
    evidenceCard("Storage", "Browser", "Local capture queue"),
  );
  document.getElementById("exportPreview").value = JSON.stringify(state.manualObservations, null, 2);

  const list = document.getElementById("manualObservationList");
  if (state.manualObservations.length === 0) {
    list.replaceChildren(emptyState("No manual observations. Capture queue is empty."));
    return;
  }

  list.replaceChildren(
    ...state.manualObservations.map((observation) => {
      const item = document.createElement("article");
      item.className = "manual-item";
      item.innerHTML = `
        <strong>${escapeHtml(observation.retailer)} - ${escapeHtml(observation.product_name)}</strong>
        <span>${escapeHtml(observation.equivalence_group_slug)} - ${formatMoney(observation.shelf_price)} - ${escapeHtml(observation.collected_at)}</span>
      `;
      return item;
    }),
  );
}

function renderReviewQueue() {
  document.getElementById("reviewQueueSummary").replaceChildren(
    methodCard("No unresolved fixture items", "The static demo data is treated as reviewed for UI purposes."),
    methodCard("Human review hook", "Parser, grouping and low-confidence cases should route here once API data is connected."),
    methodCard("Claim gating", "Public-facing alerts should not promote unresolved review items."),
    methodCard("Manual captures", `${state.manualObservations.length} local draft records are waiting outside the database.`),
  );
}

function renderSourceHealth() {
  const freshness = freshnessInfo();
  document.getElementById("sourceHealthStatus").textContent = freshness.isStale ? "Stale fixture" : "Fixture-backed";
  document.getElementById("sourceHealthGrid").replaceChildren(
    methodCard("Last collected", state.fixture.collected_at, freshness.isStale ? "warning" : "normal"),
    methodCard("Retailers", `${retailerBasketTotals().length} covered`, "normal"),
    methodCard("Observations", `${state.findings.length} loaded`, "normal"),
    methodCard("Data mode", "Local fixture", "info"),
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
  renderSummary();
  renderReviewQueue();
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
    const cheapest = enriched.reduce((best, item) =>
      item.currentUnitPrice < best.currentUnitPrice ? item : best,
    );

    for (const item of enriched) {
      const competitorMedianYoy = median(
        Object.entries(yoyByRetailer)
          .filter(([retailer]) => retailer !== item.observation.retailer)
          .map(([, yoy]) => yoy),
      );
      const excess = item.yoy - competitorMedianYoy;
      const currentPremium = item.currentUnitPrice / cheapest.currentUnitPrice - 1;
      const offenderScore = weightedScore(excess, currentPremium);
      const verdict = verdictForScore(offenderScore);

      findings.push({
        groupSlug: group.slug,
        groupName: group.display_name,
        unitBasis: group.unit_basis,
        retailer: item.observation.retailer,
        productName: item.observation.product_name,
        currentPrice: Number(item.observation.current.price),
        currentUnitPrice: item.currentUnitPrice,
        packLabel: packLabel(item.observation.current.normalised_size, group.unit_basis),
        loyaltyLabel: item.observation.current.loyalty_price
          ? formatMoney(Number(item.observation.current.loyalty_price))
          : "Not supplied",
        previousUnitPrice: item.previousUnitPrice,
        yoy: item.yoy,
        competitorMedianYoy,
        currentPremium,
        cheapestRetailer: cheapest.observation.retailer,
        cheapestUnitPrice: cheapest.currentUnitPrice,
        offenderScore,
        recommendation: recommendationFor(verdict.label, item.observation.retailer),
      });
    }
  }

  return findings.sort((a, b) => b.offenderScore - a.offenderScore || b.currentPremium - a.currentPremium);
}

function retailerBasketTotals() {
  const totals = new Map();
  if (!state.fixture) return [];

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

function basketCoverage() {
  const totals = Object.fromEntries(retailerBasketTotals().map((item) => [item.retailer, item.total]));
  const retailers = [...new Set(state.fixture.groups.flatMap((group) => group.observations.map((item) => item.retailer)))].sort();
  return retailers.map((retailer) => {
    const observedGroups = state.fixture.groups.filter((group) =>
      group.observations.some((observation) => observation.retailer === retailer),
    );
    const missingGroups = state.fixture.groups
      .filter((group) => !group.observations.some((observation) => observation.retailer === retailer))
      .map((group) => group.display_name);

    return {
      retailer,
      observedGroups: observedGroups.length,
      totalGroups: state.fixture.groups.length,
      missingGroups,
      total: totals[retailer] ?? 0,
    };
  });
}

function freshnessInfo() {
  if (!state.fixture?.collected_at) {
    return { label: "Unavailable", daysOld: null, isStale: true };
  }

  const collected = new Date(`${state.fixture.collected_at}T00:00:00Z`);
  const now = new Date();
  const daysOld = Math.max(0, Math.floor((now - collected) / 86400000));
  const label = daysOld === 0 ? "Collected today" : `${daysOld} days old`;
  return { label, daysOld, isStale: daysOld > STALE_AFTER_DAYS };
}

function confidenceInfo() {
  if (!state.fixture) return { label: "Unavailable" };
  const groupCoverage = state.fixture.groups.map((group) => group.observations.length);
  const minimumCoverage = Math.min(...groupCoverage);
  if (minimumCoverage >= 4) return { label: "High confidence" };
  if (minimumCoverage >= 3) return { label: "Good confidence" };
  if (minimumCoverage >= 2) return { label: "Moderate confidence" };
  return { label: "Low confidence" };
}

function unitPrice(observation) {
  return Number(observation.price) / Number(observation.normalised_size);
}

function packLabel(normalisedSize, unitBasis) {
  const size = Number(normalisedSize);
  if (unitBasis === "kg" && size < 1) return `${Math.round(size * 1000)}g`;
  if (unitBasis === "litre" && size < 1) return `${Math.round(size * 1000)}ml`;
  return `${new Intl.NumberFormat("en-GB", { maximumFractionDigits: 3 }).format(size)} ${unitBasis}`;
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

function routeCard(label, value, detail) {
  const card = document.createElement("article");
  card.className = "route-card";
  card.innerHTML = `<span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><p>${escapeHtml(detail)}</p>`;
  return card;
}

function detailSummary(title, detail, meta) {
  const card = document.createElement("article");
  card.className = "detail-summary";
  card.innerHTML = `<span>${escapeHtml(meta)}</span><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p>`;
  return card;
}

function methodCard(title, detail, tone = "") {
  const card = document.createElement("article");
  card.className = "method-card";
  const pill = tone ? `<span class="status-pill ${tone === "warning" ? "watch" : tone}">${escapeHtml(tone)}</span>` : "";
  card.innerHTML = `<strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p>${pill}`;
  return card;
}

function emptyState(message) {
  const element = document.createElement("div");
  element.className = "empty-state";
  element.textContent = message;
  return element;
}

function listItem(text) {
  const item = document.createElement("li");
  item.textContent = text;
  return item;
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
