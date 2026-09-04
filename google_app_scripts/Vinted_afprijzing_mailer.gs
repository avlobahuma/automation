const VINTED_AFPRIJZING_CONFIG = {
  spreadsheet_id: '1wYOlZmos_U6PQk-TDbzBdGTxU7cyFn9D06WCu9qshbs',
  sheet_gid: 0,
  recipient_email: 'kristiaan@krstn.nl',
  email_subject: 'Spreadsheet overzicht',
  max_rows: 200,
  trigger_hour: 8,
  filter_header: '',
  filter_value: ''
};

function vinted_afprijzing_mailer() {
  const started = new Date();
  const config = VINTED_AFPRIJZING_CONFIG;
  Logger.log('Starting script...');
  Logger.log('Spreadsheet ID: ' + config.spreadsheet_id);
  Logger.log('Sheet gid: ' + config.sheet_gid);

  const spreadsheet = SpreadsheetApp.openById(config.spreadsheet_id);
  const sheet = vinted_get_sheet_by_gid_(spreadsheet, config.sheet_gid);
  Logger.log('Opened spreadsheet: ' + spreadsheet.getName());
  Logger.log('Using sheet: ' + sheet.getName());

  const values = sheet.getDataRange().getDisplayValues();
  if (!values.length) {
    throw new Error('Sheet "' + sheet.getName() + '" is empty.');
  }

  const headers = values[0];
  const data_rows = values.slice(1).filter(row => row.some(cell => String(cell).trim() !== ''));
  Logger.log('Found ' + data_rows.length + ' data rows');

  const filtered_rows = vinted_apply_filter_(headers, data_rows, config.filter_header, config.filter_value);
  Logger.log('Rows after filter: ' + filtered_rows.length);

  const truncated = filtered_rows.length > config.max_rows;
  const rows_for_email = truncated ? filtered_rows.slice(0, config.max_rows) : filtered_rows;
  const recipient = String(config.recipient_email || '').trim();
  if (!recipient) {
    throw new Error('recipient_email is empty. Set it in VINTED_AFPRIJZING_CONFIG.');
  }
  const subject = config.email_subject + ' — ' + spreadsheet.getName();
  const html_body = vinted_build_email_html_(spreadsheet, sheet, headers, rows_for_email, filtered_rows.length, truncated);
  const text_body = vinted_build_email_text_(spreadsheet, sheet, headers, rows_for_email, filtered_rows.length, truncated);

  Logger.log('Sending email to: ' + recipient);
  Logger.log('Including ' + rows_for_email.length + ' of ' + filtered_rows.length + ' rows');
  Logger.log('Remaining MailApp quota: ' + MailApp.getRemainingDailyQuota());

  GmailApp.sendEmail(recipient, subject, text_body, {
    htmlBody: html_body,
    name: 'Vinted afprijzing mailer'
  });

  const duration = ((new Date()) - started) / 1000;
  Logger.log('Finished sending spreadsheet email to ' + recipient);
  Logger.log('Total execution time: ' + duration.toFixed(2) + ' seconds');
}

function vinted_afprijzing_setup_trigger() {
  const handler = 'vinted_afprijzing_mailer';
  const triggers = ScriptApp.getProjectTriggers();
  for (let i = 0; i < triggers.length; i++) {
    const name = triggers[i].getHandlerFunction();
    if (name === handler || name === 'send_spreadsheet_email') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }

  ScriptApp.newTrigger(handler)
    .timeBased()
    .atHour(VINTED_AFPRIJZING_CONFIG.trigger_hour)
    .everyDays(1)
    .inTimezone(Session.getScriptTimeZone())
    .create();

  Logger.log('Daily trigger created for ' + handler + ' at hour ' + VINTED_AFPRIJZING_CONFIG.trigger_hour);
}

function vinted_get_sheet_by_gid_(spreadsheet, gid) {
  const sheets = spreadsheet.getSheets();
  const target = Number(gid);
  for (let i = 0; i < sheets.length; i++) {
    if (sheets[i].getSheetId() === target) {
      return sheets[i];
    }
  }
  throw new Error('Sheet with gid ' + gid + ' was not found in spreadsheet ' + spreadsheet.getName() + '.');
}

function vinted_apply_filter_(headers, rows, filter_header, filter_value) {
  const header = String(filter_header || '').trim();
  if (!header) {
    return rows;
  }

  const column_index = headers.findIndex(value => String(value).trim() === header);
  if (column_index === -1) {
    throw new Error('filter_header "' + header + '" was not found. Available headers: ' + headers.join(', '));
  }

  const expected = String(filter_value || '').trim().toLowerCase();
  Logger.log('Filtering column "' + header + '" equals "' + filter_value + '"');
  return rows.filter(row => String(row[column_index] || '').trim().toLowerCase() === expected);
}

function vinted_build_email_text_(spreadsheet, sheet, headers, rows, total_rows, truncated) {
  const summary = truncated
    ? 'Showing first ' + rows.length + ' of ' + total_rows + ' rows.'
    : 'Showing all ' + total_rows + ' rows.';
  const lines = [
    spreadsheet.getName(),
    sheet.getName(),
    spreadsheet.getUrl() + '#gid=' + sheet.getSheetId(),
    summary,
    ''
  ];
  if (!rows.length) {
    lines.push('No rows matched the current settings.');
    return lines.join('\n');
  }
  lines.push(headers.join('\t'));
  for (let r = 0; r < rows.length; r++) {
    lines.push(rows[r].join('\t'));
  }
  return lines.join('\n');
}

function vinted_build_email_html_(spreadsheet, sheet, headers, rows, total_rows, truncated) {
  const spreadsheet_url = spreadsheet.getUrl() + '#gid=' + sheet.getSheetId();
  const summary = truncated
    ? 'Showing first ' + rows.length + ' of ' + total_rows + ' rows.'
    : 'Showing all ' + total_rows + ' rows.';

  let html = '';
  html += '<p>Spreadsheet: <a href="' + vinted_escape_html_(spreadsheet_url) + '">' + vinted_escape_html_(spreadsheet.getName()) + '</a></p>';
  html += '<p>Sheet: ' + vinted_escape_html_(sheet.getName()) + '</p>';
  html += '<p>' + vinted_escape_html_(summary) + '</p>';

  if (!rows.length) {
    html += '<p>No rows matched the current settings.</p>';
    return html;
  }

  html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px">';
  html += '<thead><tr>';
  for (let c = 0; c < headers.length; c++) {
    html += '<th style="background:#f2f2f2;text-align:left">' + vinted_escape_html_(headers[c]) + '</th>';
  }
  html += '</tr></thead><tbody>';

  for (let r = 0; r < rows.length; r++) {
    html += '<tr>';
    for (let c = 0; c < headers.length; c++) {
      html += '<td>' + vinted_escape_html_(rows[r][c]) + '</td>';
    }
    html += '</tr>';
  }

  html += '</tbody></table>';
  return html;
}

function vinted_escape_html_(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
