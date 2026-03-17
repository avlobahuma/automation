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
    // Vereenvoudigd: altijd vaste periode ophalen (laatste 90 dagen)
    const fromDate = new Date();
    fromDate.setDate(fromDate.getDate() - 90);
    const startDate = fromDate.toISOString().split('T')[0];
    const endDate = new Date();    // Einddatum (gisteren)
    endDate.setDate(endDate.getDate() - 1);
    const formattedEndDate = endDate.toISOString().split('T')[0]; // Formatteer als YYYY-MM-DD

    const baseUrl = `https://forelle.channelengine.net/api/v2/orders?apikey=${apiKey}&from=${startDate}&to=${formattedEndDate}`;

    if (ENABLE_VERBOSE_LOG) {
        Logger.log(`Start fetchAndUpdateOrders`);
        Logger.log(`Vandaag (now) = ${new Date().toISOString().split('T')[0]}`);
        Logger.log(`Datum-range (die wordt opgehaald): from=${startDate}, to=${formattedEndDate}`);
    }

    const start = new Date(); // Starttijd voor laadtijdlog
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheetByName("Orders") || ss.insertSheet("Orders");
    const logSheet = ss.getSheetByName("log") || ss.insertSheet("log");
    const masterSheet = ss.getSheetByName("Master");
    const portiSheet = ss.getSheetByName("Porti");

    // Werk in tabblad Master voor alle regels de Fulfillment-kolom bij naar een vaste waarde van 3 euro
    if (masterSheet) {
        const lastRow = masterSheet.getLastRow();
        if (lastRow >= 2) {
            const numRows = lastRow - 1; // exclusief header
            const fulfillmentValues = Array.from({ length: numRows }, () => [3]);
            masterSheet.getRange(2, 4, numRows, 1).setValues(fulfillmentValues); // kolom D = Fulfillment
        }
    }

    // Bouw een lookup-tabel voor verzendkosten op basis van CountryIso uit tabblad Porti
    // Verwacht structuur Porti:
    // Kolom A: CountryIso
    // Kolom B: Verzendkosten
    const shippingLookup = {};
    if (portiSheet) {
        const portiData = portiSheet.getDataRange().getValues();
        for (let i = 1; i < portiData.length; i++) { // sla header over
            const countryIso = String(portiData[i][0] || "").trim();
            const cost = portiData[i][1];
            if (countryIso) {
                shippingLookup[countryIso] = cost;
            }
        }
    }

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
        "IsBusinessOrder", "Verzendkosten"
    ];

    // Controleer en stel headers in op rij 1
    const existingHeaders = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
    const headersMissing = existingHeaders.some((header, index) => header !== headers[index]);
    if (headersMissing) {
        sheet.clear(); // Maak de sheet leeg
        sheet.appendRow(headers); // Stel nieuwe headers in
    }

    // We bouwen het Orders-tabblad elke run volledig opnieuw op
    // (alle rijen onder de header worden eerst leeggemaakt).
    const lastRowOrders = sheet.getLastRow();
    if (lastRowOrders > 1) {
        sheet.getRange(2, 1, lastRowOrders - 1, headers.length).clearContent();
    }

    let page = 1;
    let totalPages = 1;      // Placeholder
    const allRows = [];      // Alle rijen die we gaan wegschrijven

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

                // Verzendkosten lookup op basis van CountryIso (vergelijkbaar met VLOOKUP op tabblad Porti)
                const countryIso = order.ShippingAddress.CountryIso;
                const verzendkosten = shippingLookup[countryIso] !== undefined ? shippingLookup[countryIso] : "";

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
                    order.IsBusinessOrder,                  // IsBusinessOrder
                    verzendkosten                           // Verzendkosten (op basis van Porti)
                ];

                allRows.push(row);
            });
        }

        page++; // Volgende pagina
    } while (page <= totalPages);

    // Schrijf alle opgehaalde orderregels in één keer weg (vanaf rij 2)
    if (allRows.length > 0) {
        sheet.getRange(2, 1, allRows.length, headers.length).setValues(allRows);
    }

    // Sorteer op order-ID (kolom A) aflopend
    sheet.sort(1, false);

    // Eindtijd en logging
    const end = new Date();
    const duration = (end - start) / 1000; // Laadtijd in seconden
    const totalRecords = allRows.length;

    // Schrijf logwaarden in vaste cellen (overschrijven per run)
    logSheet.getRange('B1').setValue(new Date());
    logSheet.getRange('B2').setValue(totalRecords);
    // Duration als tijd (hh:mm:ss): seconden omrekenen naar dag-fractie
    logSheet.getRange('B3').setValue(duration / 86400);
    logSheet.getRange('B3').setNumberFormat('hh:mm:ss');

    // Laatste log in Apps Script Logger
    Logger.log(`Records: ${totalRecords}, Totaal laadtijd: ${duration} seconden`);

    // Incrementiële sync niet meer gebruikt; we slaan geen laatste syncdatum meer op.
}
