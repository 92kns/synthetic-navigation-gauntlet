"use strict";

(function () {
  const DEAL_COUNT = __DOM_NODES__;
  const seed = (self.__gen && self.__gen.hydration) | 0;

  for (const price of document.querySelectorAll(".price")) {
    const sku = Number(price.dataset.sku);
    price.textContent = `$${(19 + ((seed >>> sku) & 63)).toFixed(2)}`;
  }
  for (const button of document.querySelectorAll(".card button")) {
    button.disabled = false;
  }

  const deals = document.getElementById("deals");
  const fragment = document.createDocumentFragment();
  for (let i = 0; i < DEAL_COUNT; i++) {
    const cell = document.createElement("div");
    cell.className = (seed ^ (i * 2654435761)) & 4 ? "deal hot" : "deal";
    cell.textContent = `#${i} -${(i * 7) % 40}%`;
    fragment.appendChild(cell);
  }
  deals.textContent = "";
  deals.classList.remove("placeholder");
  deals.appendChild(fragment);

  for (const [i, cell] of document.querySelectorAll(".gt td").entries()) {
    cell.className = `g${(i * 13 + seed) & 31}`;
  }

  document.body.classList.add("hydrated");
  document.documentElement.dataset.hydrated = "1";
  navGauntlet.rendered();
})();
