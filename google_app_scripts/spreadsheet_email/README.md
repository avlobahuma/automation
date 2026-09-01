# Spreadsheet email digest

Google Apps Script that reads [this spreadsheet](https://docs.google.com/spreadsheets/d/1wYOlZmos_U6PQk-TDbzBdGTxU7cyFn9D06WCu9qshbs/edit?gid=0#gid=0) and emails the contents.

Upload from Cursor or a local terminal with **clasp**.

## One-time Google setup

1. Enable the Apps Script API: https://script.google.com/home/usersettings
2. Open a terminal in this folder:

```bash
cd google_app_scripts/spreadsheet_email
npm install
npx clasp login
```

`clasp login` opens a browser. Sign in with the Google account that can open the spreadsheet.

3. Create a bound Apps Script project on the spreadsheet, or reuse an existing one.

Create a new bound project:

```bash
npm run create
```

Or paste an existing Script ID into `.clasp.json`:

```json
{
  "scriptId": "YOUR_SCRIPT_ID",
  "rootDir": "."
}
```

Find the Script ID in the Apps Script editor: Project Settings → IDs.

4. Upload:

```bash
npm run push
```

5. In the Apps Script editor, run `send_spreadsheet_email` once and approve the permissions.
6. Optional: run `setup_daily_trigger` for a daily email at 08:00 Europe/Amsterdam.

## Upload after code changes

```bash
cd google_app_scripts/spreadsheet_email
npm run push
```

## Config

Edit the constants at the top of `spreadsheet_email_digest.gs`:

| Setting | Meaning |
| --- | --- |
| `RECIPIENT_EMAIL` | Leave empty to email the Google account that owns the script |
| `EMAIL_SUBJECT` | Subject prefix |
| `MAX_ROWS` | Max table rows in the email |
| `TRIGGER_HOUR` | Hour for the daily trigger (0-23) |
| `FILTER_HEADER` | Optional column header to filter on |
| `FILTER_VALUE` | Required value when `FILTER_HEADER` is set |
