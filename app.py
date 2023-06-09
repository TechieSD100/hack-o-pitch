import os
from datetime import datetime

from flask import Flask, redirect, render_template, request, send_from_directory, url_for,jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_security import login_required,login_user,logout_user,auth_required,current_user
from flask_security import Security,hash_password,verify_password
from flask_cors import CORS
from flask_restful import Api
from dotenv import load_dotenv

import eventlet
import json
from flask_mqtt import Mqtt,MQTT_LOG_INFO,MQTT_LOG_NOTICE,MQTT_LOG_DEBUG
from flask_socketio import SocketIO
from flask_bootstrap import Bootstrap

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET'] = 'my secret key'


# Parameters for SSL enabled
# app.config['MQTT_BROKER_PORT'] = 8883
# app.config['MQTT_TLS_ENABLED'] = True
# app.config['MQTT_TLS_INSECURE'] = True
# app.config['MQTT_TLS_CA_CERTS'] = 'ca.crt'



load_dotenv('./.env')

app = Flask(__name__, static_folder='static')
# csrf = CSRFProtect(app)

# WEBSITE_HOSTNAME exists only in production environment
if 'WEBSITE_HOSTNAME' not in os.environ:
    # local development, where we'll use environment variables
    print("Loading config.development and environment variables from .env file.")
    app.config.from_object('azureproject.development')
else:
    # production
    print("Loading config.production.")
    app.config.from_object('azureproject.production')

app.config.update(
    SQLALCHEMY_DATABASE_URI=app.config.get('DATABASE_URI'),
    SQLALCHEMY_TRACK_MODIFICATIONS=True,
)

# Initialize the database connection

# Enable Flask-Migrate commands "flask db init/migrate/upgrade" to work


# The import must be done after db initialization due to circular import issue
from models import db,Appliance,Device,Users,user_datastore
db.init_app(app)
migrate = Migrate(app, db)
#Security init
security = Security(app,user_datastore)

CORS(app)
app.app_context().push()

api= Api(app)
mqtt = Mqtt(app)
socketio = SocketIO(app)
bootstrap = Bootstrap(app)
app.app_context().push()

from api import *
api.add_resource(UserApi,'/api/user/<string:username>','/api/user')
api.add_resource(DeviceApi,'/api/devices/<int:id>','/api/devices')
api.add_resource(LoginApi,'/api/login')
api.add_resource(ApplianceApi,'/api/log/<int:log_id>','/api/log')

@app.login_manager.unauthorized_handler
def unauth_handler():
    if request.is_json:
        return jsonify(message='Authorize please to access this page.'), 401
    else:
        return render_template('errors.html'), 401

@app.route('/',methods=['GET','POST'])
def home():
    if current_user.is_authenticated:
        return index()
    else:
        return login()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method=='POST':
        uname=request.form.get('username')
        passd=request.form.get('password')
        try:
            user=Users.query.filter(Users.username==uname).first()
            if user==None:
                raise Exception("usernotfound")
        except Exception as e:
            print(e)
            return render_template('login.html',error='incorrect password or username')
        if verify_password(passd,user.password):
            login_user(user,True) #session login
            return index()
    else:
        return render_template('login.html')
#---------------------------
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/signup',methods=['GET','POST'])
def signup():
    if request.method=='POST':
        uname=request.form.get('username')
        passd=request.form.get('password')
        email=request.form.get('email')
        location = request.values.get('location')
        if uname not in [i.username for i in Users.query.all()] and email_valid(email):
            user_datastore.create_user(username=uname,email=email,location=location, password=hash_password(passd))
            db.session.commit()
            return login()
        return render_template('notfound.html',error="invalid email")
    return render_template('signup.html')

@app.route('/index', methods=['GET'])
def index():
    print('Request for index page received')
    try:
        devices = Device.query.filter(Device.user_id==current_user.id).all()
    except Exception as e:
        print(e)
        return render_template('errors.html',)
    return render_template('devices.html', devices=devices)

@app.route('/details/<int:id>', methods=['GET'])
def details(id):
    device = Device.query.where(Device.id== id).first()
    appliances=Appliance.query.where(Appliance.device_id==id).order_by(Appliance.id).all()
    return render_template('details.html', device=device,appliances=appliances)

@app.route('/create', methods=['GET'])
def create_device():
    print('Request for add device page received')
    return render_template('create_device.html')

@app.route('/add', methods=['POST'])
def add_device():
    try:
        secret= request.values.get('secret')
        name = request.values.get('name')
        room_name = request.values.get('room_name')
        user_id = current_user.id
        if len(secret)!=8:
            return render_template('errors.html',error_message= "You must include a room name and device secret key")
        device = Device()
        device.name = name
        device.secret=secret
        device.room_name=room_name
        device.user_id=user_id
        db.session.add(device)
        db.session.commit()
        app1=Appliance(name="Light 1",type="digital",device_id=device.id)
        app2=Appliance(name="Light 2",type="digital",device_id=device.id)
        app3=Appliance(name="Socket",type="digital",device_id=device.id)
        app4=Appliance(name="Fan",type="analog",device_id=device.id)
        db.session.add(app1)
        db.session.add(app2)
        db.session.add(app3)
        db.session.add(app4)
        db.session.commit()
        return redirect(url_for('details', id=device.id))
    except (KeyError):
        # Redisplay the question voting form.
        return render_template('add_device.html', {
            'error_message': "You must include a device name, address, and description",
        })

