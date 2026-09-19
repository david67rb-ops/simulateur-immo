const eur = (v) =>
  v === null || v === undefined
    ? "–"
    : v.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

const pct = (v, digits = 2) =>
  v === null || v === undefined ? "–" : (v * 100).toFixed(digits) + " %";

let lastMarketResult = null;
let cashflowChart = null;

// ---------- Type de projet / structure juridique (global) ----------

const typeProjetSelect = document.getElementById("type-projet");
const structureSelect = document.getElementById("structure-juridique");
const structureNote = document.getElementById("structure-note");
const simForm = document.getElementById("sim-form");

function hide(id, hidden) {
  const el = document.getElementById(id);
  if (el) el.hidden = hidden;
}

function updateVisibility() {
  const typeProjet = typeProjetSelect.value;
  const structure = structureSelect.value;
  const regimeLocationField = simForm.querySelector("select[name=regime_location]");
  const regimeLocation = regimeLocationField ? regimeLocationField.value : "nue";

  const isLCD = typeProjet === "location_courte_duree";
  const isAchatRevente = typeProjet === "achat_revente";
  const isMeublee = isLCD || regimeLocation === "meublee";
  const isSciIs = structure === "sci_is";

  hide("fieldset-lcd", !isLCD);
  hide("fieldset-achat-revente", !isAchatRevente);
  hide("fieldset-amortissement", isAchatRevente || !(isMeublee || isSciIs));
  hide("fieldset-regime", isAchatRevente);

  hide("label-regime-location", isLCD);
  hide("label-tmi", isSciIs);

  for (const id of [
    "label-loyer",
    "label-charges-copro",
    "label-frais-gestion",
    "label-vacance",
    "label-entretien",
    "label-duree-credit",
    "label-duree-projection",
    "label-reval-loyers",
  ]) {
    hide(id, isAchatRevente);
  }
  hide("label-frais-comptable", isAchatRevente || !(isMeublee || isSciIs));
  hide("label-mobilier", isAchatRevente || !isMeublee);

  // Marché : le loyer n'a pas de sens pour une opération d'achat-revente
  document.getElementById("ms-loyer-block").hidden = isAchatRevente;

  let note = "";
  if (isLCD && structure === "sci_ir") {
    note =
      "⚠️ Une SCI à l'IR pratiquant la location meublée de façon habituelle est en principe " +
      "requalifiée à l'IS par l'administration (sauf recettes meublées accessoires, < 10 % du total).";
  } else if (isSciIs) {
    note =
      "SCI à l'IS : impôt sur les sociétés (15 %/25 %), amortissement du bien, mais fiscalité " +
      "différente à la revente (pas d'abattement pour durée de détention) et flat tax de 30 % " +
      "en cas de distribution du résultat aux associés.";
  } else if (structure === "sci_ir") {
    note = "SCI à l'IR : transparente fiscalement, imposée comme en direct au nom des associés.";
  }
  structureNote.textContent = note;
}

typeProjetSelect.addEventListener("change", updateVisibility);
structureSelect.addEventListener("change", updateVisibility);
simForm.querySelector("select[name=regime_location]").addEventListener("change", updateVisibility);
updateVisibility();

// ---------- Extraction depuis un lien d'annonce ----------

document.getElementById("btn-extraire").addEventListener("click", async () => {
  const url = document.getElementById("ms-url").value.trim();
  const statusEl = document.getElementById("extract-status");
  if (!url) {
    statusEl.textContent = "Colle le lien d'une annonce ci-dessus.";
    statusEl.className = "status error";
    return;
  }
  statusEl.textContent = "Extraction en cours…";
  statusEl.className = "status";

  try {
    const resp = await fetch("/api/parse-listing", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Échec de l'extraction");

    if (data.adresse) document.getElementById("ms-adresse").value = data.adresse;
    if (data.type_bien) document.getElementById("ms-type").value = data.type_bien;
    if (data.surface_m2) document.getElementById("ms-surface").value = data.surface_m2;
    if (data.prix_achat) simForm.prix_achat.value = Math.round(data.prix_achat);
    if (data.surface_m2) simForm.surface_m2.value = data.surface_m2;
    if (data.type_bien) simForm.type_bien.value = data.type_bien;

    const manquants = data.champs_manquants || [];
    statusEl.textContent = manquants.length
      ? `Extrait (à vérifier) — champs non trouvés : ${manquants.join(", ")}.`
      : "Informations extraites et préremplies ci-dessous.";
  } catch (err) {
    statusEl.textContent = "Erreur : " + err.message;
    statusEl.className = "status error";
  }
});

// ---------- Calcul automatique des frais de notaire ----------

document.getElementById("btn-calc-notaire").addEventListener("click", async () => {
  const prixAchat = parseFloat(simForm.prix_achat.value);
  const neuf = simForm.bien_neuf.value === "true";
  if (!prixAchat || prixAchat <= 0) return;

  const resp = await fetch("/api/frais-notaire", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prix_achat: prixAchat, neuf }),
  });
  const data = await resp.json();
  if (resp.ok) {
    simForm.frais_notaire.value = Math.round(data.total);
  }
});

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
    type_projet: typeProjetSelect.value,
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
    document.getElementById("ms-prix-bas").textContent = comp.prix_m2_bas ? `${eur(comp.prix_m2_bas)}/m²` : "–";
    document.getElementById("ms-prix-moyen").textContent = comp.prix_m2_moyen ? `${eur(comp.prix_m2_moyen)}/m²` : "Pas assez de données";
    document.getElementById("ms-prix-haut").textContent = comp.prix_m2_haut ? `${eur(comp.prix_m2_haut)}/m²` : "–";
    document.getElementById("ms-nb-trans").textContent = comp.nb_transactions ?? "0";

    const loyer = data.loyers_marche || {};
    document.getElementById("ms-loyer-bas").textContent = loyer.loyer_m2_bas ? `${loyer.loyer_m2_bas.toFixed(2)} €/m²` : "–";
    document.getElementById("ms-loyer-moyen").textContent = loyer.loyer_m2_moyen ? `${loyer.loyer_m2_moyen.toFixed(2)} €/m²` : "Non disponible";
    document.getElementById("ms-loyer-haut").textContent = loyer.loyer_m2_haut ? `${loyer.loyer_m2_haut.toFixed(2)} €/m²` : "–";
    document.getElementById("ms-fiabilite").textContent = loyer.fiabilite_r2 ?? "–";

    let note = "";
    if (loyer.nb_observations_commune !== undefined && loyer.nb_observations_commune < 30) {
      note += "⚠️ Peu d'observations pour cette commune : indicateur de loyer peu fiable. ";
    }
    if (!comp.nb_transactions) {
      note += "⚠️ Aucune transaction DVF trouvée dans ce rayon/commune pour ce type de bien. ";
    }
    if (data.avertissement_loyer) {
      note += "⚠️ " + data.avertissement_loyer;
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
  const surface = parseFloat(document.getElementById("ms-surface").value);
  simForm.type_bien.value = document.getElementById("ms-type").value;
  simForm.surface_m2.value = surface;

  const prixEstime = lastMarketResult.prix_marche_estime_pour_surface;
  if (prixEstime) simForm.prix_achat.value = Math.round(prixEstime);

  const loyerEstime = lastMarketResult.loyer_mensuel_estime_pour_surface;
  if (loyerEstime && simForm.loyer_mensuel_hors_charges) {
    simForm.loyer_mensuel_hors_charges.value = Math.round(loyerEstime);
  }

  document.getElementById("sim-section").scrollIntoView({ behavior: "smooth" });
});

