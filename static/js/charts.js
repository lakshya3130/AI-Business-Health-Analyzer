document.addEventListener('DOMContentLoaded', () => {
  if (!window.Chart) return;
  const palette = { revenue: '#328a79', expenses: '#d89b52', profit: '#6578d4' };
  document.querySelectorAll('canvas[data-labels]').forEach((canvas) => {
    const labels = JSON.parse(canvas.dataset.labels || '[]');
    const series = ['revenue', 'expenses', 'profit'].map((key) => ({
      label: key[0].toUpperCase() + key.slice(1),
      data: JSON.parse(canvas.dataset[key] || '[]'),
      borderColor: palette[key], backgroundColor: `${palette[key]}1a`,
      fill: key === 'revenue', tension: 0.32, borderWidth: 2, pointRadius: 3
    }));
    new Chart(canvas, { type: 'line', data: { labels, datasets: series }, options: {
      responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: 'index' },
      plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8 } } },
      scales: { y: { beginAtZero: true, grid: { color: '#edf0f2' }, ticks: { callback: (v) => '₹' + Intl.NumberFormat('en-IN', { notation: 'compact' }).format(v) } }, x: { grid: { display: false } } }
    }});
  });
});
