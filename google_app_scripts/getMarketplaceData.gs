// One-time setup helper to store the ChannelEngine API key securely
// in Script Properties. Run this once (and then remove or comment
// out the hardcoded key) so the key is no longer in source code.
function setChannelEngineApiKey() {
    const apiKey = 'PASTE_YOUR_CHANNELENGINE_API_KEY_HERE';
    PropertiesService.getScriptProperties().setProperty('CHANNELENGINE_API_KEY', apiKey);
}

function fetchAndUpdateOrders() {
    // Debug-instellingen (makkelijk aan/uit te zetten):
    const ENABLE_VERBOSE_LOG = true;      // Zet op false om extra logging uit te zetten

    const scriptProps = PropertiesService.getScriptProperties();
    const apiKey = scriptProps.getProperty('CHANNELENGINE_API_KEY');
    if (!apiKey) {
        throw new Error('CHANNELENGINE_API_KEY is not set. Run setChannelEngineApiKey() once to store it in Script Properties.');
    }

    // Start- en einddatums instellen
    // Gebruik de laatste sync-datum uit Script Properties zodat we
    // alleen nieuwe/gewijzigde orders ophalen in plaats van alles.
    const lastSyncDate = scriptProps.getProperty('CHANNELENGINE_LAST_SYNC_DATE');
    let startDate;
    if (lastSyncDate) {
        const fromDate = new Date(lastSyncDate);
        fromDate.setDate(fromDate.getDate() - 1); // kleine overlap om gemiste orders te voorkomen
        startDate = fromDate.toISOString().split('T')[0];
    } else {
        // Geen eerdere sync bekend: importeer alleen de laatste 30 dagen
        const fromDate = new Date();
        fromDate.setDate(fromDate.getDate() - 30);
        startDate = fromDate.toISOString().split('T')[0];
    }
    const endDate = new Date();    // Einddatum (gisteren)
    endDate.setDate(endDate.getDate() - 1);
    const formattedEndDate = endDate.toISOString().split('T')[0]; // Formatteer als YYYY-MM-DD

    const baseUrl = `https://forelle.channelengine.net/api/v2/orders?apikey=${apiKey}&from=${startDate}&to=${formattedEndDate}`;

    if (ENABLE_VERBOSE_LOG) {
        Logger.log(`Start fetchAndUpdateOrders`);
        Logger.log(`CHANNELENGINE_LAST_SYNC_DATE = ${lastSyncDate || 'NIET GEZET'}`);
        Logger.log(`Vandaag (now) = ${new Date().toISOString().split('T')[0]}`);
        Logger.log(`Datum-range (die wordt opgehaald): from=${startDate}, to=${formattedEndDate}`);
    }

    const start = new Date(); // Starttijd voor laadtijdlog
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Orders") || SpreadsheetApp.getActiveSpreadsheet().insertSheet("Orders");
    const logSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("log") || SpreadsheetApp.getActiveSpreadsheet().insertSheet("log");
    
    // Optional enrichment sources (currently disabled):
    // - Master tab: adds COGS/Category/Fulfillment based on SKU (MerchantProductNo)
    // - Porti tab: adds shipping cost ("Verzendkosten") based on SKU + destination country
    //
    // To re-enable: uncomment these lines + the lookup sections further down, and
    // also expand the headers + row output to include the extra columns.
    // const masterSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Master");
    // const portiSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Porti");

    // Maak het log-tabblad leeg en zet vaste labels
    logSheet.clear();
    logSheet.getRange('A1').setValue('Date');
    logSheet.getRange('A2').setValue('Records');
    logSheet.getRange('A3').setValue('Duration');

    // Headers instellen
    const headers = [
        "Id", "OrderDate", "ChannelName", "Status", 
        "CountryIso", "Description", "Quantity", "UnitPriceExclVat", 
        "TotalUnitPriceExclVat", "MerchantProductNo", "OriginalSubTotalFee", 
        "IsBusinessOrder"
        // Extra columns from Master/Porti (disabled for now):
        // "Cogs", "Category", "Fulfillment", "Verzendkosten"
    ];

    // Controleer en stel headers in op rij 1
    const existingHeaders = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
    const headersMissing = existingHeaders.some((header, index) => header !== headers[index]);
    if (headersMissing) {
        sheet.clear(); // Maak de sheet leeg
        sheet.appendRow(headers); // Stel nieuwe headers in
    }

    // Haal bestaande order-ID's op
    const existingData = sheet.getDataRange().getValues();
    const existingOrderIds = existingData.slice(1).map(row => row[0]); // Kolom A, vanaf rij 2
    // Bepaal hoogste bestaande order-ID (voor "alleen nieuwe" check)
    const numericExistingIds = existingOrderIds
        .map(id => Number(id))
        .filter(id => !isNaN(id));
    const maxExistingOrderId = numericExistingIds.length > 0 ? Math.max(...numericExistingIds) : 0;

    if (ENABLE_VERBOSE_LOG) {
        Logger.log(`Max bestaande order-ID in sheet = ${maxExistingOrderId || 'GEEN'}`);
    }
    
    // Optional enrichment lookups (currently disabled):
    // - Master lookup maps SKU -> {cogs, category, fulfillment}
    // - Porti lookup maps SKU -> shipping costs per country (based on Porti header row)
    /*
    const masterData = masterSheet.getDataRange().getValues();
    const masterLookup = masterData.slice(1).reduce((acc, row) => {
        acc[row[0]] = { cogs: row[1], category: row[2], fulfillment: row[3] };
        return acc;
    }, {});

    const portiData = portiSheet.getDataRange().getValues();
    const portiHeaders = portiData[0]; // Eerste rij als headers (landen)
    const portiLookup = portiData.slice(1).reduce((acc, row) => {
        const sku = row[0]; // SKU staat in kolom A
        acc[sku] = row.slice(1); // Overige kolommen zijn verzendkosten voor landen
        return acc;
    }, {});
    */

    let page = 1;
    let totalPages = 1;      // Placeholder
    const updates = [];      // Updates voor bestaande orders
    const newOrders = [];    // Nieuwe orders
    let stopFetching = false; // Flag om te stoppen zodra we bij bekende IDs komen

    do {
        const url = `${baseUrl}&page=${page}`;
        if (ENABLE_VERBOSE_LOG) {
            Logger.log(`Ophalen pagina ${page}... URL=${url}`);
        }

        const response = UrlFetchApp.fetch(url);
        const data = JSON.parse(response.getContentText());

        totalPages = Math.ceil(data.TotalCount / 100); // Bereken het totaal aantal pagina's

        if (ENABLE_VERBOSE_LOG) {
            Logger.log(`Pagina ${page}: ${data.Content.length} orders, TotalCount=${data.TotalCount}, berekende totalPages=${totalPages}`);
        }

        for (let i = 0; i < data.Content.length; i++) {
            const order = data.Content[i];
            const orderIdNum = Number(order.Id);

            // Als we al een maximale bestaande ID hebben en deze order-ID is
            // kleiner of gelijk, dan gaan we ervan uit dat alles vanaf hier al bekend is.
            if (maxExistingOrderId && !isNaN(orderIdNum) && orderIdNum <= maxExistingOrderId) {
                if (ENABLE_VERBOSE_LOG) {
                    Logger.log(`Order ${order.Id} <= maxExistingOrderId ${maxExistingOrderId} -> stoppen, vanaf hier geen nieuwe orders meer (pagina ${page}, index ${i})`);
                }
                stopFetching = true;
                break;
            }

            order.Lines.forEach(line => {
                // Berekening voor TotalUnitPriceExclVat
                const totalUnitPriceExclVat = line.Quantity * line.UnitPriceExclVat;

                // Default waardes
                let unitPriceExclVat = line.UnitPriceExclVat;
                let originalSubTotalFee = order.OriginalSubTotalFee || (line.UnitPriceInclVat * 0.15);

                // Maak bedragen negatief als de status RETURNED is
                if (order.Status === 'RETURNED') {
                    unitPriceExclVat = -Math.abs(unitPriceExclVat);
                    originalSubTotalFee = -Math.abs(originalSubTotalFee);
                }

                // Optional enrichment (currently disabled):
                // - Adds cogs/category/fulfillment from Master
                // - Adds shipping cost from Porti by country
                /*
                const masterRow = masterLookup[line.MerchantProductNo] || {};
                const cogs = masterRow.cogs || "N/A";
                const category = masterRow.category || "N/A";
                const fulfillment = masterRow.fulfillment || "N/A";

                const countryIndex = portiHeaders.indexOf(order.ShippingAddress.CountryIso);
                const portiRow = portiLookup[line.MerchantProductNo] || [];
                const verzendkosten = countryIndex > -1 ? portiRow[countryIndex - 1] || "N/A" : "N/A"; // Correctie index (-1 vanwege header)
                */

                const row = [
                    order.Id,                                // Order ID
                    order.OrderDate,                        // Orderdatum
                    order.ChannelName,                      // Kanaalnaam
                    order.Status,                           // Status
                    order.ShippingAddress.CountryIso,       // Landcode
                    line.Description,                       // Productomschrijving
                    line.Quantity,                          // Aantal
                    unitPriceExclVat,                       // Prijs exclusief BTW (mogelijk negatief)
                    totalUnitPriceExclVat,                  // Totaalprijs exclusief BTW
                    line.MerchantProductNo,                 // Merchant Productnummer
                    originalSubTotalFee,                    // Original SubTotal Fee (mogelijk negatief)
                    order.IsBusinessOrder                   // IsBusinessOrder
                    // Extra columns from Master/Porti (disabled for now):
                    // ,cogs, category, fulfillment, verzendkosten
                ];

                if (existingOrderIds.includes(order.Id)) {
                    // Voeg bijwerkte orders toe voor vergelijking
                    updates.push(row);
                } else {
                    // Voeg nieuwe orders toe
                    newOrders.push(row);
                }
            });
        }

        page++; // Volgende pagina
    } while (page <= totalPages && !stopFetching);

    // Update bestaande orders
    updates.forEach(update => {
        const rowIndex = existingOrderIds.indexOf(update[0]) + 2; // Rij-index vinden
        const range = sheet.getRange(rowIndex, 1, 1, update.length);
        range.setValues([update]); // Update specifieke rij
    });

    // Voeg nieuwe orders toe
    if (newOrders.length > 0) {
        sheet.getRange(sheet.getLastRow() + 1, 1, newOrders.length, newOrders[0].length).setValues(newOrders);
    }

    // Sorteer op order-ID (kolom A) aflopend
    sheet.sort(1, false);

    // Eindtijd en logging
    const end = new Date();
    const duration = (end - start) / 1000; // Laadtijd in seconden
    const totalRecords = updates.length + newOrders.length;

    // Schrijf logwaarden in vaste cellen (overschrijven per run)
    logSheet.getRange('B1').setValue(new Date());
    logSheet.getRange('B2').setValue(totalRecords);
    // Duration als tijd (hh:mm:ss): seconden omrekenen naar dag-fractie
    logSheet.getRange('B3').setValue(duration / 86400);
    logSheet.getRange('B3').setNumberFormat('hh:mm:ss');

    // Laatste log in Apps Script Logger
    Logger.log(`Records: ${totalRecords}, Totaal laadtijd: ${duration} seconden`);

    // Sla de laatste succesvolle einddatum op voor een volgende incrementele run
    scriptProps.setProperty('CHANNELENGINE_LAST_SYNC_DATE', formattedEndDate);
}
