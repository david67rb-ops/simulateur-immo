const eur = (v) =>
  v === null || v === undefined
    ? "–"
    : v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

const pct = (v, digits = 2) =>
  v === null || v === undefined ? "–" : (v * 100).toFixed(digits) + " %";

let lastMarketResult = null;
let cashflowChart = null;

// ---------- Étude de marché ----------

document.getElementById("btn-market").addEventListener("click", async () => {
  const adresse = document.getElementById("ms-adresse").value.trim();
  const statusEl = document.getElementById("market-status");
  const resultsEl = document.getElementById("market-results");
  if (!adresse) {
    statusEl.textContent = "Merci de saisir une adresse.";
    statusEl.className = "status error";
    return;
  }
  statusEl.textContent = "Analyse en cours…";
  statusEl.className = "status";
  resultsEl.hidden = true;

  const payload = {
    adresse,
    type_bien: document.getElementById("ms-type").value,
    surface_m2: parseFloat(document.getElementById("ms-surface").value) || null,
    rayon_metres: parseInt(document.getElementById("ms-rayon").value, 10) || 500,
  };

  try {
    const resp = await fetch("/api/market-study", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Erreur inconnue");

    lastMarketResult = data;
    statusEl.textContent = `Adresse localisée : ${data.adresse.label} (INSEE ${data.adresse.code_insee})`;

    const comp = data.comparables_ventes || {};
    document.getElementById("ms-prix-m2").textContent = comp.prix_m2_median
      ? `${eur(comp.prix_m2_median)}/m²`
      : "Pas assez de données";
    document.getElementById("ms-prix-m2-moyen").textContent = comp.prix_m2_moyen
      ? `${eur(comp.prix_m2_moyen)}/m²`
      : "–";
    document.getElementById("ms-nb-trans").textContent = comp.nb_transactions ?? "0";

    const loyer = data.loyers_marche || {};
    document.getElementById("ms-loyer-m2").textContent = loyer.loyer_m2_estime
      ? `${loyer.loyer_m2_estime.toFixed(2)} €/m²`
      : "Non disponible";
    document.getElementById("ms-fiabilite").textContent = loyer.fiabilite_r2 ?? "–";

    let note = "";
    if (loyer.nb_observations_commune !== undefined && loyer.nb_observations_commune < 30) {
      note += "⚠️ Peu d'observations pour cette commune : indicateur de loyer peu fiable. ";
    }
    if (!comp.nb_transactions) {
      note += "⚠️ Aucune transaction DVF trouvée dans ce rayon/commune pour ce type de bien.";
    }
    document.getElementById("market-note").textContent = note;

    resultsEl.hidden = false;
  } catch (err) {
    statusEl.textContent = "Erreur : " + err.message;
    statusEl.className = "status error";
  }
});

document.getElementById("btn-use-market").addEventListener("click", () => {
  if (!lastMarketResult) return;
  const form = document.getElementById("sim-form");
  const surface = parseFloat(document.getElementById("ms-surface").value);
  form.type_bien.value = document.getElementById("ms-type").value;
  form.surface_m2.value = surface;

  const prixEstime = lastMarketResult.prix_marche_estime_pour_surface;
  if (prixEstime) form.prix_achat.value = Math.round(prixEstime);

  const loyerEstime = lastMarketResult.loyer_mensuel_estime_pour_surface;
  if (loyerEstime) form.loyer_mensuel_hors_charges.value = Math.round(loyerEstime);

  document.getElementById("sim-section").scrollIntoView({ behavior: "smooth" });
});

// ---------- Simulateur ----------

const form = document.getElementById("sim-form");
const regimeSelect = form.querySelector("select[name=regime_location]");
const fieldsetAmortissement = document.getElementById("fieldset-amortissement");

function toggleAmortissementFieldset() {
  fieldsetAmortissement.hidden = regimeSelect.value !== "meublee";
}
regimeSelect.addEventListener("change", toggleAmortissementFieldset);
toggleAmortissementFieldset();

function buildPayload() {
  const fd = new FormData(form);
  const payload = {};
  for (const [key, value] of fd.entries()) {
    if (["type_bien", "regime_location"].includes(key)) {
      payload[key] = value;
    } else {
      payload[key] = parseFloat(value);
    }
  }
  // Les pourcentages sont saisis en % dans l'UI, l'API attend des fractions
  for (const key of [
    "taux_credit_annuel",
    "taux_assurance_emprunteur",
    "frais_gestion_pct_loyers",
    "vacance_locative_pct",
    "part_terrain_pct",
    "taux_revalorisation_bien_annuel",
    "taux_revalorisation_loyers_annuel",
  ]) {
    if (payload[key] !== undefined) payload[key] = payload[key] / 100;
  }
  return payload;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = buildPayload();

  const resp = await fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok) {
    alert("Erreur : " + (data.detail || JSON.stringify(data)));
    return;
  }
  renderResults(data);
});

