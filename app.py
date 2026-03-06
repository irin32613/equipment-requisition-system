from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///equipment.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
THAI_TZ = pytz.timezone('Asia/Bangkok')


# โมเดลสำหรับ Stock อุปกรณ์
class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    quantity = db.Column(db.Integer, nullable=False)
    
    def __repr__(self):
        return f'<Equipment {self.name}>'

# โมเดลสำหรับประวัติการเบิกและเติม
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(20), nullable=False)
    employee_id = db.Column(db.String(50), nullable=False)
    employee_name = db.Column(db.String(100), nullable=False)
    equipment_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_type': self.transaction_type,
            'employee_id': self.employee_id,
            'employee_name': self.employee_name,
            'equipment_name': self.equipment_name,
            'quantity': self.quantity,
            'note': self.note,
            'created_by': self.created_by,
            'timestamp': self.timestamp.strftime('%d/%m/%Y %H:%M:%S')
        }
    
    def __repr__(self):
        return f'<Requisition {self.employee_name} - {self.equipment_name}>'

# สร้างตารางและข้อมูลเริ่มต้น
with app.app_context():
    db.create_all()
    
    # เพิ่มข้อมูลอุปกรณ์เริ่มต้นถ้ายังไม่มี
    if Equipment.query.count() == 0:
        initial_equipment = [
            Equipment(name='คอมพิวเตอร์', quantity=10),
            Equipment(name='เมาส์', quantity=50),
            Equipment(name='คีย์บอร์ด', quantity=30),
            Equipment(name='จอภาพ', quantity=15),
            Equipment(name='เครื่องพิมพ์', quantity=5)
        ]
        db.session.add_all(initial_equipment)
        db.session.commit()

# หน้าแรก - แสดง Stock ปัจจุบัน
@app.route('/')
def index():
    equipments = Equipment.query.all()
    return render_template('index.html', equipments=equipments)

# ฟอร์มเบิกอุปกรณ์
@app.route('/requisition', methods=['GET', 'POST'])
def requisition_form():
    equipments = Equipment.query.all()
    
    if request.method == 'POST':
        employee_id = request.form['employee_id']
        employee_name = request.form['employee_name']
        equipment_name = request.form['equipment']
        quantity = int(request.form['quantity'])
        
        # ตรวจสอบ Stock
        equipment = Equipment.query.filter_by(name=equipment_name).first()
        
        if equipment and equipment.quantity >= quantity:
            # อัปเดต Stock
            equipment.quantity -= quantity
            
            # บันทึกประวัติการเบิก
            new_transaction = Transaction(
                transaction_type='withdraw',
                employee_id=employee_id,
                employee_name=employee_name,
                equipment_name=equipment_name,
                quantity=quantity
            )
            
            db.session.add(new_transaction)
            db.session.commit()
            
            return redirect(url_for('history'))
        else:
            return render_template('requisition_form.html', 
                                 equipments=equipments, 
                                 error='อุปกรณ์ไม่เพียงพอ หรือไม่พบอุปกรณ์')
    
    return render_template('requisition_form.html', equipments=equipments)

# ฟอร์มเติม Stock
@app.route('/restock', methods=['GET', 'POST'])
def restock_form():
    equipments = Equipment.query.all()

    if request.method == 'POST':
        employee_id = request.form['employee_id']
        employee_name = request.form['employee_name']
        equipment_name = request.form['equipment']
        quantity = int(request.form['quantity'])
        
        # ตรวจสอบ Stock
        equipment = Equipment.query.filter_by(name=equipment_name).first()
        
        if equipment and equipment.quantity >= quantity:
            # อัปเดต Stock
            equipment.quantity += quantity

            # บันทึกประวัติการเติม
            new_transaction = Transaction(
                transaction_type='stock_in',
                employee_id=employee_id,
                employee_name=employee_name,
                equipment_name=equipment_name,
                quantity=quantity
            )
            
            db.session.add(new_transaction)
            db.session.commit()
            
            return redirect(url_for('history'))
        else:
            return render_template('restock_form.html', 
                                 equipments=equipments, 
                                 error='ไม่พบอุปกรณ์')
    
    return render_template('restock_form.html', equipments=equipments)

# หน้าค้นหาประวัติการเบิกและเติม
@app.route('/history', methods=['GET', 'POST'])
def history():
    # ดึงข้อมูลอุปกรณ์ทั้งหมดสำหรับ dropdown
    equipments = Equipment.query.all()
    
    # รับค่าจากฟอร์มค้นหา
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    equipment_filter = request.args.get('equipment', '')
    type_filter = request.args.get('type', '')
    
    # สร้าง query พื้นฐาน เรียงรายการล่าสุดไปเก่าสุด
    query = Transaction.query
    
    # กรองตามวันที่ (ถ้ามี)
    if start_date and end_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        # เพิ่มเวลาสิ้นสุดเป็น 23:59:59 ของวันนั้น
        end = end.replace(hour=23, minute=59, second=59)
        query = query.filter(Transaction.timestamp.between(start, end))
    elif start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(Transaction.timestamp >= start)
    elif end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d')
        end = end.replace(hour=23, minute=59, second=59)
        query = query.filter(Transaction.timestamp <= end)
    
    # กรองตามอุปกรณ์ (ถ้ามี)
    if equipment_filter:
        query = query.filter(Transaction.equipment_name == equipment_filter)
    
    # กรองตามประเภท
    if type_filter:
        query = query.filter(Transaction.transaction_type == type_filter)

    # เรียงตามเวลาล่าสุดและดึงข้อมูล
    requisitions = query.order_by(Transaction.timestamp.desc()).all()


    for r in requisitions:
        r.timestamp = r.timestamp.replace(tzinfo=pytz.utc).astimezone(THAI_TZ)
    
    return render_template('history.html', 
                         requisitions=requisitions,
                         equipments=equipments,
                         start_date=start_date,
                         end_date=end_date,
                         equipment_filter=equipment_filter,
                         type_filter=type_filter)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)