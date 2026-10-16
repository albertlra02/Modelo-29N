/* Calculadora de mayorías: suma en el navegador los escaños de los partidos elegidos en cada
   simulación del escenario. La coalición elegida queda en la dirección (#PP+VOX) para compartirla. */
"use strict";

(() => {
  const { partidos, sim, atajos, tokens } = JSON.parse(document.getElementById("datos-calculadora").textContent);
  const claves = partidos.map((p) => p.clave);
  const n = sim[claves[0]].length;
  const raiz = document.querySelector("[data-calculadora]");
  const cajaAtajos = raiz.querySelector("[data-atajos]");
  const cajaPartidos = raiz.querySelector("[data-partidos]");
  const hist = document.getElementById("f-histograma");
  const MAYORIA = 176;

  // Sumar + Podemos <-> Frente Amplio: la coalición del enlace sirve con las dos opciones de candidaturas
  const traduccion = { SUMAR: ["FRENTE_AMPLIO"], PODEMOS: ["FRENTE_AMPLIO"], FRENTE_AMPLIO: ["SUMAR", "PODEMOS"] };
  const desdeHash = decodeURIComponent(location.hash.slice(1)).split("+").filter(Boolean)
    .flatMap((x) => (claves.includes(x) ? [x] : traduccion[x] || []));
  let elegidos = new Set(desdeHash.length ? desdeHash.filter((x) => claves.includes(x)) : ["PP", "VOX"].filter((x) => claves.includes(x)));

  const pct = (x) => `${Math.round(100 * x)} %`;
  const nombre = (c) => partidos.find((p) => p.clave === c).nombre;
  const lista = (ns) => (ns.length === 1 ? ns[0] : `${ns.slice(0, -1).join(", ")} y ${ns[ns.length - 1]}`);
  function cuantil(ordenado, q) {          // interpolación lineal, como pandas
    const pos = (ordenado.length - 1) * q;
    const lo = Math.floor(pos), hi = Math.ceil(pos);
    return ordenado[lo] + (ordenado[hi] - ordenado[lo]) * (pos - lo);
  }

  // ------------------------------------------------------------ controles

  const botonesAtajo = Object.entries(atajos).map(([texto, miembros]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ficha ficha--atajo";
    b.textContent = texto;
    b.addEventListener("click", () => { elegidos = new Set(miembros); actualizar(); });
    b._miembros = miembros;
    cajaAtajos.append(b);
    return b;
  });

  const botonesPartido = partidos.map((p) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ficha";
    b.style.setProperty("--c", p.color);
    b.dataset.clave = p.clave;
    const i = document.createElement("i");
    const s = document.createElement("small");
    s.textContent = `(${p.mediana})`;
    b.append(i, p.nombre, s);
    b.addEventListener("click", () => {
      if (elegidos.has(p.clave)) elegidos.delete(p.clave); else elegidos.add(p.clave);
      actualizar();
    });
    cajaPartidos.append(b);
    return b;
  });

  // ------------------------------------------------------------ resultado

  function histograma(suma) {
    const frec = new Map();
    for (const v of suma) frec.set(v, (frec.get(v) || 0) + 1);
    const x = [...frec.keys()].sort((a, b) => a - b);
    const traza = (filtro, color, nombreTraza) => {
      const xs = x.filter(filtro);
      return {
        type: "bar", x: xs, y: xs.map((v) => (100 * frec.get(v)) / n), name: nombreTraza,
        marker: { color, line: { width: 0 } },
        hovertemplate: "Coalición: %{x} escaños<br>%{y:.1f} % de las simulaciones<extra></extra>",
      };
    };
    const ejes = { gridcolor: tokens.regla, zeroline: false, linecolor: tokens.regla, tickfont: { color: tokens.tinta3 } };
    const layout = {
      height: 320, paper_bgcolor: tokens.panel, plot_bgcolor: tokens.panel, separators: ",.",
      font: { family: tokens.fuente, color: tokens.tinta2, size: 13 },
      margin: { l: 10, r: 20, t: 40, b: 10 }, bargap: 0.08, barcornerradius: 4, showlegend: true,
      legend: { orientation: "h", y: 1.12, x: 0, font: { color: tokens.tinta2 } },
      hoverlabel: { bgcolor: tokens.panel, bordercolor: tokens.regla, font: { family: tokens.fuente, color: tokens.tinta, size: 13 } },
      xaxis: { ...ejes, title: { text: "Escaños", font: { color: tokens.tinta3 } }, automargin: true },
      yaxis: { ...ejes, title: { text: "% de simulaciones", font: { color: tokens.tinta3 } }, automargin: true },
      shapes: [{ type: "line", x0: 175.5, x1: 175.5, yref: "paper", y0: 0, y1: 1, line: { color: tokens.tinta, width: 1.5, dash: "dot" } }],
      annotations: [{ x: 175.5, y: 0.98, yref: "paper", text: "176", showarrow: false, xanchor: "right", yanchor: "top",
        xshift: -6, font: { color: tokens.tinta, size: 12, family: tokens.cifras } }],
    };
    const data = [traza((v) => v < MAYORIA, tokens.gris, "Por debajo de 176"), traza((v) => v >= MAYORIA, tokens.bronce, "176 o más")];
    Plotly.react(hist, data, layout, window.Modelo.CONFIG);
  }

  function actualizar() {
    botonesPartido.forEach((b) => b.setAttribute("aria-pressed", String(elegidos.has(b.dataset.clave))));
    botonesAtajo.forEach((b) => {
      const igual = b._miembros.length === elegidos.size && b._miembros.every((x) => elegidos.has(x));
      b.setAttribute("aria-pressed", String(igual));
    });
    const orden = claves.filter((c) => elegidos.has(c));
    history.replaceState(null, "", orden.length ? `#${orden.join("+")}` : location.pathname + location.search);

    const cifra = raiz.querySelector("[data-cifra]");
    const texto = raiz.querySelector("[data-texto]");
    const filas = raiz.querySelector("[data-filas]");
    if (!orden.length) {
      cifra.textContent = "–";
      texto.textContent = "Elige al menos un partido.";
      filas.replaceChildren();
      Plotly.purge(hist);
      return;
    }
    const suma = new Int32Array(n);
    for (const c of orden) { const s = sim[c]; for (let i = 0; i < n; i++) suma[i] += s[i]; }
    let llegan = 0;
    for (const v of suma) if (v >= MAYORIA) llegan++;
    const ordenado = Array.from(suma).sort((a, b) => a - b);
    const mediana = cuantil(ordenado, 0.5);

    cifra.textContent = pct(llegan / n);
    texto.textContent = `de las simulaciones dan 176 escaños o más a ${lista(orden.map(nombre))}`;
    const datos = [
      ["Escaños, mediana", Math.round(mediana)],
      ["80 % de las simulaciones", `${Math.round(cuantil(ordenado, 0.1))}–${Math.round(cuantil(ordenado, 0.9))}`],
      ["Les faltan para 176 (mediana)", Math.max(MAYORIA - Math.round(mediana), 0)],
    ];
    filas.replaceChildren(...datos.map(([a, b]) => {
      const d = document.createElement("div");
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = a;
      dd.textContent = b;
      d.append(dt, dd);
      return d;
    }));
    histograma(suma);
  }

  actualizar();
})();
