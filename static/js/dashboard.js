class DashboardController {
    constructor() {
        this.filterForm = document.querySelector('#dashboard-filter-form');
        this.municipioSelect = document.querySelector('#filtro-municipio');
        this.refreshBtn = document.querySelector('#btn-recargar-dashboard');
        this.alertBox = document.querySelector('#dashboard-alerta');

        this.labelCurrentFilter = document.querySelector('#etiqueta-filtro-actual');
        this.kpiTotal = document.querySelector('#kpi-total');
        this.kpiSubtitle = document.querySelector('#kpi-subtitulo-filtro');
        this.kpiPendientes = document.querySelector('#kpi-pendientes');
        this.kpiResueltos = document.querySelector('#kpi-resueltos');
        this.kpiPorcentaje = document.querySelector('#kpi-porcentaje');
        this.kpiProgressBar = document.querySelector('#kpi-barra-progreso');
        this.estatusChartSubtitle = document.querySelector('#subtitulo-grafica-estatus');
        this.tableBody = document.querySelector('#tabla-municipios-body');

        this.estatusCanvas = document.querySelector('#estatus-chart');
        this.municipiosCanvas = document.querySelector('#municipios-chart');

        this.estatusChart = null;
        this.municipiosChart = null;
    }

    init() {
        if (!this.filterForm || !this.municipioSelect) {
            return;
        }

        const initialDataTag = document.querySelector('#dashboard-initial-data');
        if (initialDataTag) {
            try {
                const initialData = JSON.parse(initialDataTag.textContent);
                this.render(initialData);
            } catch {
                this.fetchAndRender(this.municipioSelect.value);
            }
        }

        this.municipioSelect.addEventListener('change', () => {
            this.fetchAndRender(this.municipioSelect.value);
        });

        this.filterForm.addEventListener('submit', (event) => {
            event.preventDefault();
            this.fetchAndRender(this.municipioSelect.value);
        });

        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => {
                this.fetchAndRender(this.municipioSelect.value);
            });
        }
    }

    showAlert(message) {
        if (!this.alertBox) {
            return;
        }
        if (message) {
            this.alertBox.textContent = message;
            this.alertBox.classList.remove('d-none');
        } else {
            this.alertBox.textContent = '';
            this.alertBox.classList.add('d-none');
        }
    }

    async fetchAndRender(municipioValue) {
        const query = municipioValue && municipioValue !== 'all'
            ? `?municipio_id=${encodeURIComponent(municipioValue)}`
            : '';
        this.showAlert('');
        if (this.refreshBtn) {
            this.refreshBtn.disabled = true;
        }

        try {
            const response = await fetch(`/api/v1/dashboard/estatus${query}`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.mensaje || 'No se pudieron obtener las estadísticas.');
            }
            this.render(data);
            const nextUrl = query ? `/admin${query}` : '/admin';
            window.history.replaceState({}, '', nextUrl);
        } catch (error) {
            this.showAlert(error.message || 'Error al actualizar el tablero.');
        } finally {
            if (this.refreshBtn) {
                this.refreshBtn.disabled = false;
            }
        }
    }

    render(data) {
        const filtroNombre = data.filtro?.municipio_nombre || 'Todos los municipios (Total)';
        const resumen = data.resumen || {
            total: 0,
            pendientes: 0,
            resueltos: 0,
            otros: 0,
            porcentaje_resuelto: 0
        };

        this.labelCurrentFilter.textContent = filtroNombre;
        this.kpiTotal.textContent = String(resumen.total);
        this.kpiSubtitle.textContent = filtroNombre;
        this.kpiPendientes.textContent = String(resumen.pendientes);
        this.kpiResueltos.textContent = String(resumen.resueltos);
        this.kpiPorcentaje.textContent = `${resumen.porcentaje_resuelto}%`;
        this.kpiProgressBar.style.width = `${resumen.porcentaje_resuelto}%`;
        this.estatusChartSubtitle.textContent = `Comparativa “Pendiente” vs “Resuelto” (${filtroNombre})`;

        this.renderTable(data.por_municipio || []);
        this.renderEstatusChart(resumen);
        this.renderMunicipiosChart(data.por_municipio || []);
    }

    renderTable(porMunicipio) {
        if (!this.tableBody) {
            return;
        }
        this.tableBody.innerHTML = '';

        if (porMunicipio.length === 0) {
            const emptyRow = document.createElement('tr');
            const cell = document.createElement('td');
            cell.colSpan = 5;
            cell.className = 'text-center text-body-secondary py-3';
            cell.textContent = 'No hay municipios registrados para mostrar.';
            emptyRow.appendChild(cell);
            this.tableBody.appendChild(emptyRow);
            return;
        }

        porMunicipio.forEach((item) => {
            const row = document.createElement('tr');
            const avance = item.total > 0
                ? Math.round((item.resueltos / item.total) * 1000) / 10
                : 0.0;

            const tdNombre = document.createElement('td');
            tdNombre.className = 'fw-semibold';
            tdNombre.textContent = item.nombre;
            if (!item.activo) {
                const badgeInactivo = document.createElement('span');
                badgeInactivo.className = 'badge text-bg-secondary ms-1';
                badgeInactivo.textContent = 'Inactivo';
                tdNombre.appendChild(badgeInactivo);
            }

            const tdPendiente = document.createElement('td');
            tdPendiente.className = 'text-center';
            const badgePendiente = document.createElement('span');
            badgePendiente.className = 'badge status-badge-pendiente';
            badgePendiente.textContent = String(item.pendientes);
            tdPendiente.appendChild(badgePendiente);

            const tdResuelto = document.createElement('td');
            tdResuelto.className = 'text-center';
            const badgeResuelto = document.createElement('span');
            badgeResuelto.className = 'badge status-badge-resuelto';
            badgeResuelto.textContent = String(item.resueltos);
            tdResuelto.appendChild(badgeResuelto);

            const tdTotal = document.createElement('td');
            tdTotal.className = 'text-center fw-bold';
            tdTotal.textContent = String(item.total);

            const tdAvance = document.createElement('td');
            tdAvance.className = 'text-end';
            tdAvance.textContent = `${avance}%`;

            row.append(tdNombre, tdPendiente, tdResuelto, tdTotal, tdAvance);
            this.tableBody.appendChild(row);
        });
    }

    renderEstatusChart(resumen) {
        if (!this.estatusCanvas) {
            return;
        }

        const labels = ['Pendiente', 'Resuelto'];
        const values = [resumen.pendientes, resumen.resueltos];
        const bgColors = ['#f59f00', '#2b8a3e'];

        if (resumen.otros > 0) {
            labels.push('Otros');
            values.push(resumen.otros);
            bgColors.push('#5b2c6f');
        }

        if (typeof window.Chart === 'undefined') {
            this.drawFallbackBars(this.estatusCanvas, labels, values, bgColors);
            return;
        }

        if (this.estatusChart) {
            this.estatusChart.data.labels = labels;
            this.estatusChart.data.datasets[0].data = values;
            this.estatusChart.data.datasets[0].backgroundColor = bgColors;
            this.estatusChart.update();
            return;
        }

        this.estatusChart = new window.Chart(this.estatusCanvas, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [
                    {
                        data: values,
                        backgroundColor: bgColors,
                        borderColor: '#ffffff',
                        borderWidth: 2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    renderMunicipiosChart(porMunicipio) {
        if (!this.municipiosCanvas) {
            return;
        }

        const labels = porMunicipio.map((m) => m.nombre);
        const pendientesData = porMunicipio.map((m) => m.pendientes);
        const resueltosData = porMunicipio.map((m) => m.resueltos);

        if (typeof window.Chart === 'undefined') {
            this.drawFallbackBars(
                this.municipiosCanvas,
                labels,
                porMunicipio.map((m) => m.total),
                labels.map(() => '#5b2c6f')
            );
            return;
        }

        if (this.municipiosChart) {
            this.municipiosChart.data.labels = labels;
            this.municipiosChart.data.datasets[0].data = pendientesData;
            this.municipiosChart.data.datasets[1].data = resueltosData;
            this.municipiosChart.update();
            return;
        }

        this.municipiosChart = new window.Chart(this.municipiosCanvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Pendiente',
                        data: pendientesData,
                        backgroundColor: '#f59f00',
                        borderRadius: 4
                    },
                    {
                        label: 'Resuelto',
                        data: resueltosData,
                        backgroundColor: '#2b8a3e',
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    drawFallbackBars(canvas, labels, values, colors) {
        const ctx = canvas.getContext('2d');
        if (!ctx) {
            return;
        }
        const width = canvas.parentElement.clientWidth || 360;
        const height = 240;
        canvas.width = width;
        canvas.height = height;
        ctx.clearRect(0, 0, width, height);

        const maxVal = Math.max(...values, 1);
        const barWidth = Math.max(24, Math.floor((width - 40) / Math.max(labels.length * 1.8, 1)));

        labels.forEach((label, index) => {
            const val = values[index] || 0;
            const barHeight = Math.round((val / maxVal) * (height - 65));
            const x = 24 + index * (barWidth + 20);
            const y = height - 35 - barHeight;

            ctx.fillStyle = colors[index % colors.length] || '#5b2c6f';
            ctx.fillRect(x, y, barWidth, barHeight);

            ctx.fillStyle = '#2c3e50';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(String(val), x + barWidth / 2, y - 6);
            ctx.fillText(label.slice(0, 10), x + barWidth / 2, height - 14);
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const controller = new DashboardController();
    controller.init();
});

