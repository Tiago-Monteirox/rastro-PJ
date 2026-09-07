(() => {
  "use strict";

  const app = document.querySelector("#analytics-map-app");
  if (!app) return;

  const form = document.querySelector("#map-filter-form");
  const status = document.querySelector("#map-status");
  const initialElement = document.querySelector("#map-initial-data");
  const number = new Intl.NumberFormat("pt-BR");
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

  const rankingRows = (items, label, value) =>
    items.map((item) => {
      const row = document.createElement("li");
      const name = document.createElement("span");
      const total = document.createElement("strong");
      name.textContent = label(item);
      total.textContent = number.format(value(item));
      row.append(name, total);
      return row;
    });

  const renderMunicipalityTable = (features) => {
    const body = document.querySelector("#map-municipality-body");
    const rows = [...features]
      .sort((left, right) => left.properties.name.localeCompare(right.properties.name, "pt-BR"))
      .map((feature) => {
        const row = document.createElement("tr");
        const values = [
          feature.properties.name,
          number.format(feature.properties.establishments),
          number.format(feature.properties.companies),
          `${feature.properties.coverage_percentage.toLocaleString("pt-BR")}%`,
        ];
        values.forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.append(cell);
        });
        return row;
      });
    replaceChildren(body, rows);
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
    replaceChildren(
      document.querySelector("#municipality-ranking"),
      rankingRows(
        data.rankings.municipalities,
        (item) => item.name,
        (item) => item.establishments,
      ),
    );
    replaceChildren(
      document.querySelector("#cnae-ranking"),
      rankingRows(
        data.rankings.cnaes,
        (item) => item.code,
        (item) => item.establishments,
      ),
    );
    renderMunicipalityTable(data.municipalities.features);
    if (mapReady) {
      map.getSource("municipalities").setData(data.municipalities);
      loadLocations();
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
    detail.textContent = `${number.format(properties.total)} estabelecimento(s) de ${number.format(properties.companies)} empresa(s).`;
    wrapper.append(heading, detail);
    return wrapper;
  };

  const loadLocations = async () => {
    if (!mapReady) return;
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
      const link = document.createElement("a");
      link.href = item.company_url;
      link.textContent = item.trade_name || item.legal_name || "Sem nome informado";
      companyCell.append(link);
      const values = [
        item.cnpj,
        item.branch_type,
        item.main_cnae_code || "Não informado",
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
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const detailPageButton = (label, page) => {
    const button = document.createElement("button");
    button.className = "text-button";
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", () => loadDetails(detailsSelection, page));
    return button;
  };

  const loadDetails = async (selection, page = 1) => {
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
      renderDetails(await fetchJson(app.dataset.detailsUrl, parameters));
      setStatus("Detalhes do local carregados.");
    } catch (error) {
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
      loadLocations();
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
      if (map.getZoom() >= 9 || !event.features.length) return;
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
      map.easeTo({ center: event.lngLat, zoom: 9 });
    });
    map.on("click", "location-circles", (event) => {
      if (!event.features.length) return;
      const feature = event.features[0];
      const coordinate = feature.geometry.coordinates.slice();
      new window.mapboxgl.Popup()
        .setLngLat(coordinate)
        .setDOMContent(locationPopup(feature))
        .addTo(map);
      if (feature.properties.kind === "location") {
        loadDetails({
          coordinate,
          locationMethod: feature.properties.location_method,
          cnefeLevel: feature.properties.cnefe_level,
        });
      } else {
        map.easeTo({ center: coordinate, zoom: Math.min(map.getZoom() + 2, 14) });
      }
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

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    updateAnalysis();
  });
  document.querySelector("#map-clear-filters").addEventListener("click", () => {
    for (const field of form.elements) {
      if (!field.name) continue;
      if (field.name === "competence") {
        field.value = currentData.projection ? initialData.selection.competence : "";
      } else {
        field.value = "";
      }
    }
    updateAnalysis();
  });
  document.querySelector("#map-close-details").addEventListener("click", () => {
    document.querySelector("#map-location-details").hidden = true;
  });

  if (initialData) applyBootstrap(initialData);
  initializeMap();
})();
