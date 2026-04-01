# -*- coding: utf-8 -*-
#
# Copyright 2022 Confluent Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Web application

import os
import re
import json
import uuid
import logging
import datetime

from flask import Flask, request, session, jsonify, send_from_directory
from flask_cors import CORS
from flask_login import (
    UserMixin,
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from utils import (
    FOLDER_LOGS,
    EXTENSION_LOGS,
    GracefulShutdown,
    log_ini,
    save_pid,
    get_hostname,
    get_script_name,
    delivery_report,
    delivery_report_avro,
    timestamp_now,
    validate_cli_args,
    get_system_config,
    set_producer_consumer,
    import_state_store_class,
    get_schema_registry_client,
    create_avro_serializer,
)
from confluent_kafka.serialization import SerializationContext, MessageField


####################
# Global variables #
####################
SCRIPT = get_script_name(__file__)
HOSTNAME = get_hostname()
log_ini(SCRIPT)
next_delete_past_timestamp = datetime.datetime.now()

# Validate command arguments
kafka_config_file, sys_config_file = validate_cli_args(SCRIPT)

# Get system config file
SYS_CONFIG = get_system_config(sys_config_file)

# Set producer object
delivery_report_avro(kafka_config_file)
PRODUCE_TOPIC_ORDERED = SYS_CONFIG["kafka-topics"]["pizza_ordered"]
_, PRODUCER, _, _ = set_producer_consumer(
    kafka_config_file,
    producer_extra_config={
        "on_delivery": delivery_report,
        "client.id": f"""{SYS_CONFIG["kafka-client-id"]["webapp"]}_{HOSTNAME}""",
    },
    disable_consumer=True,
)

# Set Schema Registry client and Avro serializer
SCHEMA_REGISTRY_CLIENT = get_schema_registry_client(kafka_config_file)
AVRO_SERIALIZER = create_avro_serializer(
    SCHEMA_REGISTRY_CLIENT,
    PRODUCE_TOPIC_ORDERED,
)

# Set signal handler
GRACEFUL_SHUTDOWN = GracefulShutdown()

# State Store (Get DB class dynamically)
DB = import_state_store_class(SYS_CONFIG["state-store-orders"]["db_module_class"])
ORDERS_DB = SYS_CONFIG["state-store-orders"]["name"]
with GRACEFUL_SHUTDOWN as _:
    with DB(
        ORDERS_DB,
        sys_config=SYS_CONFIG,
    ) as db:
        db.create_order_table()
        db.delete_past_timestamp(
            SYS_CONFIG["state-store-orders"]["table_orders"],
            hours=int(SYS_CONFIG["state-store-orders"]["table_orders_retention_hours"]),
        )

# Webapp (Flask)
app = Flask(
    __name__,
    static_folder="frontend/build",
    static_url_path="",
)
app.config["SECRET_KEY"] = "718d5fec-cc52-4b29-b3dd-9c2e7b97266e"
CORS(app, supports_credentials=True)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
log = logging.getLogger("werkzeug")
log.setLevel(logging.WARNING)


###########
# Classes #
###########
class User(UserMixin):
    def __init__(self, id: str) -> None:
        super().__init__()
        self.id = id


#################
# Flask routing #
#################
@app.route("/health-check", methods=["GET"])
def view_logs():
    """Health-Check for LB"""
    return "Ok"


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Unauthorized"}), 401


@login_manager.user_loader
def load_user(customer_id):
    return User(id=customer_id)


@app.route("/api/auth/check", methods=["GET"])
def check_auth():
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "username": session.get("username", "Anonymous"),
            "customer_id": session.get("customer_id", "")
        })
    else:
        return jsonify({"authenticated": False})


@app.route("/api/auth/login", methods=["POST"])
def do_login():
    data = request.get_json()
    session["customer_id"] = uuid.uuid4().hex
    session["username"] = data.get("username", "Anonymous").strip()[:16]
    login_user(
        User(session["username"]),
        duration=datetime.timedelta(hours=1),
        force=True,
    )
    return jsonify({
        "success": True,
        "username": session["username"],
        "customer_id": session["customer_id"]
    })


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.pop("username", None)
    session.pop("customer_id", None)
    return jsonify({"success": True})


