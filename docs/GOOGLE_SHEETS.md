# Google Sheets tracker

The default tracker is an Excel file on your computer. Google Sheets is useful when you want to see the tracker on your phone.

## 1. Install the extra

```bash
~/.jobpilot/venv/bin/pip install "gspread>=6" "google-auth>=2.20"
```

or install with `JOBPILOT_EXTRAS=gsheets`.

## 2. Create a service account

1. Open console.cloud.google.com and create a project (any name)
2. APIs and services > Library: enable **Google Sheets API** and **Google Drive API**
3. APIs and services > Credentials > Create credentials > Service account. No roles needed
4. Open the service account > Keys > Add key > JSON. A file downloads
5. Move it into your workspace, for example `~/JobPilot/google-service-account.json`. The workspace `.gitignore` already ignores it

## 3. Create and share the sheet

1. Create an empty Google Sheet
2. Share it with the service account email (looks like `name@project.iam.gserviceaccount.com`) as Editor
3. Copy the ID from the URL: `docs.google.com/spreadsheets/d/<THIS PART>/edit`

## 4. Point JobPilot at it

Re-run `jobpilot setup` and pick Google Sheets, or edit `profile.yaml`:

```yaml
tracker:
  backend: gsheets
  gsheet_id: 1AbC...xyz
  service_account_json: google-service-account.json
```

Then `jobpilot doctor`. JobPilot creates the tabs and headers on first use.

## Moving from Excel to Sheets

Open the xlsx in Google Sheets (File > Import > Replace spreadsheet) into the sheet you shared, then switch the backend. Tab names and columns are the same.
