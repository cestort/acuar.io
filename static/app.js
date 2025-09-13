async function fetchMeasurements(aqId) {
  if (!aqId) return [];
  const res = await fetch(`/api/measurements/${aqId}`);
  return await res.json();
}

function lineDataset(label, key, data) {
  return {
    label: label,
    data: data.map(d => ({ x: d.date, y: d[key] })),
    spanGaps: true
  };
}

document.addEventListener("DOMContentLoaded", async () => {
  const aqId = window.__SELECTED_AQUARIUM__;
  const ctx = document.getElementById("evolutionChart");
  if (!ctx || !aqId) return;

  let raw = await fetchMeasurements(aqId);

  const toggles = Array.from(document.querySelectorAll(".metric-toggle"));

  const metrics = [
    { key: "nitrate", label: "NO₃" },
    { key: "phosphate", label: "PO₄" },
    { key: "kh", label: "KH" },
    { key: "magnesium", label: "Mg" },
    { key: "calcium", label: "Ca" },
  ];

  function visibleKeys() {
    return toggles.filter(t => t.checked).map(t => t.value);
  }

  let chart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: visibleKeys().map(k => {
        const m = metrics.find(m => m.key === k);
        return lineDataset(m.label, m.key, raw);
      })
    },
    options: {
      parsing: false,
      normalized: true,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { type: "time", time: { unit: "day" } },
        y: { beginAtZero: false }
      },
      plugins: {
        tooltip: { mode: "nearest", intersect: false },
        legend: { position: "bottom" }
      }
    }
  });

  toggles.forEach(t => {
    t.addEventListener("change", () => {
      chart.data.datasets = visibleKeys().map(k => {
        const m = metrics.find(m => m.key === k);
        return lineDataset(m.label, m.key, raw);
      });
      chart.update();
    });
  });
});