@app.route("/api/menu", methods=["GET"])
@login_required
def view_menu():
    """Get pizza menu options"""
    return jsonify({
        "sauces": SYS_CONFIG["pizza"]["sauce"],
        "cheeses": SYS_CONFIG["pizza"]["cheese"],
        "main_toppings": SYS_CONFIG["pizza"]["main_topping"],
        "extra_toppings": SYS_CONFIG["pizza"]["extra_toppings"],
    })


@app.route("/api/orders", methods=["POST"])
@login_required
def order_pizza():
    """Process pizza order request"""
    with GRACEFUL_SHUTDOWN as _:
        # Generate order unique ID
        order_id = uuid.uuid4().hex[-8:]

        # Get request data
        data = request.get_json()
        order_data = {
            "sauce": data.get("sauce"),
            "cheese": data.get("cheese"),
            "main_topping": data.get("main_topping"),
            "customer_id": session["customer_id"],
            "username": session["username"],
        }

        # Get extra topping list
        extra_toppings = data.get("extra_toppings", [])

        order_details = {
            "status": SYS_CONFIG["status-id"]["order_placed"],
            "timestamp": timestamp_now(),
            "order": {
                "extra_toppings": extra_toppings,
                **order_data,
            },
        }

        # Add order to DB
        with DB(
            ORDERS_DB,
            sys_config=SYS_CONFIG,
        ) as db:
            db.add_order(
                order_id,
                order_details,
            )
            # Add to status to check statefulness (daemon on msvc_status)
            db.upsert_status(
                order_id,
                SYS_CONFIG["status-id"]["order_placed"],
            )

        # Produce to kafka topic with Avro serialization
        if AVRO_SERIALIZER:
            # Use Avro serialization
            value = AVRO_SERIALIZER(
                order_details,
                SerializationContext(
                    PRODUCE_TOPIC_ORDERED,
                    MessageField.VALUE,
                ),
            )
        else:
            # Fallback to JSON if Schema Registry is not configured
            value = json.dumps(order_details).encode()

        PRODUCER.produce(
            PRODUCE_TOPIC_ORDERED,
            key=order_id,
            value=value,
        )
        PRODUCER.flush()

        return jsonify({
            "success": True,
            "order_id": order_id
        })


@app.route("/api/orders", methods=["GET"])
@login_required
def view_orders():
    """View all orders for the customer_id"""
    global next_delete_past_timestamp

    with GRACEFUL_SHUTDOWN as _:
        with DB(
            ORDERS_DB,
            sys_config=SYS_CONFIG,
        ) as db:
            if next_delete_past_timestamp < datetime.datetime.now():
                # Only go through that cycle every 60 seconds
                next_delete_past_timestamp = (
                    datetime.datetime.now() + datetime.timedelta(seconds=60)
                )
                db.delete_past_timestamp(
                    SYS_CONFIG["state-store-orders"]["table_orders"],
                    hours=int(
                        SYS_CONFIG["state-store-orders"]["table_orders_retention_hours"]
                    ),
                )
            return jsonify({
                "orders": db.get_orders(session["customer_id"])
            })


@app.route("/api/orders/<order_id>/status", methods=["GET"])
@login_required
def get_order_ajax(order_id):
    """View order status by order_id"""
    with GRACEFUL_SHUTDOWN as _:
        with DB(
            ORDERS_DB,
            sys_config=SYS_CONFIG,
        ) as db:
            order_details = db.get_order_id(
                order_id,
                customer_id=session["customer_id"],
            )
            if order_details is not None:
                return jsonify({
                    "str": order_details["status_str"],
                    "status": order_details["status"],
                })
    return jsonify({"error": "Order not found"}), 404


