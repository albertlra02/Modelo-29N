/* Comportamiento común de la web: gráficas, panel de escenario, cálculos pendientes, tablas y
   los controles de las páginas de provincias y encuestas. Sin dependencias salvo plotly.js. */
"use strict";

(() => {
  const CONFIG = { displayModeBar: false, responsive: true, locale: "es" };
  const ASPECTO_MAPA = 1.5;      // ancho / alto del encuadre de España en interfaz/graficos.py (Mercator)

  Plotly.register({
    moduleType: "locale", name: "es", dictionary: {},
    format: {
      days: ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"],
      shortDays: ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"],
      months: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
        "noviembre", "diciembre"],
      shortMonths: ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
      date: "%d/%m/%Y", decimal: ",", thousands: ".",
    },
  });

  /** Pinta una figura (objeto o JSON de Plotly) en un elemento. */
  function pintar(div, fig) {
    const f = typeof fig === "string" ? JSON.parse(fig) : fig;
    // Mapas: la proyección conserva la forma, así que en pantallas estrechas sobra alto; se ajusta al ancho
    if (f.layout && f.layout.geo && f.layout.height && div.clientWidth) {
      f.layout.height = Math.min(f.layout.height, Math.round(div.clientWidth / ASPECTO_MAPA) + 8);
    }
    div.style.minHeight = (f.layout && f.layout.height ? f.layout.height : 300) + "px";
    return Plotly.newPlot(div, { data: f.data, layout: f.layout, frames: f.frames || [], config: CONFIG });
  }

  /** Pide una figura a la API y la pinta; devuelve el resto de la respuesta. */
  async function cargar(div, url) {
    div.classList.add("cargando");
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error(r.statusText);
      const j = await r.json();
      await pintar(div, j.fig);
      return j;
    } finally {
      div.classList.remove("cargando");
    }
  }

  /** Parámetros del escenario actual (los de la URL) con otros añadidos. */
  function conEscenario(extra) {
    const q = new URLSearchParams(location.search);
    for (const [k, v] of Object.entries(extra)) q.set(k, v);
    return q.toString();
  }

  function pulsado(grupo, boton) {
    grupo.forEach((b) => b.setAttribute("aria-pressed", String(b === boton)));
  }

  window.Modelo = { pintar, cargar, conEscenario, CONFIG };

  // ------------------------------------------------------------ gráficas incrustadas

  document.querySelectorAll("[data-fig]").forEach((div) => {
    const datos = document.getElementById(div.dataset.fig);
    if (datos) div.pintado = pintar(div, datos.textContent);
  });

  // ------------------------------------------------------------ panel de escenario

  const panel = document.getElementById("panel-escenario");
  if (panel) {
    const form = panel.querySelector("form");
    const defectos = JSON.parse(form.dataset.defectos);
    document.querySelectorAll("[data-abrir-escenario]").forEach((b) => b.addEventListener("click", () => panel.showModal()));
    panel.querySelector("[data-cerrar]").addEventListener("click", () => panel.close());
    panel.addEventListener("click", (e) => { if (e.target === panel) panel.close(); });   // clic fuera del cajón

    const fecha = form.querySelector("#f-fecha");
    const iso = JSON.parse(fecha.dataset.iso);
    const textos = JSON.parse(fecha.dataset.textos);
    fecha.addEventListener("input", () => {
      form.querySelector("#f-fecha-texto").textContent = textos[fecha.value];
      form.elements.fecha.value = iso[fecha.value];
    });

    const part = form.querySelector("#f-part");
    const reparto = form.querySelector("#f-reparto");
    const detalle = form.querySelector("#f-reparto-detalle");
    const actualizarReparto = () => {
      const base = part.value === part.dataset.base;
      reparto.disabled = base;
      detalle.textContent = `De cada 100 votos extra: ${reparto.selectedOptions[0].dataset.detalle}.`
        + (base ? ` No influye con una participación del ${part.dataset.base} %.` : "");
    };
    part.addEventListener("input", () => {
      form.querySelector("#f-part-texto").textContent = `${part.value} %`;
      actualizarReparto();
    });
    reparto.addEventListener("change", actualizarReparto);

    // deslizadores de las palancas: cifra al lado, con signo en la movilización
    form.querySelectorAll("input[type=range][data-salida]").forEach((r) => {
      const salida = document.getElementById(r.dataset.salida);
      r.addEventListener("input", () => {
        const v = Number(r.value);
        salida.textContent = `${"signo" in r.dataset && v > 0 ? "+" : ""}${v} %`;
      });
    });

    // URL limpia: sólo lo que difiere del escenario por defecto
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = new URLSearchParams();
      for (const [k, v] of new FormData(form)) {
        if (String(defectos[k]) !== String(v)) q.set(k, v);
      }
      const s = q.toString();
      location.href = form.getAttribute("action") + (s ? "?" + s : "");
    });
  }

  // ------------------------------------------------------------ escenarios pendientes de calcular

  document.querySelectorAll("[data-calcular]").forEach((caja) => {
    const total = Number(caja.dataset.total);
    let pendientes = Number(caja.dataset.pendientes);
    const barra = caja.querySelector(".progreso");
    const estado = caja.querySelector("[data-estado]");
    const boton = caja.querySelector("[data-empezar]");

    async function calcular() {
      if (boton) boton.hidden = true;
      caja.classList.add("calculando");
      while (pendientes > 0) {
        let r;
        try {
          r = await fetch("/api/calcular?" + conEscenario({ tarea: caja.dataset.calcular }), { method: "POST" });
        } catch {
          r = null;
        }
        if (!r || !r.ok) {
          caja.classList.remove("calculando");
          estado.textContent = "No se ha podido calcular. Revisa la terminal donde corre la web.";
          if (boton) boton.hidden = false;
          return;
        }
        const j = await r.json();
        pendientes = j.pendientes;
        estado.textContent = j.texto;
        barra.firstElementChild.style.width = `${(100 * (total - pendientes)) / total}%`;
        barra.setAttribute("aria-valuenow", String(total - pendientes));
      }
      location.reload();
    }
    if (caja.dataset.auto === "1") calcular();
    else boton.addEventListener("click", calcular);
  });

  // ------------------------------------------------------------ tablas ordenables y filtro

  document.querySelectorAll("table[data-ordenable]").forEach((tabla) => {
    const cabeceras = [...tabla.tHead.rows[0].cells];
    cabeceras.forEach((th, col) => {
      if (!th.dataset.orden) return;
      th.tabIndex = 0;
      const ordenar = () => {
        // primer clic: textos de la A a la Z y cifras de mayor a menor; los siguientes alternan
        const num = th.dataset.orden === "num";
        const actual = th.getAttribute("aria-sort");
        const asc = actual ? actual === "descending" : !num;
        cabeceras.forEach((c) => c.removeAttribute("aria-sort"));
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        const valor = (fila) => {
          const celda = fila.cells[col];
          const v = celda.dataset.valor ?? celda.textContent.trim();
          return num ? Number(v) : v;
        };
        const filas = [...tabla.tBodies[0].rows];
        filas.sort((a, b) => {
          const x = valor(a), y = valor(b);
          const c = num ? x - y : String(x).localeCompare(String(y), "es");
          return asc ? c : -c;
        });
        tabla.tBodies[0].append(...filas);
      };
      th.addEventListener("click", ordenar);
      th.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ordenar(); } });
    });
  });

  const filtro = document.querySelector("[data-filtro-ccaa]");
  if (filtro) {
    const filas = document.querySelectorAll("tr[data-ccaa]");
    filtro.addEventListener("change", () => {
      filas.forEach((f) => { f.hidden = Boolean(filtro.value) && f.dataset.ccaa !== filtro.value; });
    });
  }

  // ------------------------------------------------------------ provincias y Senado: modos del mapa

  const mapa = document.querySelector("[data-mapa]");
  if (mapa) {
    const div = mapa.querySelector("#f-mapa");
    const api = mapa.dataset.api || "/api/mapa";
    const modos = [...mapa.querySelectorAll("[data-modo]")];
    const filaPartidos = mapa.querySelector("[data-partidos-mapa]");
    const partidos = filaPartidos ? [...filaPartidos.querySelectorAll("[data-partido]")] : [];
    const leyenda = mapa.querySelector("[data-leyenda-mapa]");
    const nota = mapa.querySelector("[data-nota-mapa]");
    let modo = "ganador";
    let partido = partidos.length ? partidos[0].dataset.partido : "";

    // ---- detalle de una provincia (sólo en /provincias): clic en el mapa o en la tabla
    const hueco = mapa.querySelector("[data-detalle-provincia]");
    const apiDetalle = mapa.dataset.detalleApi;
    let elegida = null;

    /** Remarca la provincia elegida con un trazo oscuro (una capa más, encima del resto). */
    function resaltar() {
      const i = div.data.findIndex((t) => t.meta === "realce");
      if (i >= 0) Plotly.deleteTraces(div, i);
      if (!elegida) return;
      const origen = div.data.find((t) => t.type === "choropleth" && t.locations.includes(elegida));
      if (!origen) return;
      const texto = origen.customdata[origen.locations.indexOf(elegida)];
      Plotly.addTraces(div, {
        type: "choropleth", meta: "realce", geojson: origen.geojson, featureidkey: "id", locations: [elegida],
        z: [0], colorscale: [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale: false,
        marker: { line: { color: "#15202B", width: 2.5 } },
        customdata: [texto], hovertemplate: "%{customdata}<extra></extra>",
      });
    }

    async function abrir(prov, desdeTabla) {
      elegida = prov;
      history.replaceState(null, "", "#" + encodeURIComponent(prov));   // enlace directo a la provincia
      resaltar();
      hueco.hidden = false;
      hueco.classList.add("cargando");
      try {
        const r = await fetch(apiDetalle + "?" + conEscenario({ nombre: prov }));
        if (!r.ok) throw new Error(r.statusText);
        const j = await r.json();
        if (elegida !== prov) return;          // ya se ha pulsado otra
        hueco.innerHTML = j.html;
      } catch {
        hueco.textContent = "No se ha podido cargar el detalle de la provincia.";
      } finally {
        hueco.classList.remove("cargando");
      }
      hueco.scrollIntoView({ block: desdeTabla ? "start" : "nearest" });
    }

    function cerrar() {
      elegida = null;
      history.replaceState(null, "", location.pathname + location.search);
      hueco.hidden = true;
      hueco.replaceChildren();
      resaltar();
    }

    /** newPlot quita los manejadores de eventos: hay que engancharlos tras cada pintado. */
    function enganchar() {
      if (!apiDetalle) return;
      div.on("plotly_click", (ev) => {
        const pt = ev.points && ev.points[0];
        const prov = pt && (pt.location || pt.text);
        if (prov && prov !== "Canarias") abrir(prov, false);
      });
      resaltar();
    }

    if (apiDetalle) {
      Promise.resolve(div.pintado).then(() => {
        enganchar();
        const ancla = decodeURIComponent(location.hash.slice(1));
        if (ancla && document.querySelector(`[data-provincia="${CSS.escape(ancla)}"]`)) abrir(ancla, true);
      });
      hueco.addEventListener("click", (e) => { if (e.target.closest("[data-cerrar-provincia]")) cerrar(); });
      document.querySelectorAll("[data-provincia]").forEach((b) => b.addEventListener("click", () => {
        abrir(b.dataset.provincia, true);
      }));
    }

    async function actualizar() {
      const j = await cargar(div, api + "?" + conEscenario({ modo, partido }));
      enganchar();
      leyenda.replaceChildren(...j.leyenda.map((l) => {
        const d = document.createElement("div");
        const i = document.createElement("i");
        i.style.background = l.color;
        const b = document.createElement("b");
        b.textContent = l.n;
        d.append(i, `${l.nombre} `, b, l.n === 1 ? " provincia" : " provincias");
        return d;
      }));
      nota.textContent = j.nota;
    }
    modos.forEach((b) => b.addEventListener("click", () => {
      modo = b.dataset.modo;
      pulsado(modos, b);
      if (filaPartidos) filaPartidos.hidden = modo !== "partido";
      actualizar();
    }));
    partidos.forEach((b) => b.addEventListener("click", () => {
      partido = b.dataset.partido;
      pulsado(partidos, b);
      actualizar();
    }));
  }

  // ------------------------------------------------------------ encuestas: partidos, desde y casas

  const enc = document.querySelector("[data-encuestas]");
  if (enc) {
    const div = enc.querySelector("#f-serie");
    const fichas = [...enc.querySelectorAll("[data-enc-partido]")];
    const desdes = [...enc.querySelectorAll("[data-desde]")];
    let desde = desdes.find((b) => b.getAttribute("aria-pressed") === "true").dataset.desde;
    const actualizar = () => {
      const elegidos = fichas.filter((b) => b.getAttribute("aria-pressed") === "true").map((b) => b.dataset.encPartido);
      if (elegidos.length) cargar(div, "/api/encuestas?" + conEscenario({ partidos: elegidos.join(","), desde }));
    };
    fichas.forEach((b) => b.addEventListener("click", () => {
      const activo = b.getAttribute("aria-pressed") === "true";
      if (activo && fichas.filter((x) => x.getAttribute("aria-pressed") === "true").length === 1) return;  // al menos uno
      b.setAttribute("aria-pressed", String(!activo));
      actualizar();
    }));
    desdes.forEach((b) => b.addEventListener("click", () => {
      desde = b.dataset.desde;
      pulsado(desdes, b);
      actualizar();
    }));
  }

  const casas = document.querySelector("[data-casas]");
  if (casas) {
    const sel = casas.querySelector("[data-casa-partido]");
    sel.addEventListener("change", () => cargar(casas.querySelector("#f-casas"), "/api/casas?" + conEscenario({ partido: sel.value })));
  }
})();
