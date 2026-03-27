function updateOrderStatusesLast40Days() {
    updateOrderStatusesLastNDays_(40);
}

function updateOrderStatusesLastNDays_(daysBack) {
    const ENABLE_VERBOSE_LOG = true;

    const scriptProps = PropertiesService.getScriptProperties();
    const apiKey = scriptProps.getProperty('CHANNELENGINE_API_KEY');
    if (!apiKey) {
        throw new Error('CHANNELENGINE_API_KEY is not set. Run setChannelEngineApiKey() once to store it in Script Properties.');
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const ordersSheet = ss.getSheetByName("Orders");
    if (!ordersSheet) {
        throw new Error('Tabblad "Orders" niet gevonden.');
    }

    const now = new Date();
    const fromDate = new Date(now);
    fromDate.setDate(fromDate.getDate() - Number(daysBack || 40));
    const startDate = fromDate.toISOString().split('T')[0];
    const endDate = new Date(now);
    endDate.setDate(endDate.getDate() - 1);
    const formattedEndDate = endDate.toISOString().split('T')[0];

    const baseUrl = `https://forelle.channelengine.net/api/v2/orders?apikey=${apiKey}&from=${startDate}&to=${formattedEndDate}`;

    if (ENABLE_VERBOSE_LOG) {
        Logger.log(`Start updateOrderStatusesLastNDays_(${daysBack})`);
        Logger.log(`Datum-range: from=${startDate}, to=${formattedEndDate}`);
    }

    // 1) Haal alle orders in de periode op en bouw lookup: orderId -> status
    const statusByOrderId = {};
    let page = 1;
    let totalPages = 1;

    do {
        const url = `${baseUrl}&page=${page}`;
        const response = UrlFetchApp.fetch(url);
        const data = JSON.parse(response.getContentText());

        totalPages = Math.ceil(data.TotalCount / 100);
        if (ENABLE_VERBOSE_LOG) {
            Logger.log(`Pagina ${page}/${totalPages}: ${data.Content.length} orders`);
        }

        for (let i = 0; i < data.Content.length; i++) {
            const order = data.Content[i];
            statusByOrderId[String(order.Id)] = order.Status;
        }

        page++;
    } while (page <= totalPages);

    // 2) Lees Orders-sheet en bepaal kolomindexen op basis van headers
    const lastRow = ordersSheet.getLastRow();
    const lastCol = ordersSheet.getLastColumn();
    if (lastRow < 2) {
        Logger.log('Geen data in Orders (alleen headers). Niets om bij te werken.');
        return;
    }

    const headers = ordersSheet.getRange(1, 1, 1, lastCol).getValues()[0].map(h => String(h || '').trim());
    const idColIdx = headers.indexOf('Id');
    const statusColIdx = headers.indexOf('Status');
    const orderDateColIdx = headers.indexOf('OrderDate');

    if (idColIdx === -1 || statusColIdx === -1) {
        throw new Error('Kan kolommen "Id" en/of "Status" niet vinden in Orders headers.');
    }

    // 3) Update alleen rijen binnen cutoff én waar status veranderd is
    const cutoff = new Date(now);
    cutoff.setDate(cutoff.getDate() - Number(daysBack || 40));

    const values = ordersSheet.getRange(2, 1, lastRow - 1, lastCol).getValues();
    let changed = 0;
    let matched = 0;

    for (let r = 0; r < values.length; r++) {
        const row = values[r];
        const orderId = String(row[idColIdx] || '');
        if (!orderId) continue;

        // Optioneel: alleen rijen met recente OrderDate updaten (sneller/veiliger)
        if (orderDateColIdx !== -1 && row[orderDateColIdx]) {
            const od = new Date(row[orderDateColIdx]);
            if (!isNaN(od.getTime()) && od < cutoff) {
                continue;
            }
        }

        const newStatus = statusByOrderId[orderId];
        if (!newStatus) continue;

        matched++;
        const oldStatus = String(row[statusColIdx] || '');
        if (oldStatus !== newStatus) {
            row[statusColIdx] = newStatus;
            changed++;
        }
    }

    if (changed > 0) {
        // We schrijven alleen de status-kolom terug voor alle rijen (bulk), maar met de aangepaste values-array.
        // Dit is sneller dan cell-by-cell updates.
        const statusColValues = values.map(r => [r[statusColIdx]]);
        ordersSheet.getRange(2, statusColIdx + 1, statusColValues.length, 1).setValues(statusColValues);
    }

    Logger.log(`Status update klaar. Matched rijen (binnen periode): ${matched}. Gewijzigde statuses: ${changed}.`);
}