@app.route("/api/orders/<order_id>", methods=["GET"])
@login_required
def get_order(order_id: str):
    """View order by order_id"""
    with GRACEFUL_SHUTDOWN as _:
        with DB(
            ORDERS_DB,
            sys_config=SYS_CONFIG,
        ) as db:
            order_details = db.get_order_id(
                order_id,
                customer_id=session["customer_id"],
            )
            if order_details is not None:
                # Order exists
                return jsonify({
                    "order_id": order_id,
                    "timestamp": datetime.datetime.fromtimestamp(
                        order_details["timestamp"] / 1000
                    ).strftime("%Y-%b-%d %H:%M:%S"),
                    "status": int(order_details["status"]),
                    "status_str": order_details["status_str"],
                    "status_delivered": SYS_CONFIG["status-id"]["delivered"],
                    "username": order_details["username"],
                    "sauce": order_details["sauce"],
                    "cheese": order_details["cheese"],
                    "topping": order_details["topping"],
                    "extras": order_details["extras"],
                })
            else:
                # Order does not exist
                return jsonify({"error": f"Order '{order_id}' not found"}), 404


@app.route("/api/logs/<order_id>", methods=["GET"])
@login_required
def view_logs_ajax(order_id: str):
    """View logs"""
    msvc_logs = {
        "all_logs": list(),
    }
    log_files = [
        os.path.join(FOLDER_LOGS, file)
        for file in os.listdir(FOLDER_LOGS)
        if EXTENSION_LOGS in file
    ]
    for file in log_files:
        msvc_name = os.path.splitext(os.path.splitext(os.path.split(file)[-1])[0])[0]
        if msvc_name not in msvc_logs.keys():
            msvc_logs[msvc_name] = list()
        with open(file, "r") as f:
            lines = f.read().split("\x00")
            lines = [
                line.strip("\n").replace("\n", "<br>")
                for line in lines
                if order_id in line
            ]
            msvc_logs["all_logs"] += lines
            msvc_logs[msvc_name] += lines
    if msvc_logs["all_logs"]:
        for k in msvc_logs.keys():
            msvc_logs[k].sort()  # sort lines by timestamp
            msvc_logs[k] = "<br><br>".join(msvc_logs[k])
            headers = re.findall(
                "(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}.\d{3} \[.+?\].+?:)",
                msvc_logs[k],
            )
            for header in headers:
                msvc_logs[k] = msvc_logs[k].replace(
                    header, f"""<b>{header.replace(": ", ":<br>")}</b>"""
                )
        for k in msvc_logs.keys():
            msvc_logs[k] = (
                msvc_logs[k].replace("<br>" * 3, "<br>" * 2) + "<br>" + "<br>"
            )
    else:
        msvc_logs = {
            "all_logs": f"No logs found for order_id {order_id}",
        }
    return jsonify(msvc_logs)


# Serve static files (React build assets and images)
@app.route("/static/<path:filename>")
def serve_static(filename):
    """Serve static files from React build or app/static"""
    # First, try to serve from React build's static folder (JS, CSS)
    react_static_path = os.path.join(app.static_folder, "static", filename)
    if os.path.exists(react_static_path):
        return send_from_directory(os.path.join(app.static_folder, "static"), filename)

    # Otherwise, serve from app/static (images)
    return send_from_directory("static", filename)


# Custom 404 error handler - serve React app
@app.errorhandler(404)
def not_found(e):
    """Serve React app for all 404 errors (let React Router handle routing)"""
    # Don't intercept API 404s - return JSON
    if request.path.startswith('/api/'):
        return jsonify({"error": "Not found"}), 404

    # For all other paths, serve React app
    return send_from_directory(app.static_folder, "index.html")


# Serve React App
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    """Serve React app for all non-API routes"""
    # Skip API routes (they're handled above)
    if path.startswith('api/'):
        return jsonify({"error": "Not found"}), 404

    # Try to serve file from React build (for assets like favicon.ico)
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)

    # Otherwise serve React index.html (React Router will handle the routing)
    return send_from_directory(app.static_folder, "index.html")


########
# Main #
########
def main(*args):
    # If started using gunicorn
    return app


if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # Start web app
    app.run(
        host="localhost",
        port=8000,
        debug=True,
    )
