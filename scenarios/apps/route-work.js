/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

let generation = 0;
const sizes = {kilncast: 3000, ledger: 1262, elsewhere: 2005, commonplot: 2800, morrow: 2500, letterdesk: 1600, video: 4953};

export async function routeWork(app, view) {
  const module = await import(`/apps/${app}/route-work.js?generation=${++generation}`);
  const records = module.schemas.map((schema, index) => ({...schema, key: `${view}-${index}`, caption: `${schema.caption} · ${view}`}));
  const byName = new Map(records.map(record => [record.key, record]));
  window.gauntletRouteIndex = byName;
  let details = document.querySelector('#route-details');
  if (!details) {
    details = document.createElement('section');
    details.id = 'route-details';
    details.className = 'route-details';
    (document.querySelector('#reading-pane') || document.querySelector('main') || document.body).append(details);
  }
  const count = Math.ceil(sizes[app] / 6);
  details.replaceChildren();
  const geometry = [];
  for (let index = 0; index < count; index++) {
    const record = records[index % records.length];
    const article = document.createElement('article');
    const title = document.createElement('h3');
    title.textContent = `${view} · Field note ${index + 1}`;
    const text = document.createElement('p');
    text.textContent = record.caption;
    const label = document.createElement('span');
    label.textContent = record.tone;
    article.append(title, text, label);
    details.append(article);
    geometry.push({width: article.getBoundingClientRect().width, font: getComputedStyle(article).font});
  }
  window.gauntletRouteLayout = geometry;
  const images = [...document.images].filter(image => image.loading !== 'lazy' && image.src);
  await Promise.all(images.map(image => image.decode()));
  const sources = [...new Set(images.slice().sort((a, b) => b.naturalWidth * b.naturalHeight - a.naturalWidth * a.naturalHeight).map(image => image.currentSrc || image.src))].slice(0, 4);
  await Promise.all(sources.map(async source => {
    const response = await fetch(source);
    if (!response.ok) throw new Error(`Route image unavailable: ${response.status}`);
    const bitmap = await createImageBitmap(await response.blob());
    bitmap.close();
  }));
}
