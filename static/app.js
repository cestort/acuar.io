async function fetchMeasurements(aqId) {
  if (!aqId) return [];
  try {
    const res = await fetch(`/api/measurements/${aqId}`, { cache: "no-store" });
    if (!res.ok) {
      console.error('Error fetching measurements:', res.status);
      return [];
    }
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error('Error fetching measurements:', error);
    return [];
  }
}

function parseDate(dateStr) {
  if (!dateStr) return null;
  // Crear fecha en formato ISO para evitar problemas de timezone
  return new Date(String(dateStr).trim() + "T12:00:00");
}

function buildPoints(data, key) {
  const validPoints = data
    .filter(d => d && d.date && d[key] != null && d[key] !== '')
    .map(d => {
      const date = parseDate(d.date);
      const value = parseFloat(d[key]);
      
      if (!date || isNaN(date.getTime()) || isNaN(value)) {
        return null;
      }
      
      return { x: date, y: value };
    })
    .filter(point => point !== null)
    .sort((a, b) => a.x - b.x);
  
  console.log(`Points for ${key}:`, validPoints);
  return validPoints;
}

// Colores para las diferentes métricas
const COLORS = {
  nitrate: '#ff6b6b',    // Rojo
  phosphate: '#4ecdc4',  // Verde agua
  kh: '#45b7d1',        // Azul
  magnesium: '#f7b731',  // Amarillo
  calcium: '#a55eea'     // Púrpura
};

function createDataset(label, points, key) {
  return {
    label: label,
    data: points,
    borderColor: COLORS[key] || '#ffffff',
    backgroundColor: (COLORS[key] || '#ffffff') + '20',
    borderWidth: 2,
    pointRadius: 4,
    pointHoverRadius: 6,
    fill: false,
    tension: 0.1,
    spanGaps: false
  };
}

