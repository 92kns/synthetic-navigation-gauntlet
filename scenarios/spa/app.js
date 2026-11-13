"use strict";

(function () {
  const view = document.getElementById("view");

  // Fixed amount of work standing in for framework/state-management cost.
  function busy(iterations) {
    let x = 2463534242;
    for (let i = 0; i < iterations; i++) {
      x ^= x << 13;
      x ^= x >>> 17;
      x ^= x << 5;
    }
    return x;
  }

  function cardHtml(item, i) {
    return (
      `<a class="gc g${i % 32}" href="#"><picture><source type="image/webp" srcset="${item.img} 320w, ${item.img2x} 640w" sizes="(min-width: 1100px) 33vw, 50vw">` +
      `<img src="${item.jpeg}" width="__IMAGE_WIDTH__" height="__IMAGE_HEIGHT__" loading="${i < __IMAGE_EAGER__ ? "eager" : "lazy"}" alt=""></picture>` +
      `<span>${item.title}</span><b>$${item.price}</b>` +
      `<small>${item.blurb}</small></a>`
    );
  }

  function facetsHtml(items) {
    const rows = [];
    for (let i = 0; i < __FACETS__; i++) {
      const item = items[i % items.length];
      rows.push(
        `<label class="g${(i * 7) % 32}"><input type="checkbox"${i % 3 ? "" : " checked"}> ` +
          `${item.title.split(" ")[i % 4]} (${(item.rating * 37 + i) % 200})</label>`
      );
    }
    return `<aside class="facets">${rows.join("")}</aside>`;
  }

  async function fetchItems(url) {
    const response = await fetch(url);
    return (await response.json()).items;
  }

  async function show(name, html, restoreScroll = null) {
    view.innerHTML = html;
    if (restoreScroll !== null) scrollTo(0, restoreScroll);
    document.body.dataset.view = name;
    await navGauntlet.rendered(name);
  }

  async function renderHome(restoreScroll = null) {
    const items = await fetchItems(
      "/gen/json?items=__HOME_ITEMS__&seed=spa-home&img_delay_ms=__IMAGE_DELAY__&delay_ms=__HOME_DELAY__"
    );
    busy(__HOME_WORK__);
    await show(
      "home",
      `<section class="hero g3"><h1>Autumn collection</h1>` +
        `<p>Hand-picked items, updated daily.</p></section>` +
        `<div class="cards">${items.map(cardHtml).join("")}</div>`,
      restoreScroll
    );
  }

  async function renderProducts() {
    // No blank interstitial: it makes histogram-based SpeedIndex under-report
    // the soft navigation.
    document.body.dataset.view = "loading";
    const items = await fetchItems(
      "/gen/json?items=__ROUTE_ITEMS__&seed=spa-products&img_delay_ms=__IMAGE_DELAY__&delay_ms=__PRODUCTS_DELAY__"
    );
    busy(__ROUTE_WORK__);
    const sorted = items.slice().sort((a, b) => a.price - b.price);
    await show(
      "products",
      `<h2>Products</h2><div class="products">${facetsHtml(sorted)}` +
        `<div class="cards">${sorted.map(cardHtml).join("")}</div></div>`
    );
  }

  document.getElementById("nav-products").addEventListener("click", event => {
    event.preventDefault();
    busy(__CLICK_WORK__);
    history.replaceState({ view: "home", scroll: scrollY }, "", "/spa/index.html");
    history.pushState({ view: "products" }, "", "/spa/products");
    renderProducts();
  });

  history.scrollRestoration = "manual";
  addEventListener("popstate", async event => {
    await renderHome(event.state?.scroll || 0);
  });
  renderHome();
})();