// ---------- Simulateur ----------

function buildPayload() {
  const fd = new FormData(simForm);
  const payload = {
    type_projet: typeProjetSelect.value,
    structure_juridique: structureSelect.value,
  };
  const champsBooleens = ["bien_neuf", "meuble_tourisme_classe", "marchand_de_biens_professionnel"];
  const champsTexte = ["type_bien", "regime_location"];

  for (const [key, value] of fd.entries()) {
    if (champsBooleens.includes(key)) {
      payload[key] = value === "true";
    } else if (champsTexte.includes(key)) {
      payload[key] = value;
    } else if (value === "") {
      // champ optionnel laissé vide (ex. prix_revente_vise) -> ne pas l'envoyer
      continue;
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
    "frais_plateforme_pct",
    "frais_agence_revente_pct",
  ]) {
    if (payload[key] !== undefined) payload[key] = payload[key] / 100;
  }
  return payload;
}

simForm.addEventListener("submit", async (e) => {
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
  document.getElementById("results-section").hidden = false;
  if (data.type_projet === "achat_revente") {
    document.getElementById("results-location").hidden = true;
    document.getElementById("results-achat-revente").hidden = false;
    renderAchatRevente(data.achat_revente);
  } else {
    document.getElementById("results-achat-revente").hidden = true;
    document.getElementById("results-location").hidden = false;
    renderResultsLocation(data);
  }
});

function renderAchatRevente(r) {
  document.getElementById("ar-marge-brute").textContent = eur(r.marge_brute_avant_impot);
  document.getElementById("ar-regime").textContent = r.regime_fiscal;
  document.getElementById("ar-impot").textContent = eur(r.impot_total);
  document.getElementById("ar-marge-nette").textContent = eur(r.marge_nette);
  document.getElementById("ar-cash-final").textContent = eur(r.cash_final_investisseur);
  document.getElementById("ar-rentabilite").textContent = pct(r.rentabilite_operation_pct, 1);
  document.getElementById("ar-tri").textContent = r.tri_annualise !== null ? pct(r.tri_annualise, 1) : "n/a";
  document.getElementById("ar-portage").textContent = eur(r.frais_portage_total);

  const rows = [
    ["Coût total d'acquisition", eur(r.cout_total_acquisition)],
    ["Montant emprunté", eur(r.montant_emprunte)],
    ["Apport réel", eur(r.apport_reel)],
    ["Intérêts de portage (crédit relais)", eur(r.frais_portage_interets)],
    ["Taxe foncière (prorata portage)", eur(r.frais_portage_taxe_fonciere)],
    ["Prix de revente retenu", eur(r.prix_revente)],
    ["Frais d'agence à la revente", eur(r.frais_agence_revente)],
    ["Produit net de vente", eur(r.produit_net_vente)],
    ["Base imposable", eur(r.base_imposable)],
  ];
  const tbody = document.querySelector("#table-achat-revente tbody");
  tbody.innerHTML = rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("");
}

function renderResultsLocation(data) {
  document.getElementById("res-cout-total").textContent = eur(data.cout_total_acquisition);
  document.getElementById("res-rendement-brut").textContent = pct(data.rendement_brut, 1);
  document.getElementById("res-rendement-net").textContent = pct(data.rendement_net_charges, 1);
  document.getElementById("res-mensualite").textContent =
    eur(data.mensualite_credit_hors_assurance) + "/mois (hors assurance)";

  const avertissementsEl = document.getElementById("res-avertissements");
  avertissementsEl.innerHTML = (data.avertissements || [])
    .map((a) => `<div class="warning-box">⚠️ ${a}</div>`)
    .join("");

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
  const colors = ["#1d6f5c", "#c9822a"];
  const datasets = regimes.map((regime, i) => {
    let cumul = 0;
    const values = data.cashflows_par_regime[regime].slice(1).map((cf) => {
      cumul += cf;
      return cumul;
    });
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
