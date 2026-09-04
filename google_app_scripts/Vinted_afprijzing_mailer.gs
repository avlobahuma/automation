const SPREADSHEET_ID = '1wYOlZmos_U6PQk-TDbzBdGTxU7cyFn9D06WCu9qshbs';
const SHEET_GID = 0;
const RECIPIENT_EMAIL = 'kristiaan@krstn.nl';
const EMAIL_SUBJECT = 'Spreadsheet overzicht';
const MAX_ROWS = 200;
const TRIGGER_HOUR = 8;
const FILTER_HEADER = '';
const FILTER_VALUE = '';

function send_spreadsheet_email() {
  const started = new Date();
  Logger.log('Starting script...');
  Logger.log('Spreadsheet ID: ' + SPREADSHEET_ID);
  Logger.log('Sheet gid: ' + SHEET_GID);

  const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = get_sheet_by_gid_(spreadsheet, SHEET_GID);
  Logger.log('Opened spreadsheet: ' + spreadsheet.getName());
  Logger.log('Using sheet: ' + sheet.getName());

  const values = sheet.getDataRange().getDisplayValues();
  if (!values.length) {
    throw new Error('Sheet "' + sheet.getName() + '" is empty.');
  }

  const headers = values[0];
  const data_rows = values.slice(1).filter(row => row.some(cell => String(cell).trim() !== ''));
  Logger.log('Found ' + data_rows.length + ' data rows');

  const filtered_rows = apply_filter_(headers, data_rows);
  Logger.log('Rows after filter: ' + filtered_rows.length);

  const truncated = filtered_rows.length > MAX_ROWS;
  const rows_for_email = truncated ? filtered_rows.slice(0, MAX_ROWS) : filtered_rows;
  const recipient = get_recipient_email_();
  const subject = EMAIL_SUBJECT + ' — ' + spreadsheet.getName();
  const html_body = build_email_html_(spreadsheet, sheet, headers, rows_for_email, filtered_rows.length, truncated);
  const text_body = build_email_text_(spreadsheet, sheet, headers, rows_for_email, filtered_rows.length, truncated);

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

function setup_daily_trigger() {
  const triggers = ScriptApp.getProjectTriggers();
  for (let i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'send_spreadsheet_email') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }

  ScriptApp.newTrigger('send_spreadsheet_email')
    .timeBased()
    .atHour(TRIGGER_HOUR)
    .everyDays(1)
    .inTimezone(Session.getScriptTimeZone())
    .create();

  Logger.log('Daily trigger created for send_spreadsheet_email at hour ' + TRIGGER_HOUR);
}

function get_recipient_email_() {
  const configured = String(RECIPIENT_EMAIL || '').trim();
  if (!configured) {
    throw new Error('RECIPIENT_EMAIL is empty. Set it at the top of the script.');
  }
  return configured;
}

function get_sheet_by_gid_(spreadsheet, gid) {
  const sheets = spreadsheet.getSheets();
  const target = Number(gid);
  for (let i = 0; i < sheets.length; i++) {
    if (sheets[i].getSheetId() === target) {
      return sheets[i];
    }
  }
  throw new Error('Sheet with gid ' + gid + ' was not found in spreadsheet ' + spreadsheet.getName() + '.');
}

function apply_filter_(headers, rows) {
  const header = String(FILTER_HEADER || '').trim();
  if (!header) {
    return rows;
  }

  const column_index = headers.findIndex(value => String(value).trim() === header);
  if (column_index === -1) {
    throw new Error('FILTER_HEADER "' + header + '" was not found. Available headers: ' + headers.join(', '));
  }

  const expected = String(FILTER_VALUE || '').trim().toLowerCase();
  Logger.log('Filtering column "' + header + '" equals "' + FILTER_VALUE + '"');
  return rows.filter(row => String(row[column_index] || '').trim().toLowerCase() === expected);
}

function build_email_text_(spreadsheet, sheet, headers, rows, total_rows, truncated) {
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

function build_email_html_(spreadsheet, sheet, headers, rows, total_rows, truncated) {
  const spreadsheet_url = spreadsheet.getUrl() + '#gid=' + sheet.getSheetId();
  const summary = truncated
    ? 'Showing first ' + rows.length + ' of ' + total_rows + ' rows.'
    : 'Showing all ' + total_rows + ' rows.';

  let html = '';
  html += '<p>Spreadsheet: <a href="' + escape_html_(spreadsheet_url) + '">' + escape_html_(spreadsheet.getName()) + '</a></p>';
  html += '<p>Sheet: ' + escape_html_(sheet.getName()) + '</p>';
  html += '<p>' + escape_html_(summary) + '</p>';

  if (!rows.length) {
    html += '<p>No rows matched the current settings.</p>';
    return html;
  }

  html += '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px">';
  html += '<thead><tr>';
  for (let c = 0; c < headers.length; c++) {
    html += '<th style="background:#f2f2f2;text-align:left">' + escape_html_(headers[c]) + '</th>';
  }
  html += '</tr></thead><tbody>';

  for (let r = 0; r < rows.length; r++) {
    html += '<tr>';
    for (let c = 0; c < headers.length; c++) {
      html += '<td>' + escape_html_(rows[r][c]) + '</td>';
    }
    html += '</tr>';
  }

  html += '</tbody></table>';
  return html;
}

function escape_html_(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
