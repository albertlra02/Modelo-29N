/* Simulador "¿y si…?": cada deslizador que se toca queda fijado; el servidor reparte el resto en proporción y
   devuelve escaños, sumas y mapa. Lo fijado queda en la dirección (?v_PP=34.5) para compartirlo. */
"use strict";

(() => {
  const raiz = document.querySelector("[data-simulador]");
  if (!raiz) return;
  const { pintar } = window.Modelo;
  const deslizadores = [...raiz.querySelectorAll(".deslizador")];
  const tablas = raiz.querySelector("[data-sim-tablas]");
  const leyenda = raiz.querySelector("[data-sim-leyenda]");
  const hemiciclo = document.getElementById("f-sim-hemiciclo");
  const mapa = document.getElementById("f-sim-mapa");
  const fmt = (v) => `${Number(v).toFixed(1).replace(".", ",")} %`;
  // relleno del deslizador hasta el valor (la pista se pinta con CSS a partir de --p)
  const rellenar = (input) => input.style.setProperty("--p", `${(100 * input.value) / input.max}%`);
  deslizadores.forEach((d) => rellenar(d.querySelector("input")));

  // tocados: los que el usuario ha movido (o venían en la dirección)
  const tocados = new Set(deslizadores.filter((d) => Math.abs(Number(d.querySelector("input").value) - Number(d.dataset.base)) >= 0.05)
    .map((d) => d.dataset.clave));
  deslizadores.forEach((d) => d.classList.toggle("deslizador--fijado", tocados.has(d.dataset.clave)));

  function consulta() {
    const q = new URLSearchParams(location.search);
    [...q.keys()].filter((k) => k.startsWith("v_")).forEach((k) => q.delete(k));
    deslizadores.forEach((d) => {
      if (tocados.has(d.dataset.clave)) q.set("v_" + d.dataset.clave, d.querySelector("input").value);
    });
    return q;
  }

  let pedido = 0;
  async function recalcular() {
    const q = consulta();
    const s = q.toString();
    history.replaceState(null, "", location.pathname + (s ? "?" + s : ""));
    const mio = ++pedido;
    raiz.classList.add("cargando");
    try {
      const r = await fetch("/api/simulador?" + s);
      if (!r.ok) throw new Error(r.statusText);
      const j = await r.json();
      if (mio !== pedido) return;               // ya hay una petición más nueva
      tablas.innerHTML = j.html;
      leyenda.innerHTML = j.leyenda;
      pintar(hemiciclo, j.hemiciclo);
      pintar(mapa, j.mapa);
      // los no fijados se mueven en proporción: se refleja en su deslizador
      deslizadores.forEach((d) => {
        if (tocados.has(d.dataset.clave) || !(d.dataset.clave in j.votos)) return;
        const v = j.votos[d.dataset.clave];
        d.querySelector("input").value = v;
        rellenar(d.querySelector("input"));
        d.querySelector("[data-valor]").textContent = fmt(v);
      });
    } finally {
      if (mio === pedido) raiz.classList.remove("cargando");
    }
  }

  let espera = null;
  deslizadores.forEach((d) => {
    const input = d.querySelector("input");
    input.addEventListener("input", () => {
      tocados.add(d.dataset.clave);
      d.classList.add("deslizador--fijado");
      d.querySelector("[data-valor]").textContent = fmt(input.value);
      rellenar(input);
      clearTimeout(espera);
      espera = setTimeout(recalcular, 150);
    });
  });

  raiz.querySelector("[data-restablecer]").addEventListener("click", () => {
    tocados.clear();
    deslizadores.forEach((d) => {
      d.classList.remove("deslizador--fijado");
      d.querySelector("input").value = d.dataset.base;
      rellenar(d.querySelector("input"));
      d.querySelector("[data-valor]").textContent = fmt(d.dataset.base);
    });
    recalcular();
  });
})();
