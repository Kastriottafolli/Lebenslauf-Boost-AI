// Aggregated operational counts only: no cookies, IPs or personal user data.
export function trafficOverview(days, english = false) {
  const text = (de, en) => english ? en : de;
  const series = [
    ['page_views', text('Seitenaufrufe', 'Page views'), '#1767c3'],
    ['visit_sessions', text('App-Sitzungen', 'App sessions'), '#07877e'],
    ['registrations', text('Registrierungen', 'Registrations'), '#b86a07'],
  ];
  const rows = days.map(row => ({
    day: /^\d{4}-\d{2}-\d{2}$/.test(row.day) ? row.day : '',
    ...Object.fromEntries(series.map(([key]) => [key, Math.max(0, Number(row[key]) || 0)])),
  })).filter(row => row.day);
  const figure = document.createElement('figure');
  figure.className = 'traffic-overview';
  const caption = document.createElement('figcaption');
  caption.textContent = text('Dein Traffic im Verlauf', 'Your traffic over time');
  figure.append(caption);
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.textContent = text('Für diesen Zeitraum liegen noch keine Aufrufe vor.', 'No page views recorded for this period yet.');
    figure.append(empty);
    return figure;
  }
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 900 250');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', text('Tägliche Aufrufe, App-Sitzungen und Registrierungen. Die genauen Werte stehen in der Tabelle darunter.', 'Daily views, app sessions and registrations. Exact values are in the table below.'));
  const node = (name, attributes, value) => {
    const element = document.createElementNS(svg.namespaceURI, name);
    Object.entries(attributes).forEach(([key, v]) => element.setAttribute(key, String(v)));
    if (value !== undefined) element.textContent = value;
    return element;
  };
  const maximum = Math.max(1, ...rows.flatMap(row => series.map(([key]) => row[key])));
  [0, .5, 1].forEach(part => {
    const y = 211 - 185 * part;
    svg.append(node('line', {x1: 45, x2: 885, y1: y, y2: y, stroke: '#dbe6ee'}));
    svg.append(node('text', {x: 37, y: y + 4, 'text-anchor': 'end', fill: '#52647c', 'font-size': 12}, Math.round(maximum * part)));
  });
  const width = 840 / rows.length;
  rows.forEach((row, index) => {
    series.forEach(([key, title, color], group) => {
      const height = 185 * row[key] / maximum;
      const bar = node('rect', {x: 45 + index * width + group * width / 3, y: 211 - height, width: Math.max(.8, width / 3 - 1), height, fill: color, rx: 1});
      bar.append(node('title', {}, `${row.day} · ${title}: ${row[key]}`));
      svg.append(bar);
    });
  });
  [0, Math.floor((rows.length - 1) / 2), rows.length - 1].filter((index, i, all) => all.indexOf(index) === i).forEach(index => {
    svg.append(node('text', {x: 45 + (index + .5) * width, y: 238, 'text-anchor': 'middle', fill: '#52647c', 'font-size': 12}, rows[index].day.slice(5)));
  });
  figure.append(svg);
  const legend = document.createElement('div');
  legend.className = 'traffic-legend';
  series.forEach(([, title, color]) => {
    const label = document.createElement('span');
    const swatch = document.createElement('i');
    swatch.style.background = color;
    label.append(swatch, document.createTextNode(title));
    legend.append(label);
  });
  figure.append(legend);
  const download = document.createElement('button');
  download.type = 'button';
  download.className = 'button outline';
  download.textContent = text('Traffic als CSV herunterladen', 'Download traffic CSV');
  download.addEventListener('click', () => {
    const csv = ['day_utc,page_views,app_sessions,registrations', ...rows.map(row => [row.day, ...series.map(([key]) => Math.trunc(row[key]))].join(','))].join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'tafolliboost-traffic.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  figure.append(download);
  return figure;
}
