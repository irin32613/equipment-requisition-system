from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

app = Flask(__name__)
THAI_TZ = pytz.timezone('Asia/Bangkok')

# ---------------- GOOGLE SHEETS CONNECTION ----------------

scope = [
"https://spreadsheets.google.com/feeds",
"https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet_equipment = client.open("EquipmentDatabase").worksheet("equipment")
sheet_transaction = client.open("EquipmentDatabase").worksheet("transaction")

# ----------------------------------------------------------

# หน้าแรก - แสดง Stock ปัจจุบัน
@app.route('/')
def index():
    equipments = sheet_equipment.get_all_records()
    return render_template('index.html', equipments=equipments)


# ฟอร์มเบิกอุปกรณ์
@app.route('/requisition', methods=['GET', 'POST'])
def requisition_form():
    equipments = sheet_equipment.get_all_records()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        employee_name = request.form['employee_name']
        equipment_name = request.form['equipment']
        quantity = int(request.form['quantity'])

        cell = sheet_equipment.find(equipment_name)

        if cell:
            row = cell.row
            current_qty = int(sheet_equipment.cell(row, 2).value)

            if current_qty >= quantity:
                new_qty = current_qty - quantity

                # update stock
                sheet_equipment.update_cell(row, 2, new_qty)

                # บันทึก transaction
                sheet_transaction.append_row([
                    'เบิก',
                    employee_id,
                    employee_name,
                    equipment_name,
                    quantity,
                    datetime.now(THAI_TZ).strftime('%Y-%m-%d %H:%M:%S')
                ],table_range="A1")

                print("✅ บันทึกสำเร็จ")

                return redirect(url_for('history'))

        return render_template(
            'requisition_form.html',
            equipments=equipments,
            error='อุปกรณ์ไม่เพียงพอ หรือไม่พบอุปกรณ์'
        )

    return render_template('requisition_form.html', equipments=equipments)


# ฟอร์มเติม Stock
@app.route('/restock', methods=['GET', 'POST'])
def restock_form():
    equipments = sheet_equipment.get_all_records()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        employee_name = request.form['employee_name']
        equipment_name = request.form['equipment']
        quantity = int(request.form['quantity'])

        cell = sheet_equipment.find(equipment_name)

        if cell:
            row = cell.row
            current_qty = int(sheet_equipment.cell(row, 2).value)

            new_qty = current_qty + quantity

            # update stock
            sheet_equipment.update_cell(row, 2, new_qty)

            # บันทึก transaction
            sheet_transaction.append_row([
                'เติม',
                employee_id,
                employee_name,
                equipment_name,
                quantity,
                datetime.now(THAI_TZ).strftime('%Y-%m-%d %H:%M:%S')
            ],table_range="A1")

            return redirect(url_for('history'))

        return render_template(
            'restock_form.html',
            equipments=equipments,
            error='ไม่พบอุปกรณ์'
        )

    return render_template('restock_form.html', equipments=equipments)


# หน้าค้นหาประวัติการเบิกและเติม
@app.route('/history', methods=['GET', 'POST'])
def history():

    equipments = sheet_equipment.get_all_records()
    requisitions = sheet_transaction.get_all_records()

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    equipment_filter = request.args.get('equipment', '')
    type_filter = request.args.get('type', '')

    filtered = []

    for r in requisitions:

        timestamp = datetime.strptime(r['timestamp'], '%Y-%m-%d %H:%M:%S')

        if start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            if timestamp < start:
                continue

        if end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            if timestamp > end:
                continue

        if equipment_filter and r['equipment_name'] != equipment_filter:
            continue

        if type_filter and r['transaction_type'] != type_filter:
            continue

        r['timestamp'] = timestamp

        filtered.append(r)

    filtered = sorted(filtered, key=lambda x: x['timestamp'], reverse=True)

    return render_template(
        'history.html',
        requisitions=filtered,
        equipments=equipments,
        start_date=start_date,
        end_date=end_date,
        equipment_filter=equipment_filter,
        type_filter=type_filter
    )


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)