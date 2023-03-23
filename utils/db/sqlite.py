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

import sqlite3
import datetime

from utils import timestamp_now, get_string_status
from utils.db import BaseStateStore


class DB(BaseStateStore):
    """Class/context manager to connect to state store using SQLite3"""

    def __init__(
        self,
        db_name: str,
        sys_config: dict = None,
    ):
        self.db_name = db_name
        self.sys_config = sys_config
        self.conn = None
        self.cur = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cur = self.conn.cursor()
        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):
        if self.conn is not None:
            try:
                self.conn.close()
            except:
                pass

    def execute(
        self,
        expression: str,
        parameters: list = None,
        commit: bool = False,
    ):
        result = self.cur.execute(
            expression,
            parameters or list(),
        )
        if commit:
            self.conn.commit()
        return result

    def create_customer_table(self):
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.sys_config["state-store-delivery"]["table_customers"]} (
                order_id TEXT PRIMARY KEY,
                timestamp INTEGER,
                customer_id TEXT
            )""",
            commit=True,
        )

    def create_order_table(self):
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.sys_config["state-store-orders"]["table_orders"]} (
                order_id TEXT PRIMARY KEY,
                timestamp INTEGER,
                username TEXT,
                customer_id TEXT,
                status INTEGER,
                sauce TEXT,
                cheese TEXT,
                topping TEXT,
                extras TEXT
            )""",
            commit=True,
        )

    def create_status_table(self):
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.sys_config["state-store-orders"]["table_status"]} (
                order_id TEXT PRIMARY KEY,
                timestamp INTEGER,
                status INTEGER
            )""",
            commit=True,
        )

    def check_status_stuck(self) -> dict:
        self.execute(
            f"""SELECT * FROM {self.sys_config["state-store-orders"]["table_status"]}
                WHERE
                    timestamp < {timestamp_now()- self.sys_config["state-store-orders"]["status_invalid_timeout_minutes"]* 60 * 1000}
                    AND status NOT IN ({",".join([str(s) for s in self.sys_config["state-store-orders"]["status_completed_when"]])})
            """,
            commit=False,
        )
        data = self.cur.fetchall()
        data_all = dict()
        if data:
            cols = list(map(lambda x: x[0], self.cur.description))
            for item in data:
                item = dict(zip(cols, item))
                data_all[item["order_id"]] = {
                    "status": item["status"],
                    "timestamp": item["timestamp"],
                }
        return data_all

    def delete_stuck_status(
        self,
        order_id: str,
    ):
        self.execute(
            f"""DELETE FROM {self.sys_config["state-store-orders"]["table_status"]}
                WHERE
                    order_id=?
            """,
            parameters=[
                order_id,
            ],
            commit=True,
        )

    def delete_past_timestamp(
        self,
        table_name: str,
        timestamp_field: str = "timestamp",
        hours: int = 1,
    ):
        self.execute(
            f"""DELETE FROM {table_name}
            WHERE
                {timestamp_field} < {timestamp_now() - hours * 60 * 60 * 1000}
            """,
            commit=True,
        )

    def get_order_id_customer(
        self,
        order_id: str,
    ) -> dict:
        self.execute(
            f"""SELECT * FROM {self.sys_config["state-store-delivery"]["table_customers"]}
                WHERE
                    order_id=?
            """,
            parameters=[
                order_id,
            ],
            commit=False,
        )
        data = self.cur.fetchone()
        if data is not None:
            cols = list(map(lambda x: x[0], self.cur.description))
            data = dict(zip(cols, data))
        return data

    def get_order_id(
        self,
        order_id: str,
        customer_id: str = None,
    ) -> dict:
        where_clause = "order_id=?"
        parameters = [order_id]
        if customer_id is not None:
            where_clause += " AND customer_id=?"
            parameters.append(customer_id)
        self.execute(
            f"""SELECT * FROM {self.sys_config["state-store-orders"]["table_orders"]}
                WHERE
                    {where_clause}
            """,
            commit=False,
            parameters=parameters,
        )
        data = self.cur.fetchone()
        if data is not None:
            cols = list(map(lambda x: x[0], self.cur.description))
            data = dict(zip(cols, data))
            data["extras"] = ", ".join(data["extras"].split(","))
            data["status_str"] = get_string_status(
                self.sys_config["status"], data["status"]
            )
        return data

    def get_orders(
        self,
        customer_id: str,
    ) -> dict:
        self.execute(
            f"""SELECT * FROM {self.sys_config["state-store-orders"]["table_orders"]}
            WHERE
                customer_id=?
            ORDER BY
                timestamp DESC
            """,
            parameters=[
                customer_id,
            ],
            commit=False,
        )
        data = self.cur.fetchall()
        data_all = dict()
        if data:
            cols = list(map(lambda x: x[0], self.cur.description))
            for item in data:
                item = dict(zip(cols, item))
                data_all[item["order_id"]] = item
                data_all[item["order_id"]]["extras"] = ", ".join(
                    data_all[item["order_id"]]["extras"].split(",")
                )
                data_all[item["order_id"]]["status_str"] = get_string_status(
                    self.sys_config["status"],
                    data_all[item["order_id"]]["status"],
                )
                data_all[item["order_id"]][
                    "timestamp"
                ] = datetime.datetime.fromtimestamp(
                    data_all[item["order_id"]]["timestamp"] / 1000
                ).strftime(
                    "%Y-%b-%d %H:%M:%S"
                )
        return data_all

    def update_order_status(
        self,
        order_id: str,
        status: int,
    ):
        self.execute(
            f"""UPDATE {self.sys_config["state-store-orders"]["table_orders"]} SET
                    status={status}
                WHERE
                    order_id=?
            """,
            parameters=[
                order_id,
            ],
            commit=True,
        )

    def upsert_status(
        self,
        order_id: str,
        status: int,
    ):
        timestamp = timestamp_now()
        self.execute(
            f"""INSERT INTO {self.sys_config["state-store-orders"]["table_status"]} (
                order_id,
                timestamp,
                status
            ) VALUES (
                ?,
                {timestamp},
                {status}
            ) ON CONFLICT (order_id) DO UPDATE SET
                timestamp={timestamp},
                status={status}
            WHERE
                order_id=?
            """,
            parameters=[
                order_id,
                order_id,
            ],
            commit=True,
        )

    def update_customer(
        self,
        order_id: str,
        customer_id: dict,
    ):
        self.execute(
            f"""UPDATE {self.sys_config["state-store-delivery"]["table_customers"]} SET
                    timestamp={timestamp_now()},
                    customer_id=?
                WHERE
                    order_id=?
            """,
            parameters=[
                customer_id,
                order_id,
            ],
            commit=True,
        )

    def add_customer(
        self,
        order_id: str,
        customer_id: dict,
    ):
        self.execute(
            f"""INSERT INTO {self.sys_config["state-store-delivery"]["table_customers"]} (
                order_id,
                timestamp,
                customer_id
            )
            VALUES (
                ?,
                {timestamp_now()},
                ?
            )""",
            parameters=[
                order_id,
                customer_id,
            ],
            commit=True,
        )

    def add_order(
        self,
        order_id: str,
        order_details: dict,
    ):
        self.execute(
            f"""INSERT INTO {self.sys_config["state-store-orders"]["table_orders"]} (
                order_id,
                timestamp,
                username,
                customer_id,
                status,
                sauce,
                cheese,
                topping,
                extras
            )
            VALUES (
                ?,
                {timestamp_now()},
                ?,
                ?,
                {self.sys_config["status-id"]["order_placed"]},
                ?,
                ?,
                ?,
                ?
            )""",
            parameters=[
                order_id,
                order_details["order"]["username"],
                order_details["order"]["customer_id"],
                order_details["order"]["sauce"],
                order_details["order"]["cheese"],
                order_details["order"]["main_topping"],
                ",".join(order_details["order"]["extra_toppings"]),
            ],
            commit=True,
        )