document.addEventListener("DOMContentLoaded", async () => {
  const aqId = window.__SELECTED_AQUARIUM__;
  const ctx = document.getElementById("evolutionChart");
  
  if (!ctx) {
    console.error('Canvas element not found');
    return;
  }
  
  if (!aqId) {
    console.warn('No aquarium selected');
    return;
  }

  console.log('Loading data for aquarium ID:', aqId);
  
  const rawData = await fetchMeasurements(aqId);
  console.log('Raw measurements data:', rawData);

  const toggles = Array.from(document.querySelectorAll(".metric-toggle"));
  const metrics = [
    { key: "nitrate",   label: "NO₃ (mg/L)" },
    { key: "phosphate", label: "PO₄ (mg/L)" },
    { key: "kh",        label: "KH (dKH)" },
    { key: "magnesium", label: "Mg (ppm)" },
    { key: "calcium",   label: "Ca (ppm)" },
  ];

  function getVisibleMetrics() {
    const checked = toggles.filter(t => t.checked).map(t => t.value);
    return checked.length ? checked : ["nitrate"]; // Por defecto mostrar al menos nitrate
  }

  function createDatasets() {
    const visibleKeys = getVisibleMetrics();
    const datasets = [];
    
    visibleKeys.forEach(key => {
      const metric = metrics.find(m => m.key === key);
      if (metric) {
        const points = buildPoints(rawData, key);
        if (points.length > 0) {
          datasets.push(createDataset(metric.label, points, key));
        }
      }
    });
    
    console.log('Created datasets:', datasets);
    return datasets;
  }

  // Configuración del gráfico
  const chartConfig = {
    type: "line",
    data: {
      datasets: createDatasets()
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#ffffff',
            usePointStyle: true,
            padding: 20
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#ffffff',
          bodyColor: '#ffffff',
          borderColor: '#ffffff',
          borderWidth: 1
        }
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'day',
            displayFormats: {
              day: 'MMM dd'
            },
            tooltipFormat: 'MMM dd, yyyy'
          },
          grid: {
            color: 'rgba(255, 255, 255, 0.1)'
          },
          ticks: {
            color: '#ffffff'
          }
        },
        y: {
          beginAtZero: false,
          grid: {
            color: 'rgba(255, 255, 255, 0.1)'
          },
          ticks: {
            color: '#ffffff'
          }
        }
      }
    }
  };

  let chart;
  
  try {
    chart = new Chart(ctx, chartConfig);
    console.log('Chart created successfully');
  } catch (error) {
    console.error('Error creating chart:', error);
    
    // Fallback: crear gráfico simple sin escala de tiempo
    try {
      console.log('Attempting fallback chart without time scale');
      chartConfig.options.scales.x = {
        type: 'linear',
        grid: { color: 'rgba(255, 255, 255, 0.1)' },
        ticks: { color: '#ffffff' }
      };
      
      // Convertir fechas a números para el fallback
      const fallbackDatasets = createDatasets().map(dataset => ({
        ...dataset,
        data: dataset.data.map((point, index) => ({ x: index, y: point.y }))
      }));
      
      chartConfig.data.datasets = fallbackDatasets;
      chart = new Chart(ctx, chartConfig);
      console.log('Fallback chart created');
    } catch (fallbackError) {
      console.error('Error creating fallback chart:', fallbackError);
    }
  }

  // Event listeners para los toggles
  toggles.forEach(toggle => {
    toggle.addEventListener("change", () => {
      if (chart) {
        chart.data.datasets = createDatasets();
        chart.update('active');
        console.log('Chart updated after toggle change');
      }
    });
  });

  // Mostrar mensaje si no hay datos
  if (rawData.length === 0) {
    const chartContainer = ctx.parentElement;
    const noDataMsg = document.createElement('div');
    noDataMsg.className = 'text-center text-muted p-4';
    noDataMsg.innerHTML = '<p>No hay datos de mediciones para este acuario.</p><p>Añade algunos registros para ver la gráfica.</p>';
    chartContainer.appendChild(noDataMsg);
  }

  // ===== MEJORAS PARA MODALES =====
  
  // Auto-focus en el primer input cuando se abra un modal
  document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('shown.bs.modal', () => {
      const firstInput = modal.querySelector('input[type="text"], input[type="date"], input[name="name"]');
      if (firstInput) {
        firstInput.focus();
      }
    });
  });

  // Establecer fecha actual por defecto en el modal de nuevo registro
  const newMeasurementModal = document.getElementById('newMeasurementModal');
  if (newMeasurementModal) {
    newMeasurementModal.addEventListener('show.bs.modal', () => {
      const dateInput = document.getElementById('measurementDate');
      if (dateInput && !dateInput.value) {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        dateInput.value = `${year}-${month}-${day}`;
      }
    });
  }

  // Validación mejorada de rangos en tiempo real
  const rangeInputs = document.querySelectorAll('input[type="number"]');
  rangeInputs.forEach(input => {
    input.addEventListener('input', function() {
      const value = parseFloat(this.value);
      const min = parseFloat(this.min);
      const max = parseFloat(this.max);
      
      // Remover clases previas
      this.classList.remove('border-success', 'border-warning', 'border-danger');
      
      if (isNaN(value)) return;
      
      if (min !== undefined && max !== undefined) {
        if (value < min || value > max) {
          this.classList.add('border-danger');
          this.title = `Valor fuera del rango recomendado (${min}-${max})`;
        } else {
          this.classList.add('border-success');
          this.title = `Valor dentro del rango óptimo`;
        }
      }
    });
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Solo si no estamos en un input
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    
    // Ctrl/Cmd + N = Nuevo acuario
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
      e.preventDefault();
      const newAquariumBtn = document.querySelector('[data-bs-target="#newAquariumModal"]');
      if (newAquariumBtn) {
        newAquariumBtn.click();
      }
    }
    
    // Ctrl/Cmd + M = Nuevo registro (si hay acuario seleccionado)
    if ((e.ctrlKey || e.metaKey) && e.key === 'm') {
      e.preventDefault();
      const newMeasurementBtn = document.querySelector('[data-bs-target="#newMeasurementModal"]');
      if (newMeasurementBtn) {
        newMeasurementBtn.click();
      }
    }
    
    // Ctrl/Cmd + E = Editar acuario (si hay acuario seleccionado)
    if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
      e.preventDefault();
      const editAquariumBtn = document.querySelector('[data-bs-target="#editAquariumModal"]');
      if (editAquariumBtn) {
        editAquariumBtn.click();
      }
    }
  });

  // ===== SELECTOR DE ACUARIO CON IMAGEN DE FONDO =====
  
  function updateAquariumSelectorBackground() {
    const selector = document.getElementById('aquariumSelector');
    const preview = document.getElementById('aquariumPreview');
    
    if (!selector) return;

    function setBackground() {
      const selectedOption = selector.options[selector.selectedIndex];
      const imageUrl = selectedOption ? selectedOption.getAttribute('data-image') : null;
      
      // Limpiar estilos previos
      selector.style.backgroundImage = '';
      selector.classList.remove('has-background');
      if (preview) {
        preview.style.backgroundImage = '';
      }
      
      if (imageUrl) {
        // Verificar que la imagen existe antes de aplicarla
        const img = new Image();
        img.onload = function() {
          selector.style.backgroundImage = `url('${imageUrl}')`;
          selector.classList.add('has-background');
          if (preview) {
            preview.style.backgroundImage = `url('${imageUrl}')`;
          }
        };
        img.onerror = function() {
          console.warn('No se pudo cargar la imagen del acuario:', imageUrl);
        };
        img.src = imageUrl;
      }
    }

    // Establecer fondo inicial
    setBackground();

    // Actualizar fondo cuando cambie la selección
    selector.addEventListener('change', setBackground);
  }

  // Inicializar selector con imagen
  updateAquariumSelectorBackground();
});