function renderResults(data) {
  document.getElementById("results-section").hidden = false;
  document.getElementById("res-cout-total").textContent = eur(data.cout_total_acquisition);
  document.getElementById("res-rendement-brut").textContent = pct(data.rendement_brut, 1);
  document.getElementById("res-rendement-net").textContent = pct(data.rendement_net_charges, 1);
  document.getElementById("res-mensualite").textContent =
    eur(data.mensualite_credit_hors_assurance) + "/mois (hors assurance)";

  const annee1 = data.annees[0];
  const regimes = Object.keys(annee1.cashflow_apres_impot);

  const tbody = document.querySelector("#table-regimes tbody");
  tbody.innerHTML = "";
  for (const regime of regimes) {
    const fiscal = annee1.fiscal[regime];
    const cashflowMensuel = annee1.cashflow_apres_impot[regime] / 12;
    const tri = data.tri_par_regime[regime];
    const eligible = fiscal.eligible === false ? " ⚠️ non éligible" : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${regime}${eligible}</td>
      <td>${eur(fiscal.revenu_imposable)}</td>
      <td>${eur(fiscal.total_prelevements)}</td>
      <td>${eur(cashflowMensuel)}</td>
      <td>${tri !== null && tri !== undefined ? pct(tri, 2) : "n/a"}</td>
    `;
    tbody.appendChild(tr);
  }

  const revTbody = document.querySelector("#table-revente tbody");
  revTbody.innerHTML = "";
  for (const regime of regimes) {
    const rev = data.reventes[regime];
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${regime}</td>
      <td>${eur(rev.valeur_revente)}</td>
      <td>${eur(rev.plus_value_imposable_ir)}</td>
      <td>${eur(rev.impot_plus_value_ir + rev.impot_plus_value_ps + rev.surtaxe)}</td>
      <td>${eur(rev.net_vendeur)}</td>
    `;
    revTbody.appendChild(tr);
  }

  renderChart(data, regimes);
}

function renderChart(data, regimes) {
  const labels = data.annees.map((a) => "Année " + a.annee);
  const datasets = regimes.map((regime, i) => {
    let cumul = 0;
    const values = data.cashflows_par_regime[regime].slice(1).map((cf, idx) => {
      cumul += cf;
      return cumul;
    });
    const colors = ["#1d6f5c", "#c9822a"];
    return {
      label: "Cash-flow cumulé — " + regime,
      data: values,
      borderColor: colors[i % colors.length],
      backgroundColor: colors[i % colors.length] + "33",
      fill: false,
      tension: 0.15,
    };
  });

  const ctx = document.getElementById("chart-cashflow").getContext("2d");
  if (cashflowChart) cashflowChart.destroy();
  cashflowChart = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: { legend: { position: "bottom" } },
      scales: { y: { ticks: { callback: (v) => eur(v) } } },
    },
  });
}
