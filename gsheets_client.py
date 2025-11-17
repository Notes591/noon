import gspread

def open_sheet_from_service_account(sa_json_path, spreadsheet_id, sheet_name):
    gc = gspread.service_account(filename=sa_json_path)
    sh = gc.open_by_key(spreadsheet_id)
    ws = sh.worksheet(sheet_name)
    return ws
