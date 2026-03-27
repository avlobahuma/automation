// One-time setup helper to store the ChannelEngine API key securely
// in Script Properties. Run this once (and then remove or comment
// out the hardcoded key) so the key is no longer in source code.
function setChannelEngineApiKey() {
    const apiKey = 'PASTE_YOUR_CHANNELENGINE_API_KEY_HERE';
    PropertiesService.getScriptProperties().setProperty('CHANNELENGINE_API_KEY', apiKey);
}

/**
 * Hulpfunctie om te zien welke velden ChannelEngine teruggeeft
 * (order-level + line-level). Handig om te checken of EAN/GTIN aanwezig is.
 *
 * Run deze functie handmatig en bekijk de Execution logs.
 */
function debugLogAvailableOrderFields() {
    const scriptProps = PropertiesService.getScriptProperties();
    const apiKey = scriptProps.getProperty('CHANNELENGINE_API_KEY');
    if (!apiKey) {
        throw new Error('CHANNELENGINE_API_KEY is not set. Run setChannelEngineApiKey() once to store it in Script Properties.');
    }

    const fromDate = new Date();
    fromDate.setDate(fromDate.getDate() - 30);
    const startDate = fromDate.toISOString().split('T')[0];
    const endDate = new Date();
    endDate.setDate(endDate.getDate() - 1);
    const formattedEndDate = endDate.toISOString().split('T')[0];

    const url = `https://forelle.channelengine.net/api/v2/orders?apikey=${apiKey}&from=${startDate}&to=${formattedEndDate}&page=1`;
    const response = UrlFetchApp.fetch(url);
    const data = JSON.parse(response.getContentText());

    const firstOrder = data && data.Content && data.Content.length ? data.Content[0] : null;
    if (!firstOrder) {
        Logger.log('Geen orders gevonden in deze periode (debug).');
        return;
    }

    Logger.log(`Order keys (${Object.keys(firstOrder).length}): ${Object.keys(firstOrder).sort().join(', ')}`);

    const firstLine = firstOrder.Lines && firstOrder.Lines.length ? firstOrder.Lines[0] : null;
    if (firstLine) {
        Logger.log(`Line keys (${Object.keys(firstLine).length}): ${Object.keys(firstLine).sort().join(', ')}`);
    } else {
        Logger.log('Eerste order heeft geen Lines (debug).');
    }

    // Extra: log mogelijke "barcode"-achtige velden als ze bestaan
    const interesting = ['Gtin', 'GTIN', 'Ean', 'EAN', 'Barcode', 'ProductGtin', 'MerchantProductGtin', 'ProductEan', 'MerchantProductEan'];
    interesting.forEach((k) => {
        if (firstLine && Object.prototype.hasOwnProperty.call(firstLine, k)) {
            Logger.log(`Line.${k} = ${firstLine[k]}`);
        }
        if (Object.prototype.hasOwnProperty.call(firstOrder, k)) {
            Logger.log(`Order.${k} = ${firstOrder[k]}`);
        }
    });
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
    const portiSheet = ss.getSheetByName("Porti");
    const dataSheet = ss.getSheetByName("data");

    const normalizeGtin = (value) => {
        if (value === null || value === undefined) return "";
        const s = String(value).trim();
        if (!s) return "";
        const stripped = s.replace(/^0+/, "");
        return stripped || "0";
    };

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

    // Lookup-tabel voor COGS op basis van EAN/GTIN uit tabblad data.
    // Verwacht:
    // - Kolom A = EAN
    // - Kolom met header "cogs" = inkoopprijs
    // - Kolom met header "Conversion benchmark product group" = productgroep (o.a. "Sportschoenen")
    const cogsLookup = {};
    let dataCogsColIdx = -1;
    let dataProductGroupColIdx = -1;
    if (dataSheet) {
        const dataValues = dataSheet.getDataRange().getValues();
        const dataHeaders = dataValues.length ? dataValues[0] : [];
        dataCogsColIdx = dataHeaders.findIndex(h => String(h || "").trim().toLowerCase() === "cogs");
        dataProductGroupColIdx = dataHeaders.findIndex(h => String(h || "").trim() === "Conversion benchmark product group");

        for (let i = 1; i < dataValues.length; i++) {
            const ean = normalizeGtin(dataValues[i][0]);
            if (!ean) continue;
            const baseCogs = dataCogsColIdx >= 0 ? dataValues[i][dataCogsColIdx] : "";
            const productGroup = dataProductGroupColIdx >= 0 ? dataValues[i][dataProductGroupColIdx] : "";
            cogsLookup[ean] = { baseCogs, productGroup };
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
        "IsBusinessOrder", "Gtin", "Cogs", "Fulfillment", "Verzendkosten"
    ];

    // Controleer en stel headers in op rij 1
    const existingHeaders = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
    const headersMissing = existingHeaders.some((header, index) => header !== headers[index]);
    if (headersMissing) {
        sheet.clear(); // Maak de sheet leeg
        sheet.appendRow(headers); // Stel nieuwe headers in
    }

    let page = 1;
    let totalPages = 1;      // Placeholder
    const allRows = [];      // Alle rijen die we gaan wegschrijven

    try {
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
                const fulfillment = 3;

                const gtin = normalizeGtin(line.Gtin);
                const cogsRow = gtin ? cogsLookup[gtin] : undefined;
                const baseCogs = cogsRow ? cogsRow.baseCogs : "";
                const productGroup = cogsRow ? String(cogsRow.productGroup || "").trim() : "";
                const multiplier = productGroup === "Sportschoenen" ? 1.20 : 1.15;
                const baseCogsNumber = baseCogs === "" || baseCogs === null || baseCogs === undefined ? NaN : Number(String(baseCogs).toString().replace(",", "."));
                const cogs = isNaN(baseCogsNumber) ? "" : (baseCogsNumber * multiplier);

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
                    gtin,                                   // Gtin (zonder voorloopnullen)
                    cogs,                                   // Cogs (inkoopprijs * factor)
                    fulfillment,                            // Fulfillment (vaste waarde per orderregel)
                    verzendkosten                           // Verzendkosten (op basis van Porti)
                ];

                allRows.push(row);
                });
            }

            page++; // Volgende pagina
        } while (page <= totalPages);
    } catch (e) {
        Logger.log(`FOUT tijdens ophalen orders. Orders-tabblad blijft ongewijzigd. Error: ${e && e.stack ? e.stack : e}`);
        throw e;
    }

    // Pas overschrijven als we daadwerkelijk resultaten hebben opgehaald.
    // Zo voorkom je dat een mislukte run het Orders-tabblad leeg achterlaat.
    if (allRows.length > 0) {
        const lastRowOrders = sheet.getLastRow();
        if (lastRowOrders > 1) {
            sheet.getRange(2, 1, lastRowOrders - 1, headers.length).clearContent();
        }
        sheet.getRange(2, 1, allRows.length, headers.length).setValues(allRows);
    } else if (ENABLE_VERBOSE_LOG) {
        Logger.log('Geen orderregels opgehaald (allRows=0). Orders-tabblad is niet overschreven.');
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
