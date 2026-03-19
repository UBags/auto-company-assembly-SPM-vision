console.log('app.js loaded');
try {
    console.log('Script block started');

    function downloadCSV(csv, filename) {
        console.log('downloadCSV called with filename:', filename);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
    console.log('downloadCSV defined');

    function downloadJSON(json, filename) {
        console.log('downloadJSON called with filename:', filename);
        const blob = new Blob([json], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
    console.log('downloadJSON defined');

    function jsonToCsv(jsonData) {
        if (!jsonData || jsonData.length === 0) return '';
        const headers = Object.keys(jsonData[0]);
        const csvRows = [headers.join(',')];
        jsonData.forEach(row => {
            const values = headers.map(header => {
                const value = row[header];
                return value === null || value === undefined ? '' : `'${value}'`;
            });
            csvRows.push(values.join(','));
        });
        return csvRows.join('\n');
    }
    console.log('jsonToCsv defined');

    function query(method, params) {
        console.log('query called with method:', method, 'params:', params);
        const format = method.endsWith('/json/') ? 'json' : 'csv';
        fetch(`http://localhost:8000/api/${method}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        })
        .then(response => {
            console.log('Fetch response status:', response.status);
            const contentType = response.headers.get('Content-Type');
            if (contentType.includes('application/json')) {
                return response.json().then(data => ({ data, format: 'json' }));
            } else if (contentType.includes('text/csv')) {
                return response.text().then(text => ({ data: text, format: 'csv' }));
            } else {
                throw new Error('Unsupported response format');
            }
        })
        .then(({ data, format }) => {
            console.log('Response data:', data, 'format:', format);
            const resultArea = document.getElementById('result');
            const recordCountSpan = document.getElementById('recordCount');
            let displayContent = '';
            let recordCount = 0;
            const date = new Date().toISOString().split('T')[0];
            const methodName = method.split('/')[0];

            if (format === 'json') {
                if (data.error) {
                    resultArea.value = `Error: ${data.error}`;
                    recordCountSpan.textContent = '(0 records)';
                    return;
                }
                if (data.data && data.data.length > 0) {
                    displayContent = JSON.stringify(data.data, null, 2); // Pretty-print JSON
                    recordCount = data.data.length;
                    downloadJSON(displayContent, `${methodName}_${date}.json`);
                } else {
                    displayContent = 'No records found for the selected criteria';
                    recordCount = 0;
                }
            } else {
                displayContent = data;
                const lines = data.trim().split('\n');
                recordCount = lines.length > 1 ? lines.length - 1 : 0;
                if (recordCount > 0) {
                    downloadCSV(displayContent, `${methodName}_${date}.csv`);
                } else {
                    displayContent = 'No records found for the selected criteria';
                }
            }

            resultArea.value = displayContent;
            recordCountSpan.textContent = `(${recordCount} records)`;
        })
        .catch(error => {
            console.error('Fetch error:', error);
            document.getElementById('result').value = `Error: ${error}`;
            document.getElementById('recordCount').textContent = '(0 records)';
        });
    }
    console.log('query defined');

    function validateAndQuery(method, format, selectId = null) {
        console.log('validateAndQuery called with method:', method, 'format:', format, 'selectId:', selectId);
        const modelSelect = selectId ? document.getElementById(selectId) : null;
        const modelName = modelSelect ? modelSelect.value : '';
        const params = {};

        if (['by_model_name', 'by_model_name_and_date', 'today_by_model'].includes(method)) {
            if (modelSelect && modelSelect.options.length <= 1) {
                alert('No model names available in the database. Please populate the database.');
                document.getElementById('result').value = 'Error: No model names available';
                document.getElementById('recordCount').textContent = '(0 records)';
                return;
            }
            if (!modelName) {
                alert('Please select a valid model name.');
                document.getElementById('result').value = 'Error: Model name not selected';
                document.getElementById('recordCount').textContent = '(0 records)';
                return;
            }
        }

        if (method === 'by_model_name') {
            params.modelName = modelName;
        } else if (method === 'by_model_name_and_date') {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            if (!startDate || !endDate) {
                alert('Please select both start and end dates.');
                document.getElementById('result').value = 'Error: Start or end date not selected';
                document.getElementById('recordCount').textContent = '(0 records)';
                return;
            }
            const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
            if (!dateRegex.test(startDate) || !dateRegex.test(endDate)) {
                alert('Dates must be in YYYY-MM-DD format.');
                document.getElementById('result').value = 'Error: Invalid date format';
                document.getElementById('recordCount').textContent = '(0 records)';
                return;
            }
            params.modelName = modelName;
            params.startDate = startDate;
            params.endDate = endDate;
        } else if (method === 'today_by_model') {
            params.model_name = modelName;
        } else if (method === 'by_date_limits') {
            const startDate = document.getElementById('startDate2').value;
            const endDate = document.getElementById('endDate2').value;
            if (!startDate || !endDate) {
                alert('Please select both start and end dates.');
                document.getElementById('result').value = 'Error: Start or end date not selected';
                document.getElementById('recordCount').textContent = '(0 records)';
                return;
            }
            const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
            if (!dateRegex.test(startDate) || !dateRegex.test(endDate)) {
                alert('Dates must be in YYYY-MM-DD format.');
                document.getElementById('result').value = 'Error: Invalid date format';
                document.getElementById('recordCount').textContent = '(0 records)';
                return;
            }
            params.startDate = startDate;
            params.endDate = endDate;
        } else if (method === 'all_today') {
            // No parameters needed
        } else {
            document.getElementById('result').value = 'Error: Invalid method';
            document.getElementById('recordCount').textContent = '(0 records)';
            return;
        }

        const fullMethod = `${method}/${format}/`;
        console.log('Sending params to backend:', params, 'fullMethod:', fullMethod);
        query(fullMethod, params);
    }
    console.log('validateAndQuery defined');

    window.onload = function() {
        console.log('window.onload executed');
        const selects = ['modelName1', 'modelName2', 'modelName3'];
        selects.forEach(id => {
            const select = document.getElementById(id);
            if (select && select.options.length <= 1) {
                const btnPrefix = id === 'modelName1' ? 'by_model_name' :
                                  id === 'modelName2' ? 'by_model_name_and_date' :
                                  'today_by_model';
                document.getElementById(`${btnPrefix}_csv_btn`).disabled = true;
                document.getElementById(`${btnPrefix}_json_btn`).disabled = true;
            }
        });
    };
    console.log('Script block completed');
} catch (e) {
    console.error('Script error:', e);
}