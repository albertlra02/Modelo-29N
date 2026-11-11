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

/* Investidura: con las posturas elegidas (sí, abstención, no) se cuentan en cada simulación los síes y los noes.
   Primera votación: 176 síes. Segunda: más síes que noes. */
(() => {
  const raiz = document.querySelector("[data-investidura]");
  if (!raiz) return;
  const { partidos, sim } = JSON.parse(document.getElementById("datos-calculadora").textContent);
  const claves = partidos.map((p) => p.clave);
  const n = sim[claves[0]].length;
  const MAYORIA = 176;
  const CANDIDATOS = { PP: "Feijóo", PSOE: "Sánchez" };
  // Posturas por defecto (ver la nota de la página). Lo que no aparece, abstención.
  const DEFECTO = {
    PP: { PP: "si", VOX: "si", UPN: "si", CC: "si", SALF: "no", PSOE: "no", SUMAR: "no", FRENTE_AMPLIO: "no",
      PODEMOS: "no", ERC: "no", JUNTS: "no", BILDU: "no", PNV: "no", BNG: "no", ADELANTE: "no" },
    PSOE: { PSOE: "si", SUMAR: "si", FRENTE_AMPLIO: "si", PODEMOS: "si", ERC: "si", BILDU: "si", PNV: "si",
      BNG: "si", CC: "si", ADELANTE: "si", JUNTS: "no", PP: "no", VOX: "no", UPN: "no", SALF: "no" },
  };
  const RECHAZAN_A_VOX = ["PSOE", "SUMAR", "FRENTE_AMPLIO", "PODEMOS", "ERC", "JUNTS", "BILDU", "PNV", "BNG", "ADELANTE"];
  const TEXTOS = { si: "Sí", abs: "Abstención", no: "No" };
  let posturas;
  const veto = raiz.querySelector("[data-inv-veto]");

  function porDefecto() {
    posturas = {};
    for (const c of Object.keys(CANDIDATOS)) {
      posturas[c] = Object.fromEntries(claves.map((x) => [x, DEFECTO[c][x] || "abs"]));
    }
  }

  /** Posturas efectivas: con el veto, quien rechaza a Vox vota no si Vox vota sí (salvo el propio candidato). */
  function efectivas(c) {
    const p = { ...posturas[c] };
    if (veto.checked && p.VOX === "si") {
      for (const x of RECHAZAN_A_VOX) if (x in p && x !== c) p[x] = "no";
    }
    return p;
  }

  const pct = (x) => (x > 0 && x < 0.005 ? "< 1 %" : x > 0.995 && x < 1 ? "> 99 %" : `${Math.round(100 * x)} %`);

  function calcular(c) {
    const p = efectivas(c);
    const si = new Int32Array(n), no = new Int32Array(n);
    for (const x of claves) {
      const s = sim[x];
      if (p[x] === "si") for (let i = 0; i < n; i++) si[i] += s[i];
      else if (p[x] === "no") for (let i = 0; i < n; i++) no[i] += s[i];
    }
    let primera = 0, segunda = 0;
    for (let i = 0; i < n; i++) {
      if (si[i] >= MAYORIA) primera++;
      else if (si[i] > no[i]) segunda++;
    }
    const med = (a) => Array.from(a).sort((x, y) => x - y)[Math.floor(n / 2)];
    return { primera: primera / n, segunda: segunda / n, total: (primera + segunda) / n, si: med(si), no: med(no), p };
  }

  function pintarResultados() {
    const caja = raiz.querySelector("[data-inv-resultados]");
    caja.replaceChildren(...Object.entries(CANDIDATOS).map(([c, quien]) => {
      const r = calcular(c);
      const art = document.createElement("article");
      art.className = "tarjeta investidura__candidato";
      art.style.setProperty("--c", partidos.find((x) => x.clave === c)?.color || "#888");
      art.innerHTML = `<h3>${quien} <span>(${partidos.find((x) => x.clave === c)?.nombre || c})</span></h3>
        <p class="cifra">${pct(r.total)}</p>
        <p class="cifra__texto">de las simulaciones sale investido</p>
        <dl class="filas">
          <div><dt>En la primera votación (176 síes)</dt><dd>${pct(r.primera)}</dd></div>
          <div><dt>En la segunda (más síes que noes)</dt><dd>${pct(r.segunda)}</dd></div>
          <div><dt>Síes y noes, mediana</dt><dd>${r.si} – ${r.no}</dd></div>
        </dl>`;
      return art;
    }));
    // en la tabla, marca las posturas que el veto ha cambiado
    raiz.querySelectorAll("select[data-cand]").forEach((s) => {
      const ef = efectivas(s.dataset.cand)[s.dataset.partido];
      s.classList.toggle("vetado", ef !== s.value);
      s.title = ef !== s.value ? "Vota no por el veto a Vox" : "";
    });
  }

  function pintarTabla() {
    const cuerpo = raiz.querySelector("[data-inv-filas]");
    cuerpo.replaceChildren(...partidos.map((p) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<th scope="row"><span class="punto" style="--c: ${p.color}"></span>${p.nombre}</th>
        <td class="num">${p.mediana}</td>`;
      for (const c of Object.keys(CANDIDATOS)) {
        const td = document.createElement("td");
        const sel = document.createElement("select");
        sel.className = "postura";
        sel.dataset.cand = c;
        sel.dataset.partido = p.clave;
        sel.setAttribute("aria-label", `${p.nombre}, si el candidato es ${CANDIDATOS[c]}`);
        for (const [v, t] of Object.entries(TEXTOS)) sel.add(new Option(t, v, false, posturas[c][p.clave] === v));
        sel.dataset.valor = sel.value;
        sel.addEventListener("change", () => {
          posturas[c][p.clave] = sel.value;
          sel.dataset.valor = sel.value;
          pintarResultados();
        });
        td.append(sel);
        tr.append(td);
      }
      return tr;
    }));
  }

  porDefecto();
  pintarTabla();
  pintarResultados();
  veto.addEventListener("change", pintarResultados);
  raiz.querySelector("[data-inv-restablecer]").addEventListener("click", () => {
    porDefecto();
    veto.checked = true;
    pintarTabla();
    pintarResultados();
  });
})();
