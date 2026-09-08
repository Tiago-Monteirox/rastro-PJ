(() => {
  "use strict";

  const app = document.querySelector("#analytics-map-app");
  if (!app) return;

  const form = document.querySelector("#map-filter-form");
  const status = document.querySelector("#map-status");
  const initialElement = document.querySelector("#map-initial-data");
  const number = new Intl.NumberFormat("pt-BR");
  const percentageNumber = new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  const decimalNumber = new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  const initialData = initialElement ? JSON.parse(initialElement.textContent) : null;
  let currentData = initialData;
  let map = null;
  let mapReady = false;
  let locationsRequest = null;
  let detailsSelection = null;

  const formParameters = () => {
    const values = new URLSearchParams(new FormData(form));
    for (const [key, value] of [...values.entries()]) {
      if (!value) values.delete(key);
    }
    return values;
  };

  const fetchJson = async (url, parameters, signal) => {
    const response = await fetch(`${url}?${parameters}`, {
      headers: { Accept: "application/json" },
      signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Não foi possível atualizar a análise.");
    return payload;
  };

  const setStatus = (message, isError = false) => {
    status.textContent = message;
    status.classList.toggle("error", isError);
  };

  const setMetric = (name, value) => {
    const element = document.querySelector(`[data-metric="${name}"]`);
    if (element) element.textContent = value;
  };

  const replaceChildren = (element, children) => {
    element.replaceChildren(...children);
  };

  const signedNumber = (value) => `${value > 0 ? "+" : ""}${number.format(value)}`;

  const formattedPercentage = (value, { signed = false } = {}) => {
    if (value === null || value === undefined) return "Sem base anterior";
    const prefix = signed && value > 0 ? "+" : "";
    return `${prefix}${percentageNumber.format(value)}%`;
  };

  const movementClass = (value) => {
    if (value > 0) return "positive-value";
    if (value < 0) return "negative-value";
    return "neutral-value";
  };

  const formattedPerThousand = (value) => {
    if (value === null || value === undefined) return "Sem referência";
    return `${decimalNumber.format(value)}/1 mil`;
  };

  const rankingRows = (
    items,
    label,
    value,
    formatter = number.format.bind(number),
    colorizeMovement = false,
  ) => {
    if (!items.length) {
      const empty = document.createElement("li");
      empty.className = "map-ranking-empty";
      empty.textContent = "Nenhuma variação no recorte.";
      return [empty];
    }
    return items.map((item) => {
      const row = document.createElement("li");
      const name = document.createElement("span");
      const total = document.createElement("strong");
      const rawValue = value(item);
      name.textContent = label(item);
      total.textContent = formatter(rawValue);
      if (colorizeMovement) total.classList.add(movementClass(rawValue));
      row.append(name, total);
      return row;
    });
  };

  const renderMunicipalityTable = (data) => {
    const features = data.municipalities.features;
    const isDynamics = Boolean(data.dynamics);
    const head = document.querySelector("#map-municipality-head");
    const body = document.querySelector("#map-municipality-body");
    const headers = isDynamics
      ? ["Município", "Anterior", "Atual", "Variação", "Taxa", "Aberturas", "Baixas"]
      : [
        "Município",
        "Estabelecimentos",
        "Empresas",
        `População (${data.population_reference.reference_year || "sem referência"})`,
        "Estab./1 mil hab.",
        "Cobertura",
      ];
    const headerRow = document.createElement("tr");
    headers.forEach((value) => {
      const header = document.createElement("th");
      header.textContent = value;
      headerRow.append(header);
    });
    replaceChildren(head, [headerRow]);
    const rows = [...features]
      .sort((left, right) => left.properties.name.localeCompare(right.properties.name, "pt-BR"))
      .map((feature) => {
        const row = document.createElement("tr");
        const properties = feature.properties;
        const values = isDynamics
          ? [
            properties.name,
            number.format(properties.previous_establishments),
            number.format(properties.establishments),
            signedNumber(properties.stock_change),
            formattedPercentage(properties.change_percentage, { signed: true }),
            number.format(properties.openings),
            number.format(properties.closures),
          ]
          : [
            properties.name,
            number.format(properties.establishments),
            number.format(properties.companies),
            properties.population === null ? "—" : number.format(properties.population),
            properties.establishments_per_1000 === null
              ? "—"
              : decimalNumber.format(properties.establishments_per_1000),
            `${properties.coverage_percentage.toLocaleString("pt-BR")}%`,
          ];
        values.forEach((value, index) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          if (isDynamics && index === 3) {
            cell.classList.add(movementClass(properties.stock_change));
          }
          row.append(cell);
        });
        return row;
      });
    replaceChildren(body, rows);
  };

  const setDynamicsMetric = (name, value, formatter = number.format.bind(number)) => {
    const element = document.querySelector(`[data-dynamics-metric="${name}"]`);
    if (!element) return;
    element.textContent = formatter(value);
    if (name === "change" || name === "rate") {
      element.classList.remove("positive-value", "negative-value", "neutral-value");
      element.classList.add(movementClass(value));
    }
  };

  const competenceLabel = (value) => {
    const [year, month] = value.split("-");
    return `${month}/${year}`;
  };

  const renderModePresentation = (data) => {
    const dynamics = data.dynamics;
    const isDynamics = Boolean(dynamics);
    document.querySelector("#map-stock-indicators").hidden = isDynamics;
    document.querySelector("#map-dynamics-indicators").hidden = !isDynamics;
    document.querySelector("#map-dynamics-note").hidden = !isDynamics;
    document.querySelector("#map-stock-legend").hidden = isDynamics;
    document.querySelector("#map-dynamics-legend").hidden = !isDynamics;
    document.querySelector("#map-point-legend").hidden = isDynamics;
    document.querySelector("#map-population-indicators").hidden =
      isDynamics || !data.population_reference.available;
    document.querySelector("#map-population-note").hidden =
      isDynamics || !data.population_reference.available;
    document.querySelector("#map-mode-eyebrow").textContent = isDynamics
      ? "Comparação entre competências consecutivas"
      : "Municípios → agregados → estabelecimentos";
    document.querySelector("#map-title").textContent = isDynamics
      ? "Dinâmica territorial experimental"
      : "Distribuição espacial";
    document.querySelector("#municipality-ranking-eyebrow").textContent = isDynamics
      ? "Maiores movimentos absolutos"
      : data.selection.map_metric === "per_1000"
        ? "Densidade cadastral populacional"
        : "Concentração";
    document.querySelector("#cnae-ranking-eyebrow").textContent = isDynamics
      ? "Maiores movimentos absolutos"
      : "Atividade econômica";
    document.querySelector("#cnae-ranking-title").textContent = isDynamics
      ? "Variações por CNAE"
      : "CNAEs principais";
    document.querySelector("#map-filter-note").textContent = isDynamics
      ? "Os mesmos filtros são aplicados separadamente às duas competências. Período de abertura e métrica populacional ficam indisponíveis para não distorcer a comparação."
      : data.selection.map_metric === "per_1000"
        ? `O mapa e o ranking municipal mostram estabelecimentos ativos por mil habitantes da referência ${data.population_reference.reference_year}. Os demais indicadores preservam seus valores absolutos.`
        : "Os filtros atualizam o mapa, os indicadores, os rankings e a tabela municipal com o mesmo recorte. “Ativo” refere-se à situação na competência escolhida.";

    updateStockLegend(data);

    if (!dynamics) return;
    setDynamicsMetric("previous", dynamics.previous_establishments);
    setDynamicsMetric("current", dynamics.current_establishments);
    setDynamicsMetric("change", dynamics.stock_change, signedNumber);
    setDynamicsMetric(
      "rate",
      dynamics.change_percentage,
      (value) => formattedPercentage(value, { signed: true }),
    );
    setDynamicsMetric("openings", dynamics.openings);
    setDynamicsMetric("closures", dynamics.closures);
    document.querySelector("#map-dynamics-note").textContent =
      `Comparação ${competenceLabel(dynamics.from_competence)} → ${competenceLabel(dynamics.to_competence)}. ` +
      `Saldo de ciclo de vida: ${signedNumber(dynamics.lifecycle_balance)}. ` +
      `Outros efeitos cadastrais: ${signedNumber(dynamics.other_effects)}.`;
  };

  const renderPopulationPresentation = (data) => {
    const reference = data.population_reference;
    if (!reference.available) return;
    const values = {
      population: number.format(reference.population),
      establishments: decimalNumber.format(reference.establishments_per_1000),
      companies: decimalNumber.format(reference.companies_per_1000),
      coverage: `${reference.municipalities_with_population}/${reference.expected_municipalities}`,
    };
    for (const [name, value] of Object.entries(values)) {
      const element = document.querySelector(`[data-population-metric="${name}"]`);
      if (element) element.textContent = value;
    }
    document.querySelector("#map-population-note").textContent =
      `Competência cadastral ${competenceLabel(data.selection.competence)}; ` +
      `população residente do ${reference.source}.`;
  };

  const updateStockLegend = (data) => {
    const perThousand = data.selection.map_metric === "per_1000";
    const title = document.querySelector("#map-stock-legend-title");
    const note = document.querySelector("#map-stock-legend-note");
    const labels = {
      minimum: document.querySelector('[data-stock-scale="minimum"]'),
      low: document.querySelector('[data-stock-scale="low"]'),
      high: document.querySelector('[data-stock-scale="high"]'),
      maximum: document.querySelector('[data-stock-scale="maximum"]'),
    };
    if (!perThousand) {
      title.textContent = "Concentração municipal";
      note.textContent = "Verde claro indica menos estabelecimentos; verde escuro, maior concentração.";
      labels.minimum.textContent = "0";
      labels.low.textContent = "1 mil";
      labels.high.textContent = "10 mil";
      labels.maximum.textContent = "100 mil+";
      return;
    }
    const scale = Math.max(data.population_reference.scale_max || 0, 1);
    title.textContent = "Estabelecimentos por mil habitantes";
    note.textContent =
      `Verde escuro indica maior presença cadastral relativa à população residente de ${data.population_reference.reference_year}.`;
    labels.minimum.textContent = "0";
    labels.low.textContent = decimalNumber.format(scale / 3);
    labels.high.textContent = decimalNumber.format(scale * 2 / 3);
    labels.maximum.textContent = decimalNumber.format(scale);
  };

  const focusSelectedMunicipality = (data) => {
    if (!mapReady || !data.selection.municipality) return false;
    const feature = data.municipalities.features.find(
      (item) => item.properties.ibge_code === data.selection.municipality,
    );
    const bbox = feature ? feature.properties.bbox : null;
    if (!Array.isArray(bbox) || bbox.length !== 4) return false;
    map.fitBounds(bbox, { padding: 40, maxZoom: 11 });
    return true;
  };

  const applyBootstrap = (data) => {
    currentData = data;
    const indicators = data.indicators;
    setMetric("establishments", number.format(indicators.establishments));
    setMetric("companies", number.format(indicators.companies));
    setMetric("municipalities", number.format(indicators.municipalities));
    setMetric(
      "branches",
      `${number.format(indicators.branches.headquarters)} · ${number.format(indicators.branches.branches)}`,
    );
    setMetric(
      "tax",
      `${number.format(indicators.tax_profile.mei)} · ${number.format(indicators.tax_profile.simples)} · ${number.format(indicators.tax_profile.regular)}`,
    );
    setMetric(
      "coverage",
      `${indicators.geographic_coverage.percentage.toLocaleString("pt-BR")}%`,
    );
    renderPopulationPresentation(data);
    renderModePresentation(data);
    const isDynamics = Boolean(data.dynamics);
    const perThousand = data.selection.map_metric === "per_1000";
    replaceChildren(
      document.querySelector("#municipality-ranking"),
      rankingRows(
        data.rankings.municipalities,
        (item) => item.name,
        (item) => isDynamics
          ? item.stock_change
          : perThousand
            ? item.establishments_per_1000
            : item.establishments,
        isDynamics
          ? signedNumber
          : perThousand
            ? formattedPerThousand
            : number.format.bind(number),
        isDynamics,
      ),
    );
    replaceChildren(
      document.querySelector("#cnae-ranking"),
      rankingRows(
        data.rankings.cnaes,
        (item) => item.label,
        (item) => isDynamics ? item.stock_change : item.establishments,
        isDynamics ? signedNumber : number.format.bind(number),
        isDynamics,
      ),
    );
    renderMunicipalityTable(data);
    if (mapReady) {
      map.getSource("municipalities").setData(data.municipalities);
      applyMapMode(data);
      if (!focusSelectedMunicipality(data)) loadLocations();
    }
  };

  const updateAnalysis = async () => {
    const parameters = formParameters();
    setStatus("Atualizando o recorte cartográfico…");
    try {
      const data = await fetchJson(app.dataset.bootstrapUrl, parameters);
      detailsSelection = null;
      document.querySelector("#map-location-details").hidden = true;
      applyBootstrap(data);
      window.history.replaceState({}, "", `${window.location.pathname}?${parameters}`);
      if (!mapReady) setStatus("Indicadores e tabela atualizados.");
    } catch (error) {
      setStatus(error.message, true);
    }
  };

  const locationPopup = (feature) => {
    const wrapper = document.createElement("div");
    const heading = document.createElement("strong");
    const detail = document.createElement("p");
    const properties = feature.properties;
    heading.textContent = properties.name || (
      properties.kind === "postal_code" ? `CEP ${properties.postal_code}` : "Localização"
    );
    if (properties.kind === "municipality" && currentData.dynamics) {
      detail.textContent =
        `${number.format(properties.previous_establishments)} → ${number.format(properties.establishments)} estabelecimentos ativos ` +
        `(${signedNumber(properties.stock_change)}; ${formattedPercentage(properties.change_percentage, { signed: true })}).`;
      const lifecycle = document.createElement("p");
      lifecycle.textContent =
        `${number.format(properties.openings)} abertura(s) e ${number.format(properties.closures)} baixa(s) confirmada(s).`;
      wrapper.append(heading, detail, lifecycle);
      return wrapper;
    }
    detail.textContent = `${number.format(properties.total)} estabelecimento(s) de ${number.format(properties.companies)} empresa(s).`;
    wrapper.append(heading, detail);
    if (
      properties.kind === "municipality" &&
      properties.population !== null &&
      properties.population !== undefined
    ) {
      const populationContext = document.createElement("p");
      populationContext.textContent =
        `Presença relativa: ${decimalNumber.format(properties.establishments_per_1000)} ` +
        `estabelecimento(s) por mil habitantes; população de referência: ` +
        `${number.format(properties.population)} habitantes.`;
      wrapper.append(populationContext);
    }
    if (properties.kind === "location") {
      const companies = document.createElement("div");
      companies.dataset.popupCompanies = "";
      companies.className = "map-popup-more";
      companies.textContent = "Carregando empresas deste ponto…";
      wrapper.append(companies);
    }
    return wrapper;
  };

  const companyDisplayName = (item) => item.trade_name || item.legal_name || "Sem nome informado";

  const appendCompanyIdentity = (container, item) => {
    const link = document.createElement("a");
    link.href = item.company_url;
    link.textContent = companyDisplayName(item);
    container.append(link);
    if (item.trade_name && item.legal_name && item.trade_name !== item.legal_name) {
      const legalName = document.createElement("small");
      legalName.textContent = item.legal_name;
      container.append(legalName);
    }
  };

  const renderPopupCompanies = (payload, container) => {
    if (!container) return;
    const visibleItems = payload.items.slice(0, 5);
    const list = document.createElement("ul");
    list.className = "map-popup-company-list";
    visibleItems.forEach((item) => {
      const row = document.createElement("li");
      appendCompanyIdentity(row, item);
      list.append(row);
    });
    const children = [list];
    if (payload.pagination.total > visibleItems.length) {
      const remaining = document.createElement("p");
      remaining.className = "map-popup-more";
      remaining.textContent = `Mais ${number.format(payload.pagination.total - visibleItems.length)} estabelecimento(s) na lista completa abaixo.`;
      children.push(remaining);
    }
    replaceChildren(container, children);
  };

  const loadLocations = async () => {
    if (!mapReady) return;
    if (currentData.dynamics) {
      if (locationsRequest) locationsRequest.abort();
      map.getSource("locations").setData({ type: "FeatureCollection", features: [] });
      setStatus(
        `Comparando ${competenceLabel(currentData.dynamics.from_competence)} e ${competenceLabel(currentData.dynamics.to_competence)} por município.`,
      );
      return;
    }
    if (locationsRequest) locationsRequest.abort();
    if (map.getZoom() < 9) {
      map.getSource("locations").setData({ type: "FeatureCollection", features: [] });
      setStatus("Aproxime o mapa para revelar as concentrações por CEP.");
      return;
    }
    locationsRequest = new AbortController();
    const bounds = map.getBounds();
    const parameters = formParameters();
    parameters.set("west", bounds.getWest().toFixed(6));
    parameters.set("south", bounds.getSouth().toFixed(6));
    parameters.set("east", bounds.getEast().toFixed(6));
    parameters.set("north", bounds.getNorth().toFixed(6));
    parameters.set("zoom", map.getZoom().toFixed(2));
    try {
      const data = await fetchJson(
        app.dataset.locationsUrl,
        parameters,
        locationsRequest.signal,
      );
      map.getSource("locations").setData(data.locations);
      const message = data.aggregation_reason || (
        data.level === "location"
          ? "Exibindo localizações completas dentro da área visível."
          : "Aproxime o mapa para revelar mais detalhes."
      );
      setStatus(message);
    } catch (error) {
      if (error.name !== "AbortError") {
        setStatus(`${error.message} A última visualização válida foi preservada.`, true);
      }
    }
  };

  const renderDetails = (payload) => {
    const panel = document.querySelector("#map-location-details");
    const body = document.querySelector("#map-detail-body");
    const rows = payload.items.map((item) => {
      const row = document.createElement("tr");
      const companyCell = document.createElement("td");
      appendCompanyIdentity(companyCell, item);
      const values = [
        item.cnpj,
        item.branch_type,
        item.main_cnae_label || "Não informado",
        item.cnefe_level ? `${item.precision} · nível ${item.cnefe_level}` : item.precision,
      ];
      row.append(companyCell);
      values.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });
      return row;
    });
    replaceChildren(body, rows);
    const pagination = document.querySelector("#map-detail-pagination");
    const summary = document.createElement("span");
    summary.textContent = `Página ${payload.pagination.page} de ${payload.pagination.pages} · ${number.format(payload.pagination.total)} estabelecimento(s)`;
    const controls = document.createElement("span");
    controls.className = "pagination-controls";
    if (payload.pagination.has_previous) {
      controls.append(detailPageButton("Anterior", payload.pagination.page - 1));
    }
    if (payload.pagination.has_next) {
      controls.append(detailPageButton("Próxima", payload.pagination.page + 1));
    }
    replaceChildren(pagination, [summary, controls]);
    panel.hidden = false;
  };

  const detailPageButton = (label, page) => {
    const button = document.createElement("button");
    button.className = "text-button";
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", () => loadDetails(detailsSelection, page));
    return button;
  };

  const loadDetails = async (selection, page = 1, popupContainer = null) => {
    detailsSelection = selection;
    const { coordinate, locationMethod, cnefeLevel } = selection;
    const parameters = formParameters();
    parameters.set("longitude", coordinate[0].toFixed(6));
    parameters.set("latitude", coordinate[1].toFixed(6));
    parameters.set("location_method", locationMethod);
    if (cnefeLevel) parameters.set("cnefe_level", cnefeLevel);
    parameters.set("page", page);
    setStatus("Carregando estabelecimentos do local…");
    try {
      const payload = await fetchJson(app.dataset.detailsUrl, parameters);
      renderDetails(payload);
      renderPopupCompanies(payload, popupContainer);
      setStatus("Detalhes do local carregados.");
    } catch (error) {
      if (popupContainer) popupContainer.textContent = error.message;
      setStatus(error.message, true);
    }
  };

  const initializeMap = () => {
    const token = app.dataset.mapboxToken;
    if (!token) return;
    if (!window.mapboxgl) {
      setStatus("A biblioteca do mapa não pôde ser carregada. Use a tabela municipal.", true);
      return;
    }
    window.mapboxgl.accessToken = token;
    try {
      map = new window.mapboxgl.Map({
        container: "establishment-map",
        style: app.dataset.mapboxStyle,
        bounds: [[-51.25, -21.0], [-46.3, -17.0]],
        fitBoundsOptions: { padding: 36 },
        cooperativeGestures: true,
      });
    } catch (error) {
      setStatus("O mapa não pôde ser inicializado. Use a tabela municipal.", true);
      return;
    }
    map.addControl(new window.mapboxgl.NavigationControl(), "top-right");
    map.on("load", () => {
      map.addSource("municipalities", {
        type: "geojson",
        data: currentData.municipalities,
        promoteId: "ibge_code",
      });
      map.addLayer({
        id: "municipality-fill",
        type: "fill",
        source: "municipalities",
        paint: {
          "fill-color": [
            "interpolate", ["linear"], ["get", "establishments"],
            0, "#edf4ef",
            1000, "#add6bc",
            10000, "#4e9d73",
            100000, "#0b5b3f",
          ],
          "fill-opacity": [
            "case", ["boolean", ["feature-state", "hover"], false], 0.82, 0.58,
          ],
        },
      });
      map.addLayer({
        id: "municipality-outline",
        type: "line",
        source: "municipalities",
        paint: { "line-color": "#0b3d2e", "line-width": 1.2 },
      });
      map.addSource("locations", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
        generateId: true,
      });
      map.addLayer({
        id: "location-circles",
        type: "circle",
        source: "locations",
        paint: {
          "circle-color": [
            "match", ["get", "location_method"],
            "ADDRESS", "#0b6b47",
            "POSTAL_CODE", "#d89818",
            "#28547a",
          ],
          "circle-radius": [
            "interpolate", ["linear"], ["sqrt", ["get", "total"]],
            1, 5,
            20, 20,
            100, 34,
          ],
          "circle-opacity": 0.82,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
        },
      });
      mapReady = true;
      applyMapMode(currentData);
      if (!focusSelectedMunicipality(currentData)) loadLocations();
    });

    let hoveredMunicipality = null;
    map.on("mousemove", "municipality-fill", (event) => {
      if (!event.features.length) return;
      if (hoveredMunicipality !== null) {
        map.setFeatureState(
          { source: "municipalities", id: hoveredMunicipality },
          { hover: false },
        );
      }
      hoveredMunicipality = event.features[0].id;
      map.setFeatureState(
        { source: "municipalities", id: hoveredMunicipality },
        { hover: true },
      );
    });
    map.on("mouseleave", "municipality-fill", () => {
      if (hoveredMunicipality !== null) {
        map.setFeatureState(
          { source: "municipalities", id: hoveredMunicipality },
          { hover: false },
        );
      }
      hoveredMunicipality = null;
    });
    map.on("click", "municipality-fill", (event) => {
      if (!event.features.length) return;
      if (!currentData.dynamics && map.getZoom() >= 9) return;
      new window.mapboxgl.Popup()
        .setLngLat(event.lngLat)
        .setDOMContent(locationPopup({
          properties: {
            ...event.features[0].properties,
            total: event.features[0].properties.establishments,
            kind: "municipality",
          },
        }))
        .addTo(map);
      if (!currentData.dynamics) map.easeTo({ center: event.lngLat, zoom: 9 });
    });
    map.on("click", "location-circles", (event) => {
      if (!event.features.length) return;
      const feature = event.features[0];
      const coordinate = feature.geometry.coordinates.slice();
      const detailCoordinate = [
        Number(feature.properties.detail_longitude),
        Number(feature.properties.detail_latitude),
      ];
      const popupContent = locationPopup(feature);
      new window.mapboxgl.Popup()
        .setLngLat(coordinate)
        .setDOMContent(popupContent)
        .addTo(map);
      if (feature.properties.kind === "location") {
        loadDetails({
          coordinate: detailCoordinate,
          locationMethod: feature.properties.location_method,
          cnefeLevel: feature.properties.cnefe_level,
        }, 1, popupContent.querySelector("[data-popup-companies]"));
      } else {
        map.easeTo({ center: coordinate, zoom: Math.min(map.getZoom() + 2, 14) });
      }
    });
    map.on("mouseenter", "location-circles", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "location-circles", () => {
      map.getCanvas().style.cursor = "";
    });
    map.on("moveend", loadLocations);
    map.on("error", (event) => {
      if (!map.loaded()) {
        setStatus(
          "A renderização Mapbox falhou. Indicadores, rankings e tabela continuam disponíveis.",
          true,
        );
      } else if (event.error) {
        setStatus("Uma camada do mapa falhou; a última visualização válida foi preservada.", true);
      }
    });
  };

  const stockFillExpression = [
    "interpolate", ["linear"], ["get", "establishments"],
    0, "#edf4ef",
    1000, "#add6bc",
    10000, "#4e9d73",
    100000, "#0b5b3f",
  ];

  const perThousandFillExpression = (scale) => [
    "interpolate", ["linear"], ["get", "establishments_per_1000"],
    0, "#edf4ef",
    scale / 3, "#add6bc",
    scale * 2 / 3, "#4e9d73",
    scale, "#0b5b3f",
  ];

  const dynamicsFillExpression = (scale) => [
    "interpolate", ["linear"], ["get", "stock_change"],
    -scale, "#a63d40",
    -scale * 0.25, "#efb7ad",
    0, "#f2efe7",
    scale * 0.25, "#a9d7bc",
    scale, "#0b6b47",
  ];

  const applyMapMode = (data) => {
    if (!mapReady) return;
    const dynamics = data.dynamics;
    const perThousand = data.selection.map_metric === "per_1000";
    const populationScale = Math.max(data.population_reference.scale_max || 0, 1);
    map.setPaintProperty(
      "municipality-fill",
      "fill-color",
      dynamics
        ? dynamicsFillExpression(Math.max(dynamics.scale_max, 1))
        : perThousand
          ? perThousandFillExpression(populationScale)
          : stockFillExpression,
    );
    map.setLayoutProperty(
      "location-circles",
      "visibility",
      dynamics ? "none" : "visible",
    );
    if (!dynamics) return;
    map.getSource("locations").setData({ type: "FeatureCollection", features: [] });
    setStatus(
      `Comparando ${competenceLabel(dynamics.from_competence)} e ${competenceLabel(dynamics.to_competence)} por município.`,
    );
    document.querySelector('[data-dynamics-scale="negative"]').textContent = signedNumber(
      -dynamics.scale_max,
    );
    document.querySelector('[data-dynamics-scale="positive"]').textContent = signedNumber(
      dynamics.scale_max,
    );
  };

  const syncModeControls = () => {
    const isDynamics = document.querySelector("#map-analysis-mode").value === "dynamics";
    const openingPeriod = form.elements.namedItem("opening_period");
    const mapMetric = form.elements.namedItem("map_metric");
    openingPeriod.disabled = isDynamics;
    mapMetric.disabled = isDynamics;
    if (isDynamics) {
      openingPeriod.value = "";
      mapMetric.value = "absolute";
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    updateAnalysis();
  });
  document.querySelector("#map-analysis-mode").addEventListener("change", syncModeControls);
  document.querySelector("#map-clear-filters").addEventListener("click", () => {
    for (const field of form.elements) {
      if (!field.name) continue;
      if (field.name === "competence") {
        field.value = currentData.projection ? initialData.selection.competence : "";
      } else if (field.name === "analysis_mode") {
        field.value = "stock";
      } else if (field.name === "map_metric") {
        field.value = "absolute";
      } else {
        field.value = "";
      }
    }
    syncModeControls();
    updateAnalysis();
  });
  document.querySelector("#map-close-details").addEventListener("click", () => {
    document.querySelector("#map-location-details").hidden = true;
  });

  syncModeControls();
  if (initialData) applyBootstrap(initialData);
  initializeMap();
})();