@app.route('/device/update/<int:id>', methods=['GET','POST'])
def update_device(id):
    if request.method=='POST':
        device = Device.query.get(id)
        if device:
            device.name = request.values.get('name')
            device.room_name = request.values.get('room_name')
            db.session.commit()
            return redirect(url_for('details', id=device.id))
        else:
            return render_template('errors.html',error_message="device not found")
    else:  
        device = Device.query.get(id)
        return render_template('update_device.html', device=device)

@app.route('/device/delete/<int:id>', methods=['GET'])
def delete_device(id):
    device = Device.query.get(id)
    if device:
        db.session.delete(device)
        db.session.commit()
        return redirect(url_for('index'))
    else:
        return render_template('errors.html',error_message="device not found")

@app.route('/appliance/<int:id>', methods=['POST'])
def add_appliance(id):
    try:
        user_name = request.values.get('user_name')
        rating = request.values.get('rating')
        appliance_text = request.values.get('appliance_text')
    except (KeyError):
        #Redisplay the question voting form.
        return render_template('add_appliance.html', {
            'error_message': "Error adding appliance",
        })
    else:
        appliance = Appliance()
        appliance.device = id
        appliance.appliance_date = datetime.now()
        appliance.user_name = user_name
        appliance.rating = int(rating)
        appliance.appliance_text = appliance_text
        db.session.add(appliance)
        db.session.commit()
    return redirect(url_for('details', id=id))

@app.route('/appliance/update/{{appliance.id}}', methods=['GET','POST'])
def update_appliance(id):
    if request.method=='POST':
        appliance = Appliance.query.get(id)
        if appliance:
            appliance.name = request.values.get('name')
            appliance.type = request.values.get('type')
            db.session.commit()
            return redirect(url_for('details', id=appliance.id))
        else:
            return render_template('errors.html',error_message="device not found")
    else:  
        appliance = Appliance.query.get(id)
        return render_template('details.html', Appliance=appliance)

@app.route('/change/<int:id>', methods=['POST'])
def change_appliances(id):
    try:
        device=Device.query.get(id)
        if device:
            data=dict()
            appliances=Appliance.query.filter(Appliance.device_id==device.id).order_by(Appliance.id).all()
            for i in range(1,5):
                appliance = appliances[i-1]
                if request.values.get("app"+str(i)+"_mode"):
                    appliance.mode = 1
                    if request.values.get("app"+str(i)+"_time"):
                        appliance.mode_time=request.values.get("app"+str(i)+"_time")
                    print(appliance.mode_time)
                    appliance.value = 0
                    db.session.commit()
                    data["app"+str(i)+"_mode"]=appliance.mode
                    data["app"+str(i)+"_value"]=appliance.value
                    data["app"+str(i)+"_mode_time"]=appliance.mode_time
                else:
                    appliance.mode = 0
                    appliance.mode_time=0
                    if request.values.get("app"+str(i)+"_status"):
                        appliance.value = 1
                    else:
                        appliance.value = 0
                    db.session.commit()
                    data["app"+str(i)+"_mode"]=appliance.mode
                    data["app"+str(i)+"_value"]=appliance.value
                    data["app"+str(i)+"_mode_time"]=appliance.mode_time
            mqtt.publish("envision/"+device.secret+"/request",json.dumps(data))
            return redirect(url_for('details', id=id))
        else:
            return render_template('errors.html',error_message="device not found")
    except (KeyError):
        return render_template('errors.html',error_message="change error")


    

@app.context_processor
def utility_processor():
    def star_rating(id):
        appliances = Appliance.query.where(Appliance.device == id)
        ratings = []
        appliance_count = 0
        for appliance in appliances:
            ratings += [appliance.rating]
            appliance_count += 1

        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        stars_percent = round((avg_rating / 5.0) * 100) if appliance_count > 0 else 0
        return {'avg_rating': avg_rating, 'appliance_count': appliance_count, 'stars_percent': stars_percent}

    return dict(star_rating=star_rating)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/offline.html')
def offline():
   return app.send_static_file('offline.html')


@app.route('/service-worker.js')
def sw():
   return app.send_static_file('service-worker.js')

@app.route('/mqtt')
def main():
    mqtt.subscribe("envision/action")
    mqtt.publish("envision/photo","hello")
    print("done")
    return "Successful"


@socketio.on('publish')
def handle_publish(json_str):
    data = json.loads(json_str)
    mqtt.publish(data['topic'], data['message'])


@socketio.on('subscribe')
def handle_subscribe(json_str):
    data = json.loads(json_str)
    mqtt.subscribe(data['topic'])


@socketio.on('unsubscribe_all')
def handle_unsubscribe_all():
    mqtt.unsubscribe_all()


@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    data = dict(
        topic=message.topic,
        payload=message.payload.decode()
    )
    print(data)
    socketio.emit('mqtt_message', data=data)


# @mqtt.on_log()
# def handle_logging(client, userdata, level, buf):
#     print(level,MQTT_LOG_NOTICE)
#     if level==16:
#         print(userdata,level, buf)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0',use_reloader=True, debug=True)
