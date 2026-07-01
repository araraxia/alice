/**
 * Price Graph Modal JavaScript
 * Handles chart creation and modal lifecycle for OSRS item price graphs
 */

// Define global function if not already defined
if (typeof window.closePriceGraphModal === 'undefined') {
    window.closePriceGraphModal = function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            // Destroy chart instance if exists
            const canvas = modal.querySelector('canvas');
            if (canvas && canvas.chart) {
                canvas.chart.destroy();
            }
            modal.remove();
        }
    };
}

/**
 * Initialize a price chart with the given data
 * @param {Object} config - Chart configuration
 * @param {string} config.modalId - ID of the modal containing the chart
 * @param {string} config.canvasId - ID of the canvas element
 * @param {Array} config.timestamps - Array of timestamp strings
 * @param {Array} config.highPrices - Array of high prices
 * @param {Array} config.lowPrices - Array of low prices
 */
window.initializePriceChart = function(config) {
    const { modalId, canvasId, timestamps, highPrices, lowPrices } = config;
    
    // Get canvas within modal context to avoid selecting background canvas
    const modal = document.getElementById(modalId);
    const canvas = modal ? modal.querySelector('#' + canvasId) : document.getElementById(canvasId);
    
    if (!canvas) {
        console.error('Chart canvas not found:', canvasId);
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: timestamps.map(ts => new Date(ts)),
            datasets: [
                {
                    label: 'High Price',
                    data: highPrices,
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    tension: 0.1
                },
                {
                    label: 'Low Price',
                    data: lowPrices,
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    tension: 0.1
                }
            ]
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
                    display: true,
                    position: 'top',
                },
                tooltip: {
                    enabled: true,
                    callbacks: {
                        title: function(context) {
                            const date = new Date(context[0].label);
                            return date.toLocaleString();
                        },
                        label: function(context) {
                            return context.dataset.label + ': ' + context.parsed.y.toLocaleString() + ' GP';
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'hour',
                        displayFormats: {
                            hour: 'MMM d, HH:mm',
                            day: 'MMM d, yyyy'
                        }
                    },
                    title: {
                        display: true,
                        text: 'Date/Time'
                    },
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Price (GP)'
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
    
    // Store chart instance on canvas for cleanup
    canvas.chart = chart;
};
